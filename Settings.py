import html
import json
import os
import re
import unicodedata
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from groq import Groq

try:
    from google import genai as _genai  # SDK google-genai (>=2.x)
    from google.genai import types as _genai_types
    _GENAI_AVAILABLE = True
except Exception:  # pragma: no cover - lib non installee
    _genai = None
    _genai_types = None
    _GENAI_AVAILABLE = False

try:
    from bs4 import MarkupResemblesLocatorWarning
    warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)
except ImportError:
    pass


current_dir = Path(__file__).parent if "__file__" in locals() else Path.cwd()
css_file = current_dir / "main.css"


def load_css():
    if css_file.exists():
        with open(css_file, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)



MEDIA_SCOUT_THEMES = [
    "Agrumes, Fruits rouges & Maraichage",
    "Produits laitiers & Epicerie fine",
    "Elevage (Ovins, Bovins, Caprins, Volailles)",
    "Aquaculture (elevage et transformation)",
    "Environnement, Eau & Energie",
    "ESG, QSE & SST",
]

MEDIA_SCOUT_THEME_EMOJI = {
    "Agrumes, Fruits rouges & Maraichage":           "🍊",
    "Elevage (Ovins, Bovins, Caprins, Volailles)":   "🐄",
    "Aquaculture (elevage et transformation)":       "🐟",
    "Produits laitiers & Epicerie fine":             "🧀",
    "Environnement, Eau & Energie":                  "🌍",
    "ESG, QSE & SST":                                "🏛️",
}

MEDIA_SCOUT_VEILLES = [
    "Veille Reglementaire",
    "Veille Informative",
    "Veille Evenementielle",
    "Veille Concurrentielle",
]

MEDIA_SCOUT_VEILLE_EMOJI = {
    "Veille Reglementaire":   "⚖️",
    "Veille Informative":     "📰",
    "Veille Evenementielle":  "📅",
    "Veille Concurrentielle": "🎯",
}

MEDIA_SCOUT_SOURCE_CATALOG = [
    # ─── MAROC ─────────────────────────────────────────────────────────────────
    # NB: sources retirees car injoignables/SPA (404, SSL, JS) : FNH, CGEM,
    # Medias24, ministeres (Agriculture/Sante/Transition Energ.), Dept Env,
    # IMANOR, AMMC. Leur contenu est desormais capte via les flux Google News
    # RSS reglementaires/institutionnels MA (cf. section dediee plus bas).
    {"Journal": "AgriMaroc", "URL": "https://www.agrimaroc.ma/actualite-agricole/", "Couverture": "Eau, climat, agriculture durable"},
    {"Journal": "Le Vert", "URL": "https://levert.ma/category/transition-energetique/", "Couverture": "Transition energetique"},
    {"Journal": "Le Vert - Developpement Durable", "URL": "https://levert.ma/category/developpement-durable/", "Couverture": "Developpement durable"},
    {"Journal": "MAP Ecology", "URL": "https://mapecology.ma/", "Couverture": "Ecologie, environnement, climat"},
    {"Journal": "Ministere Equipement et Eau", "URL": "https://www.equipement.gov.ma/Actualites/Pages/Actualites.aspx", "Couverture": "Eau, barrages, infrastructures"},
    {"Journal": "ONSSA", "URL": "https://www.onssa.gov.ma/actualites/", "Couverture": "Securite sanitaire des aliments, normes alimentaires"},

    # ─── UE - Reglementation alimentaire & EFSA (impact direct exports Maroc) ──
    {"Journal": "EFSA", "URL": "https://www.efsa.europa.eu/en/news", "Couverture": "Securite alimentaire europeenne, EFSA"},
    {"Journal": "DG SANTE EU - Food", "URL": "https://food.ec.europa.eu/news_en", "Couverture": "Politique alimentaire, food safety, regulations"},

    # ─── UE - ESG / QSE / SST (normes & directives impactant Maroc) ────────────
    # NB: retires car injoignables/SPA/0-article : Actu-Environnement (404),
    # EU-OSHA, EU Health News (403), Novethic (SPA), Commission EU Finance
    # Durable (SPA). Couverture normes/RSE/SST desormais via Google News RSS.
    {"Journal": "AFNOR Actualites", "URL": "https://www.afnor.org/actualites/", "Couverture": "Normes, certification, AFNOR (influence ISO)"},
    {"Journal": "EU EMAS", "URL": "https://green-business.ec.europa.eu/eco-management-and-audit-scheme-emas_en", "Couverture": "EMAS, management environnemental"},
    {"Journal": "EFRAG", "URL": "https://www.efrag.org/en/news-and-calendar/news", "Couverture": "CSRD, ESRS"},

    # ─── UE - Food industry / FMCG (couverture globale, pas locale) ────────────
    {"Journal": "Food Navigator", "URL": "https://www.foodnavigator.com/", "Couverture": "Food trends (global), FMCG, retail"},

    # ─── WORLD - Agriculture ───────────────────────────────────────────────────
    # NB: Codex (404) et GlobalG.A.P. (404) retires -> repris via Google News RSS normes.
    {"Journal": "FAO Newsroom", "URL": "https://www.fao.org/newsroom/en", "Couverture": "Agriculture, alimentation, securite alimentaire"},

    # ─── PRODUITS FRAIS / FILIERE FRUITS & LEGUMES (T1 selon contenu) ──────────
    # Presse specialisee fruits & legumes frais (export, marche, varietes). NON
    # forcees sur un theme : le scoring keywords + validation LLM ne gardent que
    # les articles lies aux cultures LDA (agrumes, fruits rouges, maraichage),
    # ce qui evite le bruit (bananes/avocats que LDA ne produit pas). Les sources
    # EN (FruitNet, FreshFruitPortal) sont auto-traduites en FR a l'affichage.
    {"Journal": "FreshPlaza FR",     "URL": "https://news.google.com/rss/search?q=site:freshplaza.fr&hl=fr&gl=MA&ceid=MA:fr", "Couverture": "Fruits & legumes frais — marche, export (FreshPlaza, via GNews)"},
    {"Journal": "Agro-media",        "URL": "https://www.agro-media.fr/feed/",        "Couverture": "Agroalimentaire France — filieres, industrie, innovation"},
    {"Journal": "FreshFruitPortal",  "URL": "https://www.freshfruitportal.com/feed/", "Couverture": "Fruits frais mondial — marche, export, varietes"},
    {"Journal": "FruitNet",          "URL": "https://www.fruitnet.com/45.rss",        "Couverture": "Filiere fruits & legumes (international, trade)"},

    # ─── CONCURRENTS LDA — Sites corporates : TOUS retires (SPA JS / pages mortes,
    # ex. Lesieur Cristal, Groupe Bel, Nestlé MENA, Aïcha). Marques concurrentes
    # entierement couvertes par les flux Google News RSS ci-dessous. ────────────

    # ─── CONCURRENTS LDA — Google News RSS (one per cluster) ───────────────────
    # Feeds RSS XML standard, ultra-fiables. Chaque feed cible une marque ou un
    # cluster de marques concurrentes via une recherche Google News dediee.
    # Le scraper RSS extrait titre + date (pubDate) + lien (URL wrappee Google).
    {"Journal": "GNews — Centrale Danone",   "URL": "https://news.google.com/rss/search?q=%22Centrale+Danone%22&hl=fr&gl=MA&ceid=MA:fr",                                                "Couverture": "Concurrent laitier MA — Centrale Danone Maroc (presse agregee)"},
    {"Journal": "GNews — COPAG Jaouda",      "URL": "https://news.google.com/rss/search?q=%22COPAG%22+OR+%22Jaouda%22&hl=fr&gl=MA&ceid=MA:fr",                                          "Couverture": "Concurrent laitier MA — COPAG / Jaouda (presse agregee)"},
    {"Journal": "GNews — Lesieur Cristal",   "URL": "https://news.google.com/rss/search?q=%22Lesieur+Cristal%22&hl=fr&gl=MA&ceid=MA:fr",                                                "Couverture": "Concurrent epicerie fine MA — Lesieur Cristal (presse agregee)"},
    {"Journal": "GNews — Marjane Maroc",     "URL": "https://news.google.com/rss/search?q=%22Marjane+Group%22+OR+%22Marjane+Maroc%22+OR+%22Carrefour+Maroc%22+OR+%22Label+Vie%22&hl=fr&gl=MA&ceid=MA:fr", "Couverture": "Concurrent distrib MA — Marjane, Carrefour, Label Vie, BIM (MDD)"},
    {"Journal": "GNews — Bel Maroc",         "URL": "https://news.google.com/rss/search?q=%22Vache+qui+rit%22+OR+%22Kiri%22+OR+%22Babybel%22+OR+%22Groupe+Bel%22&hl=fr&gl=MA&ceid=MA:fr",  "Couverture": "Concurrent laitier — Bel (Vache qui rit, Kiri, Babybel)"},
    {"Journal": "GNews — Lactalis",          "URL": "https://news.google.com/rss/search?q=%22Lactalis%22+OR+%22President+fromage%22+OR+%22Lactel%22+OR+%22Galbani%22&hl=fr&ceid=:fr",     "Couverture": "Concurrent laitier — Lactalis (President, Lactel, Galbani)"},
    {"Journal": "GNews — Savencia",          "URL": "https://news.google.com/rss/search?q=%22Savencia%22+OR+%22Caprice+des+Dieux%22+OR+%22Saint+Albray%22+OR+%22Elle+%26+Vire%22&hl=fr&ceid=:fr", "Couverture": "Concurrent laitier — Savencia (Caprice des Dieux, Saint Albray, Elle&Vire)"},
    {"Journal": "GNews — Bonne Maman Andros","URL": "https://news.google.com/rss/search?q=%22Bonne+Maman%22+OR+%22Andros+confiture%22+OR+%22Andros+groupe%22&hl=fr&ceid=:fr",            "Couverture": "Concurrent epicerie fine — Bonne Maman, Andros (confitures)"},
    {"Journal": "GNews — Hero St Dalfour",   "URL": "https://news.google.com/rss/search?q=%22Hero+confiture%22+OR+%22Hero+Group%22+OR+%22St+Dalfour%22+OR+%22St.+Dalfour%22&hl=fr&ceid=:fr",  "Couverture": "Concurrent epicerie fine — Hero, St. Dalfour (confitures premium)"},
    {"Journal": "GNews — Olive MA",          "URL": "https://news.google.com/rss/search?q=%22Cartier+Saada%22+OR+%22Zouitina%22+OR+%22Diana+Holding%22+OR+%22CaracTerre%22&hl=fr&gl=MA&ceid=MA:fr", "Couverture": "Concurrent epicerie fine MA — Cartier Saada, Zouitina, Diana Holding"},
    {"Journal": "GNews — Sovena Puget",      "URL": "https://news.google.com/rss/search?q=%22Sovena%22+OR+%22Oliveira+da+Serra%22+OR+%22Puget+huile%22+OR+%22Puget+olive%22&hl=fr&ceid=:fr", "Couverture": "Concurrent epicerie fine — Sovena, Oliveira da Serra, Puget (huiles d'olive)"},

    # ─── PRESSE ÉCONOMIQUE MAROC (RSS) — couverture multi-secteurs ─────────────
    # Articles concurrentiels detectes via mention explicite de marque LDA
    # (_LDA_COMPETITORS) — pas auto-classes T3. Le filtre post-scrape decide.
    {"Journal": "EcoActu",          "URL": "https://www.ecoactu.ma/feed/",       "Couverture": "Presse economique Maroc — entreprises, distribution, agro"},
    {"Journal": "Aujourd'hui Maroc","URL": "https://aujourdhui.ma/feed",         "Couverture": "Presse generaliste Maroc — economie, societe"},
    {"Journal": "Financial Afrik",  "URL": "https://www.financialafrik.com/feed/", "Couverture": "Presse economique Afrique — agro, FMCG, distribution"},

    # ─── VEILLE CONCURRENTIELLE T3 — Intelligence laitier & épicerie fine ──────
    # Sources organisees en 5 categories (concept "Catégorie"). Feeds Google News
    # consolides (topic-scopes sur le laitier/epicerie) + 2 presses MA en RSS direct.
    # Toutes forcees T3 + ajoutees aux sources concurrentes (cf. app.py).
    # C1 — Marché local & Maghreb
    {"Journal": "GNews — Presse éco MA", "URL": "https://news.google.com/rss/search?q=(site:leconomiste.com+OR+site:medias24.com+OR+site:leseco.ma)+(laitier+OR+fromage+OR+yaourt+OR+lait+OR+%22epicerie+fine%22+OR+distribution+OR+Danone+OR+Chergui)&hl=fr&gl=MA&ceid=MA:fr", "Couverture": "C1 Marché local — L'Économiste, Medias24, Les Éco (agro/distrib)"},
    {"Journal": "La Vie Éco",            "URL": "https://www.lavieeco.com/feed/",   "Couverture": "C1 Marché local — presse économique Maroc"},
    {"Journal": "Le Matin",              "URL": "https://lematin.ma/rssFeed/0",     "Couverture": "C1 Marché local — presse généraliste Maroc"},
    # C2 — Secteur laitier international
    {"Journal": "GNews — Lait International", "URL": "https://news.google.com/rss/search?q=(%22prix+du+lait%22+OR+%22marche+laitier%22+OR+%22cotation+lait%22+OR+%22filiere+laitiere%22+OR+%22dairy+market%22)&hl=fr&ceid=:fr", "Couverture": "C2 Secteur laitier intl — cotations, marché mondial du lait"},
    # C3 — FMCG, Retail & Distribution
    {"Journal": "GNews — FMCG Retail",   "URL": "https://news.google.com/rss/search?q=(site:lsa-conso.fr+OR+site:lineaires.com+OR+site:nielseniq.com+OR+site:kantar.com)+(laitier+OR+yaourt+OR+fromage+OR+lait+OR+distribution+OR+rayon)&hl=fr&ceid=:fr", "Couverture": "C3 FMCG/Retail — LSA, Linéaires, NielsenIQ, Kantar (laitier)"},
    # C4 — Nutrition fonctionnelle & Santé
    {"Journal": "GNews — Nutrition Santé", "URL": "https://news.google.com/rss/search?q=(%22nutrition+fonctionnelle%22+OR+%22probiotique%22+OR+%22fortification%22+OR+%22allegation+sante%22)+(lait+OR+laitier+OR+yaourt+OR+fromage)&hl=fr&ceid=:fr", "Couverture": "C4 Nutrition/Santé — probiotiques, fortification, allégations"},
    # C5 — Nouveautés produits & Marques premium
    {"Journal": "GNews — Nouveautés Premium", "URL": "https://news.google.com/rss/search?q=(%22lancement%22+OR+%22nouveau+produit%22+OR+%22packaging%22)+(laitier+OR+fromage+OR+yaourt+OR+lait+OR+%22epicerie+fine%22)&hl=fr&ceid=:fr", "Couverture": "C5 Nouveautés/Premium — lancements, packaging, repositionnements"},

    # ─── VEILLE CONCURRENTIELLE T1 — Agrumes, Fruits rouges & Tomates cerises ──
    # Intelligence export fruits & primeurs LDA, organisee en 5 categories.
    # Feeds Google News consolides (topic-scopes agrumes/fruits rouges/tomate
    # cerise). Toutes forcees T1 + Veille Concurrentielle (cf. app.py profils).
    # A1 — Marché Maroc (filiere & organismes export)
    {"Journal": "GNews — Agrumes Export MA",   "URL": "https://news.google.com/rss/search?q=(%22Morocco+Foodex%22+OR+%22EACCE%22+OR+%22Maroc+Citrus%22+OR+%22ASPAM%22+OR+%22export+agrumes%22+OR+%22export+primeurs%22+OR+%22fruits+rouges%22)+Maroc&hl=fr&gl=MA&ceid=MA:fr", "Couverture": "A1 Marché Maroc — Morocco Foodex, EACCE, Maroc Citrus, export primeurs"},
    # A2 — Export & marchés internationaux (cotations, campagnes, demande)
    {"Journal": "GNews — Marché Agrumes Intl", "URL": "https://news.google.com/rss/search?q=(%22citrus+market%22+OR+%22orange+price%22+OR+%22marche+agrumes%22+OR+%22campagne+agrumes%22+OR+%22citrus+export%22+OR+%22soft+citrus%22)&hl=fr&ceid=:fr", "Couverture": "A2 Export & marchés — cotations agrumes, campagnes, demande mondiale"},
    {"Journal": "GNews — Marché Fruits Rouges","URL": "https://news.google.com/rss/search?q=(%22berry+market%22+OR+%22blueberry%22+OR+%22strawberry+market%22+OR+%22marche+fruits+rouges%22+OR+%22soft+fruit%22)+(export+OR+prix+OR+marche)&hl=fr&ceid=:fr", "Couverture": "A2 Export & marchés — marché mondial des fruits rouges (berries)"},
    # A3 — Concurrents (exportateurs rivaux primeurs/fruits)
    {"Journal": "GNews — Concurrents Primeurs","URL": "https://news.google.com/rss/search?q=(%22Azura+Group%22+OR+%22Groupe+Azura%22+OR+%22Delassus%22+OR+%22Duroc%22+OR+%22Maraissa%22+OR+%22Disma+International%22+OR+%22Zalar%22+OR+%22Rosaflor%22+OR+%22Agrumar%22)&hl=fr&ceid=:fr", "Couverture": "A3 Concurrents — Azura, Delassus, Duroc, Maraissa, Zalar, Rosaflor, Agrumar"},
    # A4 — Filière & production (varietes, conditionnement, eau, regions)
    {"Journal": "GNews — Production Fruits MA","URL": "https://news.google.com/rss/search?q=(%22station+de+conditionnement%22+OR+%22variete+agrumes%22+OR+%22Nadorcott%22+OR+%22stress+hydrique%22+OR+%22verger%22+OR+%22Souss-Massa%22)+(agrumes+OR+fraise+OR+tomate)&hl=fr&gl=MA&ceid=MA:fr", "Couverture": "A4 Filière & production — variétés, conditionnement, eau, Souss-Massa"},
    # A5 — Variétés & premium (innovation produit, packaging)
    {"Journal": "GNews — Innovations Fruits",  "URL": "https://news.google.com/rss/search?q=(%22nouvelle+variete%22+OR+%22club+variety%22+OR+%22licence+varietale%22+OR+%22fruit+premium%22+OR+%22packaging%22)+(agrume+OR+fraise+OR+myrtille+OR+%22tomate+cerise%22)&hl=fr&ceid=:fr", "Couverture": "A5 Variétés & premium — nouvelles variétés, club varieties, packaging"},

    # ─── WORLD - Elevage (ovin/bovin/caprin/volaille) ──────────────────────────
    # NB: Poultry World + WOAH/OIE (SPA, 0 article) retires -> elevage couvert par
    # les flux GNews (Betail / Aviculture / Viande MA) + AgriMaroc Élevage.
    {"Journal": "DairyReporter","URL": "https://www.dairyreporter.com/",      "Couverture": "Filiere laitiere mondiale"},
    # AgriMaroc - section dediee elevage (en plus de la categorie generale)
    {"Journal": "AgriMaroc Élevage", "URL": "https://www.agrimaroc.ma/category/elevage/", "Couverture": "Elevage Maroc — ovins, bovins, caprins, volailles"},

    # ─── Google News RSS — Elevage Maroc (BÉTAIL strict) ───────────────────────
    # Queries focalisees STRICTEMENT sur les especes betail (ovin/bovin/caprin/
    # volaille) pour eviter les faux positifs (ex: "éleveurs d'olives", "élevé"
    # adjectif). On evite les termes generiques "elevage" / "eleveur" qui
    # peuvent matcher des contextes non-livestock.
    {"Journal": "GNews — Bétail MA",       "URL": "https://news.google.com/rss/search?q=(%22mouton%22+OR+%22ovin%22+OR+%22bovin%22+OR+%22caprin%22+OR+%22vache+laitiere%22+OR+%22cheptel%22+OR+%22betail%22)+Maroc&hl=fr&gl=MA&ceid=MA:fr", "Couverture": "Elevage MA — Bétail (ovins, bovins, caprins, cheptel)"},
    {"Journal": "GNews — Aviculture MA",    "URL": "https://news.google.com/rss/search?q=(%22aviculture%22+OR+%22filiere+avicole%22+OR+%22poulet%22+OR+%22volaille%22+OR+%22dinde%22)+Maroc&hl=fr&gl=MA&ceid=MA:fr",  "Couverture": "Elevage MA — Aviculture, volaille, poulet, dinde"},
    {"Journal": "GNews — Viande MA",       "URL": "https://news.google.com/rss/search?q=(%22filiere+viande%22+OR+%22viande+ovine%22+OR+%22viande+bovine%22+OR+%22abattoir%22+OR+%22marche+ovin%22)+Maroc&hl=fr&gl=MA&ceid=MA:fr", "Couverture": "Elevage MA — Filiere viande, abattoirs, marche ovin"},
    {"Journal": "GNews — ANOC FIVOB",       "URL": "https://news.google.com/rss/search?q=(%22ANOC%22+OR+%22FIVOB%22+OR+%22FISA%22+OR+%22FIMABE%22+OR+%22INTERPROVI%22)+Maroc&hl=fr&gl=MA&ceid=MA:fr",                    "Couverture": "Elevage MA — Federations interprofessionnelles betail"},
    {"Journal": "GNews — Lait Maroc",       "URL": "https://news.google.com/rss/search?q=(%22filiere+laitiere%22+OR+%22production+laitiere%22+OR+%22vache+laitiere%22+OR+%22centres+collecte+lait%22)+Maroc&hl=fr&gl=MA&ceid=MA:fr",  "Couverture": "Elevage MA — Filiere laitiere, vaches laitieres"},

    # ─── Google News RSS — Aquaculture (élevage & transformation) ──────────────
    {"Journal": "GNews — Aquaculture MA",   "URL": "https://news.google.com/rss/search?q=(%22aquaculture%22+OR+%22pisciculture%22+OR+%22conchyliculture%22+OR+%22ostreiculture%22+OR+%22ANDA%22)+Maroc&hl=fr&gl=MA&ceid=MA:fr", "Couverture": "Aquaculture MA — pisciculture, conchyliculture, ANDA"},
    {"Journal": "GNews — Peche Aquaculture","URL": "https://news.google.com/rss/search?q=(%22peche%22+OR+%22halieutique%22+OR+%22produits+de+la+mer%22+OR+%22Halieutis%22)+Maroc+aquaculture&hl=fr&gl=MA&ceid=MA:fr", "Couverture": "Aquaculture MA — pêche, halieutique, produits de la mer"},
    {"Journal": "GNews — Aquaculture Monde","URL": "https://news.google.com/rss/search?q=(%22aquaculture%22+OR+%22fish+farming%22+OR+%22seafood%22+OR+%22pisciculture%22)+(%22marche%22+OR+%22production%22+OR+%22durable%22+OR+%22market%22)&hl=fr&ceid=:fr", "Couverture": "Aquaculture intl — marché, production, seafood durable"},
    {"Journal": "GNews — Transformation Poisson","URL": "https://news.google.com/rss/search?q=(%22conserverie+de+poisson%22+OR+%22transformation+des+produits+de+la+mer%22+OR+%22farine+de+poisson%22+OR+%22surimi%22+OR+%22mareyage%22+OR+%22valorisation+halieutique%22)+Maroc&hl=fr&gl=MA&ceid=MA:fr", "Couverture": "Aquaculture MA — transformation, conserverie, mareyage"},

    # ─── WORLD - Environnement / Climat / Energie ──────────────────────────────
    # NB: retires car SPA/404/502 (0 article) : UNEP, WRI, TNFD, SBTi, CDP,
    # GHG Protocol, IRENA, Energy Voice, Basel Convention. Couverture climat/eau/
    # energie desormais via Google News RSS (section dediee ci-dessous).
    {"Journal": "Climate Home News", "URL": "https://www.climatechangenews.com/feed/", "Couverture": "Politique climatique"},
    {"Journal": "Carbon Brief", "URL": "https://www.carbonbrief.org/feed", "Couverture": "Science climatique, donnees"},

    # ─── WORLD - ESG / QSE / SST / QVT ─────────────────────────────────────────
    # NB: retires car SPA/404/403 (0 article) : OECD RBC, ISO (x4), EcoVadis,
    # GRI, IFRS (x2), ESG Investor, Env Finance, PRI, ILO, OSHA US, WHO, Sedex,
    # BRCGS, IFS Food, FSSC 22000. Normes/RSE/QSE/SST captees via Google News RSS.
    {"Journal": "UN Global Compact", "URL": "https://unglobalcompact.org/news", "Couverture": "RSE, droits humains, SDGs"},
    {"Journal": "FDA News", "URL": "https://www.fda.gov/news-events/fda-newsroom", "Couverture": "FDA, normes alimentaires/pharma"},
    {"Journal": "Fairtrade International", "URL": "https://www.fairtrade.net/news", "Couverture": "Fairtrade, commerce equitable"},

    # ═══ GOOGLE NEWS RSS — BACKFILL T4 (Environnement) & T5 (Normes) ═══════════
    # Remplace les sources institutionnelles SPA/injoignables par des flux RSS
    # fiables (testes). Themes forces via MEDIA_SCOUT_FORCED_SOURCE_THEMES.
    # ── T4 : Environnement, Eau & Energie ──
    {"Journal": "GNews — Eau Maroc",        "URL": "https://news.google.com/rss/search?q=(%22stress+hydrique%22+OR+%22barrage%22+OR+%22ressources+en+eau%22+OR+%22dessalement%22+OR+%22penurie+d%27eau%22)+Maroc&hl=fr&gl=MA&ceid=MA:fr", "Couverture": "T4 — Eau, barrages, stress hydrique Maroc"},
    {"Journal": "GNews — Energie Maroc",    "URL": "https://news.google.com/rss/search?q=(%22energie+renouvelable%22+OR+%22solaire%22+OR+%22eolien%22+OR+%22hydrogene+vert%22+OR+%22transition+energetique%22)+Maroc&hl=fr&gl=MA&ceid=MA:fr", "Couverture": "T4 — Energies renouvelables, transition energetique Maroc"},
    {"Journal": "GNews — Climat Maroc",     "URL": "https://news.google.com/rss/search?q=(%22changement+climatique%22+OR+%22secheresse%22+OR+%22climat%22+OR+%22carbone%22+OR+%22biodiversite%22)+Maroc+agriculture&hl=fr&gl=MA&ceid=MA:fr", "Couverture": "T4 — Climat, secheresse, carbone, biodiversite Maroc"},
    # ── T5 : Normes : ESG, QSE & SST ──
    {"Journal": "GNews — Normes RSE",       "URL": "https://news.google.com/rss/search?q=(%22CSRD%22+OR+%22reporting+extra-financier%22+OR+%22norme+ISO%22+OR+%22ISO+14001%22+OR+%22ISO+26000%22+OR+%22RSE%22)+entreprise&hl=fr&ceid=:fr", "Couverture": "T5 — RSE, CSRD, normes ISO, reporting durable"},
    {"Journal": "GNews — Securite alimentaire", "URL": "https://news.google.com/rss/search?q=(%22securite+alimentaire%22+OR+%22HACCP%22+OR+%22FSSC+22000%22+OR+%22IFS+Food%22+OR+%22BRCGS%22+OR+%22certification+halal%22)&hl=fr&ceid=:fr", "Couverture": "T5 — Securite alimentaire, HACCP, certifications agro"},
    {"Journal": "GNews — QSE SST Maroc",    "URL": "https://news.google.com/rss/search?q=(%22sante+securite+au+travail%22+OR+%22ISO+45001%22+OR+%22accident+du+travail%22+OR+%22QHSE%22+OR+%22audit+social%22)+Maroc&hl=fr&gl=MA&ceid=MA:fr", "Couverture": "T5 — QSE, SST, ISO 45001, audit social Maroc"},
    {"Journal": "GNews — Gouvernance ESG MA", "URL": "https://news.google.com/rss/search?q=(%22gouvernance%22+OR+%22ESG%22+OR+%22developpement+durable%22+OR+%22AMMC%22+OR+%22CGEM%22)+entreprise+Maroc&hl=fr&gl=MA&ceid=MA:fr", "Couverture": "T5 — Gouvernance, ESG, AMMC, CGEM Maroc"},

]

MEDIA_SCOUT_URLS = [source["URL"] for source in MEDIA_SCOUT_SOURCE_CATALOG]
MEDIA_SCOUT_URL_TO_NAME = {source["URL"]: source["Journal"] for source in MEDIA_SCOUT_SOURCE_CATALOG}

# Domaines mappes vers un theme prioritaire quand aucun mot-cle ne matche.
MEDIA_SCOUT_DOMAIN_THEME_OVERRIDES = {
    # ESG, QSE & SST (referentials, standards, health, safety)
    "globalreporting.org":            "ESG, QSE & SST",
    "efrag.org":                      "ESG, QSE & SST",
    "unglobalcompact.org":            "ESG, QSE & SST",
    "oecd.org":                       "ESG, QSE & SST",
    "iso.org":                        "ESG, QSE & SST",
    "afnor.org":                      "ESG, QSE & SST",
    "green-business.ec.europa.eu":    "ESG, QSE & SST",
    "ecovadis.com":                   "ESG, QSE & SST",
    "ifrs.org":                       "ESG, QSE & SST",
    "finance.ec.europa.eu":           "ESG, QSE & SST",
    "unpri.org":                      "ESG, QSE & SST",
    "ammc.ma":                        "ESG, QSE & SST",
    "esginvestor.net":                "ESG, QSE & SST",
    "environmental-finance.com":      "ESG, QSE & SST",
    "imanor.gov.ma":                  "ESG, QSE & SST",
    "sedex.com":                      "ESG, QSE & SST",
    "brcgs.com":                      "ESG, QSE & SST",
    "ifs-certification.com":          "ESG, QSE & SST",
    "fssc.com":                       "ESG, QSE & SST",
    "fairtrade.net":                  "ESG, QSE & SST",
    "osha.europa.eu":                 "ESG, QSE & SST",
    "osha.gov":                       "ESG, QSE & SST",
    "ilo.org":                        "ESG, QSE & SST",
    "who.int":                        "ESG, QSE & SST",
    "fda.gov":                        "ESG, QSE & SST",
    "efsa.europa.eu":                 "ESG, QSE & SST",
    "health.ec.europa.eu":            "ESG, QSE & SST",
    # Energie & Environnement (climat, eau, energie, biodiversite)
    "tnfd.global":                    "Environnement, Eau & Energie",
    "cdp.net":                        "Environnement, Eau & Energie",
    "sciencebasedtargets.org":        "Environnement, Eau & Energie",
    "ghgprotocol.org":                "Environnement, Eau & Energie",
    "basel.int":                      "Environnement, Eau & Energie",
    "unep.org":                       "Environnement, Eau & Energie",
    "wri.org":                        "Environnement, Eau & Energie",
    "carbonbrief.org":                "Environnement, Eau & Energie",
    "climatechangenews.com":          "Environnement, Eau & Energie",
    "irena.org":                      "Environnement, Eau & Energie",
    # Agrumes, Fruits rouges & Maraichage (production vegetale orientee LDA)
    # NB: fao.org, agriculture.gov.ma, onssa.gov.ma RETIRES car ils couvrent
    # autant T1 (vegetal) que T2 (elevage). Le scoring keywords decide
    # naturellement entre les 2 selon le contenu de l'article.
    "globalgap.org":                  "Agrumes, Fruits rouges & Maraichage",
    "food.ec.europa.eu":              "Agrumes, Fruits rouges & Maraichage",
    # Elevage (filieres animales : ovin, bovin, caprin, volaille)
    "poultryworld.net":               "Elevage (Ovins, Bovins, Caprins, Volailles)",
    # Produits laitiers & Epicerie fine (filiere laitiere + food industry global)
    "dairyreporter.com":              "Produits laitiers & Epicerie fine",
    "foodnavigator.com":              "Produits laitiers & Epicerie fine",
    # Concurrents LDA — sites corporates / pages presse (force T3)
    "nestle-mena.com":                "Produits laitiers & Epicerie fine",
    "groupe-bel.com":                 "Produits laitiers & Epicerie fine",
    "ribambel.com":                   "Produits laitiers & Epicerie fine",
    "aicha.com":                      "Produits laitiers & Epicerie fine",
    # NB: news.google.com PAS dans le domain override car les feeds GNews
    # couvrent plusieurs themes (T2 elevage ET T3 laitier). Le theme par feed
    # est gere via MEDIA_SCOUT_FORCED_SOURCE_THEMES (par nom de source).
}

MEDIA_SCOUT_THEME_RULES = {
    "Agrumes, Fruits rouges & Maraichage": {
        # THEME RECENTRE (v29) sur les 3 filieres d'EXPORT phares LDA :
        # Agrumes · Fruits rouges · Tomates cerises. Le maraichage generique
        # (courgette, poivron, salade, oignon...) et les termes vegetaux larges
        # ont ete retires pour ameliorer la pertinence des veilles.
        "strong": [
            # ── Agrumes ──
            "agrume", "agrumes", "orange", "oranges", "mandarine", "mandarines",
            "clementine", "clementines", "citron", "citrons", "pamplemousse", "pamplemousses",
            "pomelo", "lime", "kumquat", "bergamote", "filiere agrumes", "citrus",
            "citron vert", "navel", "valencia", "maroc late", "nadorcott", "afourer",
            "soft citrus", "maroc citrus",
            # ── Fruits rouges ──
            "fruits rouges", "fruit rouge", "fraise", "fraises", "framboise", "framboises",
            "myrtille", "myrtilles", "mure", "mures", "cassis", "groseille", "groseilles",
            "berries", "berry", "strawberry", "raspberry", "blueberry", "blackberry",
            "cranberry", "filiere fraise", "petits fruits", "soft fruit", "soft fruits",
            # ── Tomates cerises ──
            "tomate cerise", "tomates cerises", "tomate-cerise", "tomates-cerises",
            "cherry tomato", "cherry tomatoes", "tomate", "tomates", "tomato",
            "tomate ronde", "tomate grappe", "tomate cocktail", "filiere tomate",
        ],
        "medium": [
            # Production / conditionnement / export des 3 filieres ciblees
            "verger", "vergers", "plantation", "serre", "serres", "plein champ",
            "irrigation goutte a goutte", "irrigation localisee", "station de conditionnement",
            "conditionnement", "calibrage", "recolte", "cueillette", "campagne agrumes",
            "campagne d'export", "chaine du froid", "post-recolte", "post recolte",
            "stockage frigo", "exportation fruits", "exportation legumes", "agroexport",
            "primeurs", "morocco foodex", "moroccan exports", "eacce", "aspam", "apefel",
            "fruits et legumes", "felcoop", "interfel", "agriculture biologique",
        ],
        # Agriculture generique en WEAK : ne qualifie PAS seule pour T1 (le theme
        # exige desormais une culture cible OU un signal export) -> focus renforce.
        "weak": [
            "agri", "agriculture", "agricole", "production agricole", "production vegetale",
            "agronomie", "cooperative agricole", "exploitation agricole", "campagne agricole",
            "plan maroc vert", "generation green", "comader",
        ],
    },
    "Elevage (Ovins, Bovins, Caprins, Volailles)": {
        "strong": [
            # Filieres ciblees LDA : ovin, bovin, caprin, volaille
            "elevage", "eleveur", "eleveurs", "eleveuse",
            "ovin", "ovins", "ovine", "filiere ovine", "elevage ovin",
            "mouton", "moutons", "agneau", "agneaux", "brebis", "belier", "beliers",
            "bovin", "bovins", "bovine", "filiere bovine", "elevage bovin",
            "vache", "vaches", "veau", "veaux", "boeuf", "boeufs", "taureau", "genisse",
            "caprin", "caprins", "caprine", "filiere caprine", "elevage caprin",
            "chevre", "chevres", "chevreau", "bouc",
            "volaille", "volailles", "filiere avicole", "filiere volaille", "aviculture",
            "poulet", "poulets", "poule", "poules", "poule pondeuse", "poussin",
            "dinde", "dindes", "canard", "canards", "oie", "oies", "pintade", "caille",
            "broiler", "poultry",
            # Concepts elevage transversaux
            "betail", "cattle", "livestock", "viande", "viandes", "meat",
            "viande rouge", "viande blanche", "filiere viande", "boucherie",
            "abattoir", "abattoirs", "abattage", "slaughterhouse", "atelier de decoupe",
            "sante animale", "veterinaire", "veterinaires", "veterinary",
            "epizootie", "epizooties", "zoonose", "zoonoses", "antibioresistance",
            "engraissement", "production de viande", "alimentation animale",
            "feed industry", "fourrage", "fourrages", "ration", "ensilage",
            "race ovine", "race bovine", "race caprine", "race avicole",
            "interprovi", "anoc", "fivob",
            # Aïd Al-Adha / Fête du sacrifice (evenement majeur filiere ovine MA)
            "aid al adha", "aid el adha", "aid el kebir", "aid kebir",
            "aid adha", "aid al-adha", "aid al kebir",
            "eid al adha", "eid al-adha", "eid el kebir", "eid kebir",
            "fete du sacrifice", "fête du sacrifice", "sacrifice du mouton",
            "tabaski", "marche ovin", "marche aux moutons", "marche aux bestiaux",
            "marche du betail", "souk al kbach", "souk kbach", "souk el kbach",
            # Filiere viande / abattage Maroc
            "sonacos", "filiere des viandes", "viande ovine",
            "viande bovine", "viande caprine", "viande avicole",
        ],
        "medium": [
            "animal", "animale", "animaux", "troupeau", "troupeaux", "cheptel",
            "boucher", "boucherie", "feed", "ferme d'elevage", "exploitation d'elevage",
            "production animale", "filiere animale",
        ],
        "weak": [
            "race animale",
        ],
    },
    "Aquaculture (elevage et transformation)": {
        # Filiere aquacole LDA : elevage aquatique + transformation / valorisation.
        "strong": [
            # -- Elevage aquatique --
            "aquaculture", "aquacole", "aquacoles", "filiere aquacole", "ferme aquacole",
            "aquaculture marine", "pisciculture", "piscicole", "elevage piscicole",
            "ferme piscicole", "elevage de poissons", "poisson d'elevage", "poissons d'elevage",
            "fish farming", "salmoniculture", "conchyliculture", "ostreiculture",
            "mytiliculture", "algoculture", "ecloserie", "ecloseries", "alevin", "alevins",
            "aliment aquacole", "spiruline", "microalgue", "microalgues", "macroalgue",
            # -- Especes d'elevage (non ambigues) --
            "huitre", "huitres", "moule", "moules", "crevette", "crevettes",
            "daurade", "dorade", "tilapia", "truite", "saumon d'elevage", "loup de mer",
            # -- Transformation / valorisation des produits de la mer --
            "transformation des produits de la mer", "conserverie de poisson",
            "conserve de poisson", "conserves de poisson", "farine de poisson",
            "huile de poisson", "surimi", "mareyage", "mareyeur", "filet de poisson",
            "valorisation halieutique", "industrie halieutique",
            # -- Peche / halieutique (contexte marin cible) --
            "halieutique", "produits halieutiques", "produits de la mer",
            "peche maritime", "peche cotiere", "peche artisanale",
            # -- Institutions / evenements Maroc --
            "anda", "inrh", "office national des peches", "halieutis",
        ],
        "medium": [
            "poisson", "poissons", "fruits de mer", "algue", "algues",
            "onp", "criee", "port de peche", "aquafeed",
        ],
        "weak": [
            "aquaculteur", "aquaculteurs", "pisciculteur", "pisciculteurs",
        ],
    },
    "Produits laitiers & Epicerie fine": {
        "strong": [
            # Produits laitiers (orientation transformation/distribution, vs Elevage = animal)
            "produits laitiers", "produit laitier", "dairy", "dairy products",
            "lait UHT", "lait pasteurise", "lait infantile", "formule infantile",
            "infant formula", "lait en poudre", "milk powder", "lait fermente",
            "lait demi-ecreme", "lait ecreme", "lait entier", "lactose", "sans lactose",
            "fromage", "fromages", "fromagerie", "fromagerie artisanale", "cheese",
            "fromage frais", "yaourt", "yaourts", "yogurt", "yogourt", "yoghurt",
            "kefir", "skyr", "fromage blanc", "beurre", "creme", "creme fraiche",
            "creme dessert", "lait infantile en poudre",
            "centrale danone", "danone maroc", "danone", "lactalis", "lactel",
            "yoplait", "savencia", "savencia fromage", "savencia dairy",
            "copag", "jaouda", "safilait", "jibal", "groupe bel", "vache qui rit",
            "lavachequirit", "kiri ", "president fromage", "nestle maroc", "nido ",
            "laiterie", "laiteries", "industrie laitiere", "transformation laitiere",
            "filiere laitiere", "production laitiere",
            # Epicerie fine
            "epicerie fine", "epicerie", "deli", "delicatessen", "fine food",
            "gourmet food", "produits gourmets", "produits du terroir", "specialites alimentaires",
            "confiserie", "chocolaterie", "biscuiterie", "miel", "confiture", "marmelade",
            "huile d'olive", "huile vierge", "huiles fines", "condiment", "condiments",
            "epices", "epices fines", "olives en saumure", "olive de table",
            "conserve", "conserves", "conserverie", "saumure", "marinade",
            "produits transformes", "ingredients premium",
            # Concurrents LDA - epicerie fine (marques specifiques)
            "aicha conserve", "aicha tomate", "lesieur cristal", "lesieur ",
            "zouitina", "diana holding", "caracterre", "cartier saada",
            "sovena", "oliveira da serra", "puget huile", "puget olive",
            "bonne maman", "andros confiture", "andros ", "st dalfour",
            "st. dalfour", "hero group", "hero confiture", "beldimarket",
            "marjane gourmet", "carrefour selection",
            # Distribution alimentaire / GMS (oriente vers epicerie/laitier)
            "supermarche", "hypermarche", "grande surface", "moyenne surface",
            "gms", "grande distribution", "distribution alimentaire", "retail alimentaire",
            "fmcg", "produits de grande consommation", "ultra-frais", "rayon frais",
            "rayon laitier", "rayon cremerie", "lineaire", "lineaire alimentaire",
            "marque distributeur", "mdd", "private label", "private brand", "marque propre",
            "carrefour", "auchan", "marjane", "label vie", "leclerc", "casino",
            "lidl", "aldi", "intermarche", "metro cash", "monoprix", "franprix",
            "drive alimentaire", "click and collect", "ecommerce alimentaire",
            "centrale d'achat", "centrale achat", "category management",
            "category manager", "merchandising", "tete de gondole",
            "trade marketing", "shopper marketing", "interprolait", "fimalait",
        ],
        "medium": [
            "distribution", "distributeur", "retail", "retailer", "enseigne",
            "magasin", "consommateur", "consommation", "alimentaire", "agroalimentaire",
            "food industry", "food trends", "food retail", "panier moyen",
            "promotion", "promo", "soldes", "marketing au point de vente",
            "implantation magasin", "ouverture magasin", "fermeture magasin",
            "expansion magasin", "head of category", "buying",
            "achat retail", "sourcing produits", "lait", "laitier", "laitiere",
            "oeuf", "oeufs", "egg", "lactation",
        ],
        "weak": [
            "vente", "achat",
        ],
    },
    "Environnement, Eau & Energie": {
        "strong": [
            # Climat / Environnement
            "changement climatique", "climate change", "biodiversite", "pollution",
            "dechets", "recyclage", "neutralite carbone", "rechauffement climatique",
            "deforestation", "qualite de l'air", "bilan carbone", "empreinte carbone",
            "zero dechet", "economie circulaire", "accord de paris", "cop28", "cop29", "cop30",
            "perte de biodiversite", "espece menacee", "extinction", "desertification",
            "microplastique", "pollution plastique", "gaz a effet de serre",
            "transition ecologique", "neutralite climatique", "net zero",
            "carbon neutral", "economie verte", "green economy",
            "pollution atmospherique", "pollution marine", "pollution des sols",
            "rechauffement", "marche du carbone", "credit carbone",
            "scope 1", "scope 2", "scope 3",
            # Energie / Transition energetique
            "transition energetique", "efficacite energetique", "energies renouvelables",
            "renewable energy", "hydrogene vert", "panneau solaire", "panneaux solaires",
            "eolienne", "eoliennes", "photovoltaique", "mix energetique", "stockage energie",
            "energie solaire", "energie eolienne", "energie propre", "clean energy",
            "independance energetique", "souverainete energetique", "decarbonation energetique",
            "reseau electrique intelligent", "smart grid", "centrale solaire",
            "parc solaire", "parc eolien", "centrale eolienne", "energie hydraulique",
            "hydroelectricite", "puissance renouvelable installee", "energy transition",
            "green hydrogen", "solar farm", "wind farm",
            # Eau / Hydrique
            "stress hydrique", "ressources en eau", "dessalement", "barrage", "secheresse",
            "nappe phreatique", "water scarcity", "gestion de l'eau", "eau potable",
            "assainissement", "qualite de l'eau", "penurie d'eau", "gestion hydraulique",
            "ressource hydrique", "eau souterraine", "retenue d'eau", "transfert d'eau",
            "bassin hydraulique", "amenagement hydraulique", "plan national de l'eau",
            "crise hydrique", "deficit hydrique", "mobilisation de l'eau",
            "retenue collinaire", "transfert inter-bassins", "programme eau",
            "penurie eau", "acces a l'eau potable", "water stress", "drinking water",
        ],
        "medium": [
            "environnement", "climat", "carbone", "co2", "ges", "emissions", "nature",
            "waste", "foret", "ecosysteme", "protection de l'environnement",
            "impact environnemental", "plastique", "methane", "erosion", "sol",
            "faune", "flore", "reserve naturelle", "parc national", "ecologie",
            "compostage", "tri selectif", "valorisation dechets", "polluant",
            "emission carbone", "compensation carbone", "reforestation", "reboisement",
            "decharge", "enfouissement", "collecte des dechets", "traitement des dechets",
            "etude d impact", "normes environnementales", "audit environnemental",
            "reserve de biosphere", "zone protegee", "espece", "milieu naturel",
            "programme forestier", "hceflcd",
            "energie", "energetique", "electricite", "renouvelable", "solaire", "hydrogene",
            "energy", "solar", "wind", "centrale electrique", "puissance installee",
            "capacite installee", "kwh", "mwh", "gwh", "twh", "biogaz", "biomasse",
            "petrole", "gaz naturel", "charbon", "decarbonation", "electrification",
            "interconnexion electrique", "reseau de transport", "tarif electricite",
            "facture energetique", "consommation energetique", "production electrique",
            "offshore", "onshore", "watt", "megawatt", "gigawatt",
            "masen", "noor", "iresen", "aderee",
            "combustible", "carburant", "fossile", "nucleaire", "thermique",
            "reseau electrique", "infrastructure energetique", "power",
            "hydrique", "irrigation", "nappe", "drought", "inondation", "precipitation",
            "fleuve", "riviere", "lac", "bassin versant", "aquifere", "pluvial",
            "debordement", "crue", "hydraulique", "oued", "ressource en eau",
            "approvisionnement en eau", "distribution d'eau", "traitement de l'eau",
            "epuration", "debit", "pluviometrie", "reseau d'eau", "branchement eau",
            "desserte en eau", "pompage", "station d'epuration", "station de traitement",
            "onee", "onep", "amenagement hydro", "water management",
        ],
        "weak": [
            "ecologique", "vert", "verdure", "eau", "water", "pluie", "hydrologie", "pluies",
            "kilowatt", "turbine", "generateur", "raccordement electrique",
            "compteur", "voltage",
        ],
    },
    "ESG, QSE & SST": {
        "strong": [
            # RSE / ESG
            "rse", "csr", "esg", "responsabilite societale", "responsabilite sociale",
            "social responsibility", "developpement durable", "sustainable development",
            "rapport rse", "rapport extra-financier", "esg report", "sustainability report",
            "materialite", "materiality", "double materialite", "double materiality",
            "strategie rse", "csr strategy", "esg strategy", "engagement rse",
            "csr commitment", "performance esg", "esg performance", "notation esg",
            "esg rating", "indice esg", "esg index", "label rse", "csr label",
            "objectifs odd", "sdg", "sustainable development goals",
            "global compact", "pacte mondial", "ungc", "gri", "csrd",
            "esrs", "efrag", "issb", "ifrs s1", "ifrs s2", "sasb", "ghg protocol",
            "sbti", "tnfd", "tcfd", "cdp", "b corp", "ecovadis", "devoir de vigilance",
            "csddd", "taxonomie europeenne", "sfdr", "achats responsables",
            "supply chain durable", "labellisation rse", "reporting durabilite",
            "rapport de durabilite", "due diligence",
            # Normes ISO / QSE
            "iso 26000", "iso 14001", "iso 9001", "iso 45001", "iso 50001",
            "iso 22000", "iso 27001", "iso 31000", "iso 37001", "iso 37301",
            "iso 14064", "iso 14067", "qse", "qualite securite environnement",
            "smqse", "haccp", "fssc 22000",
            # Referentiels supply chain / agroalimentaire
            "globalgap", "global gap", "globalg.a.p", "smeta", "sedex audit",
            "brc", "brcgs", "ifs food", "ifs broker", "halal", "casher", "kosher",
            "fairtrade", "rainforest alliance", "fsc certification", "rspo",
            # Sante / SST
            "sante securite au travail", "occupational health and safety", "sst",
            "accident du travail", "work accident", "maladie professionnelle",
            "occupational disease", "prevention des risques", "risk prevention",
            "document unique", "duer", "duerp", "chsct", "csst",
            "harcelement moral", "harcelement sexuel", "harassment",
            "stress au travail", "workplace stress", "ergonomie", "ergonomics",
            "psychosociaux", "risques psychosociaux", "rps", "medecine du travail",
            "inrs", "hygiene au travail",
        ],
        "medium": [
            # ESG
            "gouvernance", "governance", "ethique", "ethics", "transparence", "transparency",
            "parties prenantes", "stakeholders", "impact social", "social impact",
            "impact environnemental", "environmental impact", "diversite", "diversity",
            "inclusion", "parite", "gender parity", "droits humains", "human rights",
            "entreprise responsable", "engagement societal", "engagement social",
            # QSE / SST
            "securite", "safety", "sante publique", "sante au travail", "salarie",
            "employee", "personnel", "staff", "rh", "ressources humaines",
            "human resources", "prevention", "prevention sante", "absenteeism",
            "absenteisme", "turn-over", "turnover", "epi", "equipement de protection",
            "certification qualite", "audit qualite", "audit social",
        ],
        "weak": [
            "durable", "responsable", "sante",
        ],
    },
}

# ─── Veille Classification Rules ───────────────────────────────────────────────
# Veille Informative = catch-all default (no specific rules).
MEDIA_SCOUT_VEILLE_RULES = {
    "Veille Reglementaire": {
        "strong": [
            # Lois & textes officiels
            "loi", "decret", "reglement", "directive", "arrete", "ordonnance",
            "projet de loi", "proposition de loi", "transposition", "parlement",
            "adoption parlementaire", "promulgation", "journal officiel",
            "bulletin officiel", "conseil de gouvernement", "conseil des ministres",
            "regulation", "regulatory", "rulemaking", "compliance", "conformite",
            "non-conformite", "sanction", "amende", "penalite", "fine",
            "court ruling", "decision de justice", "jurisprudence", "tribunal",
            "loi de finances", "loi cadre", "code de l'environnement",
            "code du travail", "code de commerce", "code general des impots",
            "regulator", "autorite de regulation", "exigence reglementaire",
            "obligation legale", "obligation reglementaire",
            # Normes ISO & cadres internationaux
            "norme iso", "iso 9001", "iso 14001", "iso 14064", "iso 14067",
            "iso 22000", "iso 26000", "iso 27001", "iso 31000", "iso 45001",
            "iso 50001", "iso 37001", "iso 37301", "fssc 22000", "haccp",
            "csrd", "esrs", "sfdr", "csddd", "devoir de vigilance",
            "taxonomie europeenne", "taxonomy", "rgpd", "gdpr",
            "afnor", "imanor", "norme nm", "norme marocaine",
            # Normes & referentiels agroalimentaires / supply chain
            "globalgap", "global gap", "globalg.a.p", "smeta", "sedex",
            "brc", "brcgs", "ifs", "ifs food", "ifs broker", "ifs logistic",
            "halal", "casher", "kosher", "bio", "agriculture biologique",
            "fairtrade", "rainforest alliance", "fsc certification", "rspo",
            "codex alimentarius", "codex", "label rouge", "aoc", "aop",
            "igp", "stg",
            # Sante / pharma / food regulators
            "fda approval", "fda clearance", "fda warning", "fda recall",
            "ema approval", "ammc circulaire", "ammc visa",
            "onssa", "efsa", "dg sante", "who recommendation",
            # Actes de mise a jour de normes
            "nouvelle norme", "mise a jour de la norme", "revision de la norme",
            "revision norme", "publication norme", "nouvelle version iso",
            "nouvelle edition", "norme revisee",
            "standards update", "standard revision", "new standard",
        ],
        "medium": [
            "legal", "juridique", "reglementaire", "obligation", "exigence",
            "requirement", "interdiction", "autorisation", "agrement",
            "certification", "certifie", "certifiee", "label", "labellisation",
            "cadre legal", "cadre juridique", "cadre reglementaire",
            "ratification", "convention internationale", "accord international",
            "regle", "audit reglementaire", "audit de conformite",
            "rappel produit", "recall", "homologation", "agrement sanitaire",
        ],
        "weak": [
            "code", "norme", "standard", "referentiel", "normative",
        ],
    },
    "Veille Evenementielle": {
        "strong": [
            "salon", "salon international", "conference", "sommet", "summit",
            "congres", "forum", "journee mondiale", "journee internationale",
            "world day", "international day", "evenement", "cop28", "cop29", "cop30",
            "exposition", "foire", "foire internationale", "atelier",
            "workshop", "webinaire", "webinar", "edition annuelle",
            "rendez-vous annuel", "rassemblement", "rencontre internationale",
            "rencontres", "convention", "ceremonie", "inauguration",
            "table ronde", "panel discussion", "seminaire", "festival",
            "trade show", "expo", "world expo", "davos", "world economic forum",
            "wef annual meeting", "cop", "conference des parties",
        ],
        "medium": [
            "organise", "tenir", "accueille", "se tiendra", "se tient",
            "rdv", "rencontre", "lancement officiel", "inaugure", "ouvre ses portes",
            "cloture", "edition", "manifestation",
        ],
        "weak": [
            "event",
        ],
    },
    "Veille Concurrentielle": {
        "strong": [
            "levee de fonds", "fundraising", "tour de financement", "serie a",
            "serie b", "serie c", "fusion", "acquisition", "merger", "m&a",
            "rachat", "cession", "prise de participation", "joint venture",
            "alliance strategique", "partenariat strategique", "partnership",
            "introduction en bourse", "ipo", "cotation",
            "resultats financiers", "resultats annuels", "resultats semestriels",
            "resultats trimestriels", "chiffre d'affaires", "ca annuel", "ebitda",
            "benefice net", "marge operationnelle", "plan strategique",
            "feuille de route", "roadmap", "lance un produit", "lance une offre",
            "lance une nouvelle", "lancement officiel", "lancement de",
            "nouveau produit", "nouvelle offre",
            "ceo", "pdg", "directeur general", "presidente directrice generale",
            "nomination", "nomme", "nommee", "nouveau directeur",
            "restructuration", "plan social", "plan de depart", "layoff",
            "licenciement", "fermeture de site", "expansion", "investissement de",
            "ouvre une usine", "ouvre un site", "contrat de",
            "appel d'offres remporte", "remporte un contrat", "decroche un contrat",
            "consortium", "marche public",
            "lancement de marque", "rebranding", "relance",
            # ── Concurrents LDA — Produits laitiers (Maroc + International) ────
            "centrale danone", "danone maroc", "danone", "copag", "jaouda",
            "safilait", "jibal", "groupe bel", "vache qui rit", "lavachequirit",
            "kiri ", "president fromage", "lactel", "lactalis", "savencia",
            "savencia fromage", "savencia dairy", "nestle maroc", "nestle ",
            "nido ", "label vie", "labelvie", "bim maroc",
            # ── Concurrents LDA — Epicerie fine (Maroc + International) ────────
            "aicha conserve", "aicha tomate", "lesieur cristal", "lesieur ",
            "zouitina", "diana holding", "caracterre", "cartier saada",
            "sovena", "oliveira da serra", "puget huile", "puget olive",
            "bonne maman", "andros confiture", "andros ", "st dalfour",
            "st. dalfour", "hero group", "hero confiture", "beldimarket",
            "marjane gourmet", "carrefour selection", "marjane mdd",
        ],
        "medium": [
            "entreprise", "groupe", "societe", "company", "filiale", "subsidiary",
            "marche", "client", "produit", "service", "offre", "strategie",
            "dirigeant", "executive", "managing director", "nominations",
        ],
        "weak": [
            "business",
        ],
    },
}

# Sources strictement mono-thematiques : fallback quand aucun mot-cle ne matche.
# Critere d'inclusion : la source ne couvre QU'UN seul theme (organisme dedie ou URL specialisee).
MEDIA_SCOUT_FORCED_SOURCE_THEMES = {
    # ── MAROC (sources qui marchent uniquement) ─────────────────────────────
    # NB : AgriMaroc / ONSSA / FAO ne sont PAS forces car ils couvrent a la fois
    # T1 (production vegetale) ET T2 (elevage). Le scoring keywords decide.
    "Le Vert":                          "Environnement, Eau & Energie",
    "Le Vert - Developpement Durable":  "Environnement, Eau & Energie",
    "MAP Ecology":                      "Environnement, Eau & Energie",
    "Ministere Equipement et Eau":      "Environnement, Eau & Energie",

    # ── UE - Reglementation alimentaire (impact direct exports Maroc) ─────
    "EFSA":                             "ESG, QSE & SST",
    "DG SANTE EU - Food":               "ESG, QSE & SST",

    # ── UE - ESG / QSE / SST (sources qui marchent) ──────────────────────
    "AFNOR Actualites":                      "ESG, QSE & SST",
    "EU EMAS":                               "ESG, QSE & SST",
    "EFRAG":                                 "ESG, QSE & SST",

    # ── UE - Food industry (couverture globale, pas locale) ───────────────
    "Food Navigator":                   "Produits laitiers & Epicerie fine",

    # ── CONCURRENTS LDA — Google News RSS aggregated feeds (forces T3)
    "GNews — Centrale Danone":          "Produits laitiers & Epicerie fine",
    "GNews — COPAG Jaouda":             "Produits laitiers & Epicerie fine",
    "GNews — Lesieur Cristal":          "Produits laitiers & Epicerie fine",
    "GNews — Marjane Maroc":            "Produits laitiers & Epicerie fine",
    "GNews — Bel Maroc":                "Produits laitiers & Epicerie fine",
    "GNews — Lactalis":                 "Produits laitiers & Epicerie fine",
    "GNews — Savencia":                 "Produits laitiers & Epicerie fine",
    "GNews — Bonne Maman Andros":       "Produits laitiers & Epicerie fine",
    "GNews — Hero St Dalfour":          "Produits laitiers & Epicerie fine",
    "GNews — Olive MA":                 "Produits laitiers & Epicerie fine",
    "GNews — Sovena Puget":             "Produits laitiers & Epicerie fine",
    # ── VEILLE CONCURRENTIELLE T3 — Intelligence par categorie (forces T3) ──
    # (topic-scopes sur le laitier/epicerie -> forcage T3 sans bruit)
    "GNews — Presse éco MA":            "Produits laitiers & Epicerie fine",
    "GNews — Lait International":        "Produits laitiers & Epicerie fine",
    "GNews — FMCG Retail":              "Produits laitiers & Epicerie fine",
    "GNews — Nutrition Santé":          "Produits laitiers & Epicerie fine",
    "GNews — Nouveautés Premium":       "Produits laitiers & Epicerie fine",
    # ── VEILLE CONCURRENTIELLE T1 — Agrumes / Fruits rouges / Tomates cerises ──
    "GNews — Agrumes Export MA":        "Agrumes, Fruits rouges & Maraichage",
    "GNews — Marché Agrumes Intl":      "Agrumes, Fruits rouges & Maraichage",
    "GNews — Marché Fruits Rouges":     "Agrumes, Fruits rouges & Maraichage",
    "GNews — Concurrents Primeurs":     "Agrumes, Fruits rouges & Maraichage",
    "GNews — Production Fruits MA":     "Agrumes, Fruits rouges & Maraichage",
    "GNews — Innovations Fruits":       "Agrumes, Fruits rouges & Maraichage",
    # ── PRESSE ÉCONOMIQUE MAROC RSS (PAS forces — classification naturelle)
    # NB: EcoActu / Aujourd'hui Maroc / Challenge / Financial Afrik / La Vie Éco
    # / Le Matin ne sont PAS dans ce dict -> theme decide par keywords + LLM

    # ── WORLD - Agriculture (production vegetale OU elevage selon contenu) ─
    # FAO Newsroom : non force, couvre veg + elevage -> scoring decide

    # ── WORLD - Elevage / Laitier ─────────────────────────────────────────
    "DairyReporter":                    "Produits laitiers & Epicerie fine",
    # ── MAROC - Elevage (sources dediees) ─────────────────────────────────
    "AgriMaroc Élevage":                "Elevage (Ovins, Bovins, Caprins, Volailles)",
    # ── Google News RSS - Elevage MA (forces T2 — betail strict)
    "GNews — Bétail MA":                "Elevage (Ovins, Bovins, Caprins, Volailles)",
    "GNews — Aviculture MA":            "Elevage (Ovins, Bovins, Caprins, Volailles)",
    "GNews — Viande MA":                "Elevage (Ovins, Bovins, Caprins, Volailles)",
    "GNews — ANOC FIVOB":               "Elevage (Ovins, Bovins, Caprins, Volailles)",
    "GNews — Lait Maroc":               "Elevage (Ovins, Bovins, Caprins, Volailles)",
    # ── Google News RSS - Aquaculture (forces vers le theme dedie) ────────
    "GNews — Aquaculture MA":           "Aquaculture (elevage et transformation)",
    "GNews — Peche Aquaculture":        "Aquaculture (elevage et transformation)",
    "GNews — Aquaculture Monde":        "Aquaculture (elevage et transformation)",
    "GNews — Transformation Poisson":   "Aquaculture (elevage et transformation)",

    # ── WORLD - Environnement / Climat / Energie (sources qui marchent) ───
    "Climate Home News":                "Environnement, Eau & Energie",
    "Carbon Brief":                     "Environnement, Eau & Energie",

    # ── WORLD - ESG / QSE / SST (sources qui marchent) ────────────────────
    "UN Global Compact":                "ESG, QSE & SST",
    "FDA News":                         "ESG, QSE & SST",
    "Fairtrade International":          "ESG, QSE & SST",

    # ── Google News RSS - BACKFILL T4 Environnement (forces T4) ───────────
    "GNews — Eau Maroc":                "Environnement, Eau & Energie",
    "GNews — Energie Maroc":            "Environnement, Eau & Energie",
    "GNews — Climat Maroc":             "Environnement, Eau & Energie",
    # ── Google News RSS - BACKFILL T5 Normes/ESG/QSE/SST (forces T5) ──────
    "GNews — Normes RSE":               "ESG, QSE & SST",
    "GNews — Securite alimentaire":     "ESG, QSE & SST",
    "GNews — QSE SST Maroc":            "ESG, QSE & SST",
    "GNews — Gouvernance ESG MA":       "ESG, QSE & SST",

}

# Approche : on collecte la data depuis toutes les sources, puis on categorise chaque
# article par theme + veille via _assign_media_theme / _assign_media_veille (keyword scoring).
# Plus de mapping source -> veille a priori : chaque article est juge sur son contenu.


# Pays d'origine de chaque source (pour filtrage fin)
MEDIA_SCOUT_SOURCE_ORIGINS = {
    # Maroc
    "AgriMaroc": "Maroc",
    "AgriMaroc Élevage": "Maroc",
    "FNH - Finances News Hebdo": "Maroc",
    "CGEM": "Maroc",
    "Le Vert": "Maroc",
    "Le Vert - Developpement Durable": "Maroc",
    "Medias24 - Environnement": "Maroc",
    "Medias24 - Entreprises": "Maroc",
    "MAP Ecology": "Maroc",
    "Ministere Transition Energetique": "Maroc",
    "Ministere Equipement et Eau": "Maroc",
    "Departement Environnement": "Maroc",
    "Ministere Agriculture": "Maroc",
    "Ministere Sante": "Maroc",
    "ONSSA": "Maroc",
    "IMANOR": "Maroc",
    "AMMC": "Maroc",
    "Aïcha": "Maroc",
    # Presse economique Maroc (RSS)
    "EcoActu": "Maroc",
    "Aujourd'hui Maroc": "Maroc",

    # France (couvertures UE / globales uniquement)
    "AFNOR Actualites": "France",
    # Presse fruits & legumes / agroalimentaire
    "FreshPlaza FR": "France",
    "Agro-media": "France",
    "FruitNet": "Royaume-Uni",
    "FreshFruitPortal": "International",
    # Google News RSS (multi-source aggregators) -> zone "International"
    "GNews — Centrale Danone": "International",
    "GNews — COPAG Jaouda": "International",
    "GNews — Lesieur Cristal": "International",
    "GNews — Marjane Maroc": "International",
    "GNews — Bel Maroc": "International",
    "GNews — Lactalis": "International",
    "GNews — Savencia": "International",
    "GNews — Bonne Maman Andros": "International",
    "GNews — Hero St Dalfour": "International",
    "GNews — Olive MA": "International",
    "GNews — Sovena Puget": "International",
    # Google News RSS - Elevage MA (aggregators - betail strict)
    "GNews — Bétail MA": "International",
    "GNews — Aviculture MA": "International",
    "GNews — Viande MA": "International",
    "GNews — ANOC FIVOB": "International",
    "GNews — Lait Maroc": "International",
    "GNews — Aquaculture MA": "Maroc",
    "GNews — Peche Aquaculture": "Maroc",
    "GNews — Aquaculture Monde": "International",
    "GNews — Transformation Poisson": "Maroc",
    # Veille Concurrentielle T3 — intelligence par categorie
    "GNews — Presse éco MA": "Maroc",
    "La Vie Éco": "Maroc",
    "Le Matin": "Maroc",
    "GNews — Lait International": "International",
    "GNews — FMCG Retail": "International",
    "GNews — Nutrition Santé": "International",
    "GNews — Nouveautés Premium": "International",
    # Veille Concurrentielle T1 — Agrumes / Fruits rouges / Tomates cerises
    "GNews — Agrumes Export MA": "Maroc",
    "GNews — Marché Agrumes Intl": "International",
    "GNews — Marché Fruits Rouges": "International",
    "GNews — Concurrents Primeurs": "International",
    "GNews — Production Fruits MA": "Maroc",
    "GNews — Innovations Fruits": "International",
    # Google News RSS - BACKFILL T4 Environnement + T5 Normes
    "GNews — Eau Maroc": "International",
    "GNews — Energie Maroc": "International",
    "GNews — Climat Maroc": "International",
    "GNews — Normes RSE": "International",
    "GNews — Securite alimentaire": "International",
    "GNews — QSE SST Maroc": "International",
    "GNews — Gouvernance ESG MA": "International",
    "Financial Afrik": "International",

    # UE (institutions europeennes)
    "EFSA": "UE",
    "DG SANTE EU - Food": "UE",
    "EU Health News": "UE",
    "EU EMAS": "UE",
    "EFRAG": "UE",
    "European Commission Sustainable Finance": "UE",
    "EU-OSHA": "UE",

    # Royaume-Uni (couvertures globales uniquement)
    "Food Navigator": "Royaume-Uni",
    "Climate Home News": "Royaume-Uni",
    "Carbon Brief": "Royaume-Uni",
    "Energy Voice": "Royaume-Uni",
    "DairyReporter": "Royaume-Uni",
    "BRCGS": "Royaume-Uni",
    "Sedex (SMETA)": "Royaume-Uni",
    "CDP": "Royaume-Uni",
    "TNFD": "Royaume-Uni",

    # USA (couvertures globales / régulations alimentaires impactant exports Maroc)
    "FDA News": "USA",
    "OSHA US": "USA",
    "WRI": "USA",

    # Allemagne
    "IFS Food": "Allemagne",
    "GlobalG.A.P.": "Allemagne",
    "Fairtrade International": "Allemagne",

    # Pays-Bas
    "Poultry World": "Pays-Bas",
    "FSSC 22000": "Pays-Bas",

    # International / Onusien (HQ Geneve, NY, Paris, etc.)
    "ISO News": "International",
    "ISO 26000": "International",
    "ISO 14001": "International",
    "ISO 14000 Family": "International",
    "FAO Newsroom": "International",
    "UN Global Compact": "International",
    "OECD RBC": "International",
    "WHO News": "International",
    "Codex Alimentarius": "International",
    "ILO Safework": "International",
    "UNEP": "International",
    "IRENA": "International",
    "Basel Convention": "International",
    "SBTi": "International",
    "GHG Protocol": "International",
    "GRI": "International",
    "IFRS / ISSB": "International",
    "IFRS / SASB": "International",
    "PRI": "International",
    "ESG Investor": "International",
    "Environmental Finance": "International",
}


def get_source_origin(journal: str) -> str:
    """Retourne le pays d'origine d'une source. Defaut: 'Autre'."""
    return MEDIA_SCOUT_SOURCE_ORIGINS.get(journal, "Autre")


# Zone geographique de chaque source : MAROC | EU | WORLD
MEDIA_SCOUT_SOURCE_ZONES = {
    # MAROC
    "AgriMaroc":                              "MAROC",
    "AgriMaroc Élevage":                      "MAROC",
    "FNH - Finances News Hebdo":              "MAROC",
    "CGEM":                                   "MAROC",
    "Le Vert":                                "MAROC",
    "Le Vert - Developpement Durable":        "MAROC",
    "Medias24 - Environnement":               "MAROC",
    "Medias24 - Entreprises":                 "MAROC",
    "MAP Ecology":                            "MAROC",
    "Ministere Transition Energetique":       "MAROC",
    "Ministere Equipement et Eau":            "MAROC",
    "Departement Environnement":              "MAROC",
    "Ministere Agriculture":                  "MAROC",
    "Ministere Sante":                        "MAROC",
    "ONSSA":                                  "MAROC",
    "IMANOR":                                 "MAROC",
    "AMMC":                                   "MAROC",
    "Aïcha":                                  "MAROC",
    # Presse economique Maroc (RSS)
    "EcoActu":                                "MAROC",
    "Aujourd'hui Maroc":                      "MAROC",

    # EU (couvertures globales / directives impactant Maroc)
    "EFSA":                                   "EU",
    "DG SANTE EU - Food":                     "EU",
    "AFNOR Actualites":                       "EU",
    # Presse fruits & legumes / agroalimentaire
    "FreshPlaza FR":                          "EU",
    "Agro-media":                             "EU",
    "FruitNet":                               "EU",
    "FreshFruitPortal":                       "WORLD",
    # Google News RSS aggregators (multi-source) -> tagged WORLD
    "GNews — Centrale Danone":                "WORLD",
    "GNews — COPAG Jaouda":                   "WORLD",
    "GNews — Lesieur Cristal":                "WORLD",
    "GNews — Marjane Maroc":                  "WORLD",
    "GNews — Bel Maroc":                      "WORLD",
    "GNews — Lactalis":                       "WORLD",
    "GNews — Savencia":                       "WORLD",
    "GNews — Bonne Maman Andros":             "WORLD",
    "GNews — Hero St Dalfour":                "WORLD",
    "GNews — Olive MA":                       "WORLD",
    "GNews — Sovena Puget":                   "WORLD",
    # Veille Concurrentielle T3 — intelligence par categorie
    "GNews — Presse éco MA":                  "MAROC",
    "La Vie Éco":                             "MAROC",
    "Le Matin":                               "MAROC",
    "GNews — Lait International":              "WORLD",
    "GNews — FMCG Retail":                    "WORLD",
    "GNews — Nutrition Santé":                "WORLD",
    "GNews — Nouveautés Premium":             "WORLD",
    # Veille Concurrentielle T1 — Agrumes / Fruits rouges / Tomates cerises
    "GNews — Agrumes Export MA":              "MAROC",
    "GNews — Marché Agrumes Intl":            "WORLD",
    "GNews — Marché Fruits Rouges":           "WORLD",
    "GNews — Concurrents Primeurs":           "WORLD",
    "GNews — Production Fruits MA":           "MAROC",
    "GNews — Innovations Fruits":             "WORLD",
    # Google News RSS - Elevage MA (forces T2 - betail strict)
    "GNews — Bétail MA":                      "WORLD",
    "GNews — Aviculture MA":                  "WORLD",
    "GNews — Viande MA":                      "WORLD",
    "GNews — ANOC FIVOB":                     "WORLD",
    "GNews — Lait Maroc":                     "WORLD",
    "GNews — Aquaculture MA":                 "MAROC",
    "GNews — Peche Aquaculture":              "MAROC",
    "GNews — Aquaculture Monde":              "WORLD",
    "GNews — Transformation Poisson":         "MAROC",
    # Google News RSS - BACKFILL T4 Environnement + T5 Normes
    "GNews — Eau Maroc":                      "WORLD",
    "GNews — Energie Maroc":                  "WORLD",
    "GNews — Climat Maroc":                   "WORLD",
    "GNews — Normes RSE":                     "WORLD",
    "GNews — Securite alimentaire":           "WORLD",
    "GNews — QSE SST Maroc":                  "WORLD",
    "GNews — Gouvernance ESG MA":             "WORLD",
    "Financial Afrik":                        "WORLD",
    "EU EMAS":                                "EU",
    "EFRAG":                                  "EU",
    "Food Navigator":                         "EU",

    # WORLD
    "FAO Newsroom":                           "WORLD",
    "Codex Alimentarius":                     "WORLD",
    "GlobalG.A.P.":                           "WORLD",
    "DairyReporter":                          "WORLD",
    "Poultry World":                          "WORLD",
    "UNEP":                                   "WORLD",
    "WRI":                                    "WORLD",
    "TNFD":                                   "WORLD",
    "SBTi":                                   "WORLD",
    "CDP":                                    "WORLD",
    "GHG Protocol":                           "WORLD",
    "Climate Home News":                      "WORLD",
    "Carbon Brief":                           "WORLD",
    "IRENA":                                  "WORLD",
    "Energy Voice":                           "WORLD",
    "Basel Convention":                       "WORLD",
    "UN Global Compact":                      "WORLD",
    "OECD RBC":                               "WORLD",
    "ISO News":                               "WORLD",
    "ISO 26000":                              "WORLD",
    "ISO 14001":                              "WORLD",
    "ISO 14000 Family":                       "WORLD",
    "EcoVadis":                               "WORLD",
    "GRI":                                    "WORLD",
    "IFRS / ISSB":                            "WORLD",
    "IFRS / SASB":                            "WORLD",
    "ESG Investor":                           "WORLD",
    "Environmental Finance":                  "WORLD",
    "PRI":                                    "WORLD",
    "ILO Safework":                           "WORLD",
    "OSHA US":                                "WORLD",
    "FDA News":                               "WORLD",
    "WHO News":                               "WORLD",
    "Sedex (SMETA)":                          "WORLD",
    "BRCGS":                                  "WORLD",
    "IFS Food":                               "WORLD",
    "FSSC 22000":                             "WORLD",
    "Fairtrade International":                "WORLD",
}

MEDIA_SCOUT_SOURCE_THEME_HINTS = {
    "Agrumes, Fruits rouges & Maraichage": [
        "agri", "agriculture", "agrimaroc", "fao", "ministere agriculture", "onssa",
        "globalgap", "codex", "food.ec.europa",
        "agrume", "fruits", "legume", "maraichage", "primeur", "horticulture",
        "fraise", "framboise", "myrtille", "berries", "citrus", "orange", "mandarine",
        "tomate", "courgette", "aubergine", "poivron",
    ],
    "Elevage (Ovins, Bovins, Caprins, Volailles)": [
        "elevage", "viande", "volaille", "bovin", "ovin", "caprin", "poultry",
        "woah", "poultryworld",
        "mouton", "chevre", "agneau", "boeuf", "poulet", "dinde", "canard",
        "abattoir", "veterinaire", "sante animale",
    ],
    "Produits laitiers & Epicerie fine": [
        "foodnavigator", "dairyreporter",
        "lait", "laitier", "laiterie", "dairy", "fromage", "yaourt", "beurre",
        "epicerie", "deli", "delicatessen", "gourmet", "terroir",
        "produits laitiers", "epicerie fine",
    ],
    "Environnement, Eau & Energie": [
        "eau", "water", "equipement.gov.ma", "hydrique", "irrigation", "barrage",
        "energie", "energy", "iea", "irena", "transition-energetique", "mem.gov.ma",
        "levert", "energetique", "renouvelable", "masen", "noor",
        "environnement", "environment", "ecology", "climate", "unep", "wri", "mapecology",
        "medias24", "actu-environnement", "carbonbrief", "climatechangenews",
        "tnfd", "sbti", "ghgprotocol", "cdp", "basel",
    ],
    "ESG, QSE & SST": [
        "rse", "csr", "esg", "cgem", "novethic", "fnh", "globalreporting",
        "efrag", "ifrs", "iso", "sasb", "issb", "unglobalcompact", "global compact",
        "oecd", "ecovadis", "afnor",
        "imanor", "ammc", "sedex", "brcgs", "ifs-certification", "fssc", "fairtrade",
        "osha", "ilo", "safework", "sante", "who.int", "fda.gov",
        "efsa.europa", "health.ec.europa",
    ],
}

# ─── Filtres post-classification ──────────────────────────────────────────────
# Objectif : garder articles pertinents pour le Maroc (direct ou impact indirect),
# retirer le bruit pays-specifique (France/UK/US/etc. sans portee internationale),
# et pour le theme IA, retirer le bruit "infrastructure" (data centers, GPUs).

# Mentions directes Maroc -> garde toujours
MEDIA_SCOUT_MOROCCO_DIRECT_MARKERS = [
    "maroc", "morocco", "marocain", "marocaine", "marocains", "marocaines",
    "maghreb", "afrique du nord", "north africa",
    "casablanca", "rabat", "tanger", "marrakech", "fes ", "agadir", "meknes",
    "oujda", "tetouan", "kenitra", "dakhla", "laayoune", "ouarzazate", "nador",
    "ocp ", "managem", "attijariwafa", "bcp ", "bank of africa", "cih bank",
    "marjane", "label vie", "groupe ynna", "saham", "akwa group",
    "maroc telecom", "iam ", "addoha", "alliances",
    "cnss", "anapec", "agence pour la promotion",
    "dh ", "dirham", "dirhams",
]

# Portee large / internationale / EU-wide / standards -> garde
MEDIA_SCOUT_BROAD_SCOPE_MARKERS = [
    # Portee globale / internationale
    "international", "internationale", "internationaux", "internationales",
    "mondial", "mondiale", "mondiaux", "mondiales", "monde",
    "global", "globale", "globally", "worldwide", "world ",
    # Afrique
    "afrique", "africa", "africain", "african", "pan-african", "panafricain",
    "afdb", "african development bank", "bad ",
    # Mediterranee
    "mediterranee", "mediterranean", "pays mediterraneens", "mena ",
    "moyen-orient", "middle east",
    # EU institutionnel
    "union europeenne", "european union", " ue ", " eu ",
    "commission europeenne", "european commission",
    "conseil europeen", "european council", "parlement europeen", "european parliament",
    "directive europeenne", "european directive", "reglement europeen",
    "eu regulation", "eu directive", "eu taxonomy", "taxonomie europeenne",
    "csrd", "esrs", "sfdr", "csddd", "cbam", "esma", "efrag", "efsa",
    "dg sante", "dg env", "dg agri", "european green deal", "pacte vert",
    # Standards / referentiels internationaux
    "iso ", "norme iso", "iso 9001", "iso 14001", "iso 22000", "iso 26000",
    "iso 45001", "iso 50001", "iso 14064", "iso 14067",
    "fssc 22000", "haccp",
    "gri ", "ifrs s1", "ifrs s2", "sasb", "issb", "tcfd", "tnfd", "cdp ",
    "ghg protocol", "sbti", "science based targets",
    "globalgap", "global gap", "globalg.a.p", "smeta", "sedex",
    "brc", "brcgs", "ifs food", "fairtrade", "rspo", "rainforest alliance",
    "fsc certification", "ifoam", "codex alimentarius", "b corp", "ecovadis",
    # Organismes internationaux
    "fao ", "wto ", "omc ", "oms ", "who ", "ilo ", "oit ", "ocde", "oecd",
    "world bank", "banque mondiale", "fmi", "imf",
    "g7 ", "g20", "g7,", "g20,",
    "cop28", "cop29", "cop30", "cop31", "cop ",
    "nations unies", "united nations", "global compact", "ungc",
    "fda ", "usda ", "ema ", "ich ",
    # Climat / supply chain / sustainability scope
    "climate change", "changement climatique", "rechauffement climatique",
    "neutralite carbone", "carbon neutrality", "net zero", "carbon neutral",
    "accord de paris", "paris agreement", "paris accord",
    "biodiversite", "biodiversity", "deforestation",
    "supply chain", "chaine d'approvisionnement", "chaine de valeur",
    "transition energetique", "energy transition", "transition ecologique",
    "ecologic transition",
    # Marchés transverses / exports
    "exportation", "import-export", "commerce international", "international trade",
    "trade agreement", "accord commercial",
]

# Marqueurs pays-specifiques sans portee internationale -> drop sauf si marqueur positif present
MEDIA_SCOUT_COUNTRY_SPECIFIC_MARKERS = [
    # France
    "hexagone", "metropole francaise", "departement francais", "departements francais",
    "elysee", "matignon", "premier ministre francais", "gouvernement francais",
    "ministre francais", "ministre de france", "assemblee nationale francaise",
    "senat francais", "conseil constitutionnel francais",
    "ile-de-france", "bretagne", "normandie", "auvergne", "occitanie",
    "nouvelle-aquitaine", "hauts-de-france", "grand est", "bourgogne",
    "pays de la loire", "centre-val de loire", "provence-alpes",
    "prefet", "prefecture", "sous-prefet", "rectorat", "academie de",
    "loi francaise", "decret francais", "code du travail francais",
    "smic", "rsa ", "csg", "crds", "arcep", "arcom", "cnil",
    "fiscalite francaise", "tva francaise",
    "macron", "borne", "attal", "barnier", "lecornu",
    # UK
    "downing street", "westminster", "british government",
    "house of commons", "house of lords", "scotland regulation",
    "wales regulation", "england only", "uk parliament", "british retailer",
    "rishi sunak", "keir starmer", "ofcom", "fca uk",
    # US (US-state-specific, not Federal which often has global impact)
    "california law", "texas law", "new york state", "florida state",
    "us state-level", "california bill", "us governor",
    "house ways and means", "us house energy and commerce",
    # Germany
    "bundestag", "bundesrat", "bundesregierung",
    "scholz", "merz administration",
    # Spain
    "moncloa", "congreso de los diputados",
    "ley espanola",
    # Italy
    "palazzo chigi", "camera dei deputati",
    "meloni",
]

MEDIA_SCOUT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def _clean_media_text(value):
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


# Pied-de-page de flux RSS WordPress -> bruit a retirer des resumes/descriptions.
# Ex: "The post <titre> appeared first on <site>." / "L'article ... est apparu en
# premier sur ...". Coupe a partir du marqueur jusqu'a la fin.
_RSS_FOOTER_RE = re.compile(
    r"\s*(?:the post\b.*?appeared first on\b"
    r"|l['’]article\b.*?est apparu en premier sur\b"
    r"|cet article\b.*?(?:provient|est issu) de\b"
    r"|read more\b.*$|lire la suite\b.*$).*$",
    re.IGNORECASE | re.DOTALL,
)


def _strip_rss_artifacts(value):
    """Retire les pieds-de-page de flux RSS (WordPress) des descriptions."""
    if not value:
        return value
    return _RSS_FOOTER_RE.sub("", value).strip()


def _fold_media_text(value):
    text = _clean_media_text(value).lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(char for char in text if not unicodedata.combining(char))


def _source_name_from_url(source_url, link=""):
    for catalog_url, name in MEDIA_SCOUT_URL_TO_NAME.items():
        if source_url == catalog_url or link.startswith(catalog_url):
            return name
    host = urlparse(link or source_url).netloc.lower().replace("www.", "")
    return MEDIA_SCOUT_URL_TO_NAME.get(source_url, host or "Source inconnue")


def _normalize_media_date(date_value):
    text = _clean_media_text(date_value)
    if not text:
        return ""

    try:
        parsed = parsedate_to_datetime(text)
        if parsed:
            return parsed.strftime("%d/%m/%Y")
    except Exception:
        pass

    iso_match = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", text)
    if iso_match:
        year, month, day = iso_match.groups()
        return f"{int(day):02d}/{int(month):02d}/{year}"

    numeric_match = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", text)
    if numeric_match:
        day, month, year = numeric_match.groups()
        if len(year) == 2:
            year = f"20{year}"
        return f"{int(day):02d}/{int(month):02d}/{year}"

    folded = _fold_media_text(text).replace(".", " ")
    months = {
        "janvier": "01", "january": "01", "jan": "01",
        "fevrier": "02", "february": "02", "feb": "02",
        "mars": "03", "march": "03", "mar": "03",
        "avril": "04", "april": "04", "apr": "04",
        "mai": "05", "may": "05",
        "juin": "06", "june": "06", "jun": "06",
        "juillet": "07", "july": "07", "jul": "07",
        "aout": "08", "august": "08", "aug": "08",
        "septembre": "09", "september": "09", "sep": "09", "sept": "09",
        "octobre": "10", "october": "10", "oct": "10",
        "novembre": "11", "november": "11", "nov": "11",
        "decembre": "12", "december": "12", "dec": "12",
    }
    month_regex = "|".join(sorted(months, key=len, reverse=True))
    text_date = re.search(rf"(\d{{1,2}})(?:er)?\s+({month_regex})\s*(20\d{{2}})?", folded)
    if text_date:
        day, month_name, year = text_date.groups()
        year = year or str(datetime.now().year)
        return f"{int(day):02d}/{months[month_name]}/{year}"
    return ""


def _date_from_url(link):
    link = link or ""
    match = re.search(r"/(20\d{2})/(\d{1,2})/(\d{1,2})(?:/|-)", link)
    if match:
        year, month, day = match.groups()
        return f"{int(day):02d}/{int(month):02d}/{year}"
    return ""


# Titres "poubelle" : elements de navigation/UI captes par erreur par le scraper
# (ex: DG SANTE expose un bouton "Filter by"). Rejetes au niveau _article_record.
_JUNK_TITLES = frozenset({
    "filter by", "filter", "filters", "read more", "lire la suite", "load more",
    "voir plus", "see all", "voir tout", "show more", "all news", "toutes les actualites",
    "subscribe", "newsletter", "search", "rechercher", "menu", "share", "partager",
    "next", "previous", "suivant", "precedent", "read article", "en savoir plus",
    "more", "view all", "accueil", "home", "back", "retour",
})


def _article_record(source_url, title, description, link, date_value):
    title = _clean_media_text(title)
    description = _strip_rss_artifacts(_clean_media_text(description))
    link = urljoin(source_url, _clean_media_text(link))
    date_text = _normalize_media_date(date_value) or _date_from_url(link)
    if not title or len(title) < 8 or not link or not date_text:
        return None
    # Rejette les titres de navigation/UI (ex: "Filter by", "Read more"...)
    if _fold_media_text(title).strip() in _JUNK_TITLES:
        return None
    return {
        "Date": date_text,
        "Title": title,
        "Description": description,
        "Link": link,
        "Website_name": _source_name_from_url(source_url, link),
    }


def _fetch_media_url(url):
    # timeout=(connect, read) : echoue vite sur un hote mort (5s pour ouvrir la
    # connexion) tout en laissant le temps de lire une page lente (9s).
    try:
        response = requests.get(url, headers=MEDIA_SCOUT_HEADERS, timeout=(5, 9))
        response.raise_for_status()
        return response
    except requests.RequestException:
        return None


def _is_media_feed(url, response):
    content_type = response.headers.get("Content-Type", "").lower()
    sample = response.text[:200].lstrip().lower()
    return "xml" in content_type or "rss" in content_type or sample.startswith(("<?xml", "<rss", "<feed"))


def _find_xml_text(node, names):
    for name in names:
        value = node.findtext(name)
        if value:
            return value
    return ""


def _extract_feed_articles(response, source_url):
    try:
        root = ElementTree.fromstring(response.content)
    except ElementTree.ParseError:
        return []

    articles = []
    content_tag = "{http://purl.org/rss/1.0/modules/content/}encoded"
    dc_date_tag = "{http://purl.org/dc/elements/1.1/}date"
    for item in root.findall(".//item"):
        record = _article_record(
            source_url,
            _find_xml_text(item, ["title"]),
            _find_xml_text(item, ["description", "summary", content_tag]),
            _find_xml_text(item, ["link", "guid"]),
            _find_xml_text(item, ["pubDate", "date", dc_date_tag]),
        )
        if record:
            articles.append(record)
    return articles


_DATE_TEXT_PATTERN = re.compile(
    r"\b("
    r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}"        # 22/05/2026, 22-05-2026
    r"|\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2}"          # 2026-05-22
    r"|\d{1,2}\s+(?:jan|feb|fev|mar|apr|avr|may|mai|jun|jul|aug|aou|sep|oct|nov|dec|janvier|fevrier|mars|avril|juin|juillet|aout|septembre|octobre|novembre|decembre|january|february|march|april|june|july|august|september|october|november|december)[a-z]*\s+\d{2,4}"
    r"|(?:jan|feb|fev|mar|apr|avr|may|mai|jun|jul|aug|aou|sep|oct|nov|dec|january|february|march|april|june|july|august|september|october|november|december)[a-z]*\s+\d{1,2},?\s+\d{2,4}"
    r")\b",
    re.IGNORECASE,
)


def _extract_card_date(card):
    # 1. <time datetime="..."> ou <time>texte</time>
    time_node = card.find("time")
    if time_node:
        return time_node.get("datetime") or time_node.get_text(" ", strip=True)
    # 2. Element avec class contenant un mot-cle date-related (large)
    for class_fragment in [
        "date", "time", "published", "publish", "meta", "itemdate",
        "post-date", "release-date", "communique-date", "when", "timestamp"
    ]:
        date_node = card.find(attrs={"class": re.compile(class_fragment, re.IGNORECASE)})
        if date_node:
            text = date_node.get_text(" ", strip=True)
            if text:
                return text
    # 3. Fallback : cherche une date litterale (22/05/2026, 22 mai 2026, etc.)
    #    dans tout le texte de la card. Bcp de sites mettent juste "22 mai 2026"
    #    dans un <span> ou <p> sans class identifiable.
    card_text = card.get_text(" ", strip=True)
    if card_text:
        match = _DATE_TEXT_PATTERN.search(card_text)
        if match:
            return match.group(1)
    return ""


def _extract_html_articles(soup, source_url):
    articles = []
    # Selectors elargis pour matcher les structures presse/communiques modernes
    # (les sites corporate utilisent souvent press-release / communique / item au
    # lieu des classes article / news classiques).
    selectors = [
        "article",
        "div.timeline-content",
        "div.article-list-item",
        "div.card",
        "div.post",
        "div[class*='article']",
        "div[class*='news']",
        "div[class*='press']",
        "div[class*='release']",
        "div[class*='communique']",
        "div[class*='post']",
        "div[class*='entry']",
        "div[class*='media-item']",
        "div[class*='media-tile']",
        "li[class*='article']",
        "li[class*='news']",
        "li[class*='press']",
        "li[class*='release']",
        "li[class*='communique']",
        "li[class*='post']",
        "li[class*='entry']",
        "li[class*='item']",
    ]
    seen_nodes = set()
    for selector in selectors:
        for card in soup.select(selector):
            if id(card) in seen_nodes:
                continue
            seen_nodes.add(id(card))
            title_node = card.find(["h1", "h2", "h3", "h4"])
            link_node = title_node.find("a", href=True) if title_node else None
            link_node = link_node or card.find("a", href=True)
            if not link_node:
                continue
            description_node = card.find("p")
            record = _article_record(
                source_url,
                title_node.get_text(" ", strip=True) if title_node else link_node.get_text(" ", strip=True),
                description_node.get_text(" ", strip=True) if description_node else "",
                link_node.get("href", ""),
                _extract_card_date(card),
            )
            if record:
                articles.append(record)
    return articles


def _discover_feed_urls(soup, source_url):
    feed_urls = []
    for node in soup.find_all("link", attrs={"type": re.compile("rss|atom|xml", re.IGNORECASE)}):
        href = node.get("href")
        if href:
            feed_urls.append(urljoin(source_url, href))
    return list(dict.fromkeys(feed_urls))[:2]


def _scrape_media_source(source_url):
    response = _fetch_media_url(source_url)
    if response is None:
        return []
    if _is_media_feed(source_url, response):
        return _extract_feed_articles(response, source_url)

    soup = BeautifulSoup(response.text, "html.parser")
    articles = _extract_html_articles(soup, source_url)
    for feed_url in _discover_feed_urls(soup, source_url):
        feed_response = _fetch_media_url(feed_url)
        if feed_response is not None and _is_media_feed(feed_url, feed_response):
            articles.extend(_extract_feed_articles(feed_response, source_url))
    return articles


def _safe_scrape_media_source(source_url):
    """Wrapper defensif : ne propage jamais d'exception (parsing HTML malforme,
    encodage, etc.) pour qu'une seule source defaillante ne casse pas tout le
    batch parallele. Retourne [] en cas d'erreur."""
    try:
        return _scrape_media_source(source_url)
    except Exception:
        return []


@lru_cache(maxsize=4096)
def _compile_keyword_pattern(keyword):
    """Pre-compile et cache le pattern regex pour un mot-cle.

    Optimisation : appele des milliers de fois (chaque article x chaque keyword).
    Le LRU evite de re-compiler les memes patterns + factorise le fold/escape.
    """
    folded = _fold_media_text(keyword)
    if not folded:
        return None
    return re.compile(r"(?<!\w)" + re.escape(folded) + r"(?!\w)")


def _keyword_in_media_text(text, keyword):
    pattern = _compile_keyword_pattern(keyword)
    return bool(pattern and pattern.search(text))


def _score_media_theme(title_text, body_text, theme):
    rules = MEDIA_SCOUT_THEME_RULES.get(theme, {})
    score = 0
    strong_hits = 0
    medium_hits = 0
    title_medium_hits = 0
    for keyword in rules.get("strong", []):
        if _keyword_in_media_text(title_text, keyword):
            score += 5
            strong_hits += 1
        elif _keyword_in_media_text(body_text, keyword):
            score += 4
            strong_hits += 1
    for keyword in rules.get("medium", []):
        if _keyword_in_media_text(title_text, keyword):
            score += 3
            medium_hits += 1
            title_medium_hits += 1
        elif _keyword_in_media_text(body_text, keyword):
            score += 2
            medium_hits += 1
    for keyword in rules.get("weak", []):
        if _keyword_in_media_text(title_text, keyword) or _keyword_in_media_text(body_text, keyword):
            score += 1
    return {"score": score, "strong_hits": strong_hits, "medium_hits": medium_hits, "title_medium_hits": title_medium_hits}


def _source_has_theme_hint(source_context, theme):
    return any(_fold_media_text(hint) in source_context for hint in MEDIA_SCOUT_SOURCE_THEME_HINTS.get(theme, []))


def _has_enough_theme_signal(result, source_hint=False):
    """Verifie si un article a assez de signal pour etre rattache a un theme.

    Plusieurs voies acceptees (du plus fort au plus faible) :
      1. Au moins 1 mot strong dans le titre/body (signal direct, sans seuil de score)
      2. Mot medium dans le titre + score >= 3
      3. 2+ mots medium dans body + score >= 4
      4. Avec source hint (la source est connue thematiquement) : score >= 2 suffit
    """
    if result["strong_hits"] >= 1:
        return True
    if result["title_medium_hits"] >= 1 and result["score"] >= 3:
        return True
    if result["medium_hits"] >= 2 and result["score"] >= 4:
        return True
    if source_hint and result["score"] >= 2:
        return True
    return False


def _score_media_veille(title_text, body_text, veille):
    rules = MEDIA_SCOUT_VEILLE_RULES.get(veille, {})
    score = 0
    strong_hits = 0
    medium_hits = 0
    for keyword in rules.get("strong", []):
        if _keyword_in_media_text(title_text, keyword):
            score += 5
            strong_hits += 1
        elif _keyword_in_media_text(body_text, keyword):
            score += 4
            strong_hits += 1
    for keyword in rules.get("medium", []):
        if _keyword_in_media_text(title_text, keyword):
            score += 3
            medium_hits += 1
        elif _keyword_in_media_text(body_text, keyword):
            score += 2
            medium_hits += 1
    for keyword in rules.get("weak", []):
        if _keyword_in_media_text(title_text, keyword) or _keyword_in_media_text(body_text, keyword):
            score += 1
    return {"score": score, "strong_hits": strong_hits, "medium_hits": medium_hits}


# ─── Filtre pre-classification : exclure articles hors scope ──────────────────
# Applique sur le DataFrame brut AVANT _assign_media_theme.
# Permet de garantir une stricte adhesion thematique en supprimant le bruit.

# Stop-words distinctifs pour detection langue (FR vs autres latines)
_FR_STOP = (
    "le ", "la ", "les ", "des ", "du ", "de la ", "de l", "au ", "aux ",
    "et ", "ou ", "qui ", "que ", "qu'", "pour ", "dans ", "avec ", "sur ",
    "est ", "sont ", "ete ", "etre ", "selon ", "vers ", "chez ", "afin ",
    "donc ", "alors ", "tres ", "plus ", "moins ", "leurs ", "leur ",
    "ne ", "pas ", "n'", "c'", "d'", "l'", "j'", "m'", "t'", "s'",
)
_EN_STOP = (
    "the ", "and ", "of ", "is ", "are ", "was ", "were ", "with ", "from ",
    "for ", "this ", "that ", "these ", "those ", "have ", "has ", "had ",
    "will ", "would ", "could ", "should ", "but ", "not ", "their ",
    "they ", "them ", "which ", "between ", "through ", "during ", "however ",
    "regarding ", "moreover ", "whereas ",
)

_FILTER_REMERCIEMENT_MARKERS = (
    "remerciement", "remerciements", "remercier", "remercie", "remercions",
    "remerciant", "merci ", "merci a ", "merci à ", "merci pour",
    "thanks", "thank you", "thank-you", "acknowledgment", "acknowledgement",
    "acknowledgements", "acknowledgments", "in memoriam", "hommage", "hommages",
    "rendant hommage",
)

_FILTER_PORC_MARKERS = (
    " porc ", " porcs ", " porcin", "porcine", "porcines", "porcs ",
    " cochon", " cochons", "truie", "truies", "verrat", "verrats",
    " pork ", " hog ", " hogs ", " pig ", " pigs ", " sow ", " sows ",
    " swine", "boar ", "filiere porcine", "filiere porc", "filiere porcin",
    "elevage porcin", "elevage de porcs", "viande de porc", "viande porc",
    "porkers", "pigprogress",
)

# Filtre animaux hors scope T2 Elevage (ovins/bovins/caprins/volailles uniquement)
# Note 1 : on garde "miel" (epicerie fine T3) mais on filtre apiculture/elevage abeilles
# Note 2 : on RETIRE chameau/dromadaire/buffle car ces especes apparaissent souvent
# en mention secondaire dans des articles legitimes sur l'elevage au Maghreb
# (ex: "marche du betail incluant ovins et dromadaires").
_FILTER_OTHER_ANIMALS_MARKERS = (
    # Equides (focus competition, sport, viande -> hors scope LDA)
    " cheval ", " chevaux ", " jument", " etalon", " poney", " poulain",
    "equin ", "equine", "equidé", "equide", "filiere equine", "elevage equin",
    "viande de cheval", "viande chevaline",
    # Apiculture (elevage d'abeilles - distinct de miel produit fini)
    "apicult", "apiculteur", "apicultrice", "elevage d'abeilles", "elevage abeille",
    "ruche", "ruches", "filiere apicole",
    # NB: pisciculture / aquaculture NON exclues (thème dédié "Aquaculture")
    # Cunicole (lapin)
    " lapin ", " lapins ", "cuniculture", "cunicole", "filiere cunicole",
    " lievre ", " lievres ", "elevage cunicole", "viande de lapin",
    # Pets / animaux de compagnie
    " chien ", " chiens ", "petfood", "pet food", "animal de compagnie",
    "animaux de compagnie", "elevage canin", "filiere petfood",
    # Gibier sauvage (rarement le focus principal)
    " cerf ", " cerfs ", "daim ", " sanglier",
    "elevage de gibier", "gibier d'elevage",
    # Insectes (elevage)
    "elevage d'insectes", "elevage insectes", "filiere insectes",
)

_FILTER_JOB_MARKERS = (
    "offre d emploi", "offre d'emploi", "offres d'emploi", "offres d emploi",
    "recrute", "recrutement", "recrutent", "recruter", "recrutons",
    "job offer", "job offers", "we are hiring", "we re hiring", "we're hiring",
    "hiring now", "carriere", "carrieres", "candidature", "candidatures",
    "envoyez votre cv", "envoyer cv", "poste a pourvoir", "postes a pourvoir",
    "intitule du poste", "fiche de poste", "stage etudiant", "alternance",
    "apprentissage", "rejoignez-nous", "rejoignez nous", "join our team",
    "join us", "join the team", "open positions", "open roles",
    "talents recherches", "recherche profil", "embauche",
)

_FILTER_AUTO_MARKERS = (
    "automobile", "automotive", "voiture", "voitures", "vehicule auto",
    "vehicules automobile", "auto-moto", "auto moto", "constructeur auto",
    "constructeur automobile", "industrie automobile",
    "salon de l auto", "salon de l'auto", "salon auto",
    "renault", "peugeot", "citroen", "stellantis", "tesla", "byd auto",
    "audi", "bmw", "mercedes", "toyota", "volkswagen", "porsche", "ferrari",
    "fiat", "hyundai", "kia", "honda", "nissan", "mazda", "suzuki", "chery",
    "leapmotor", "nio", "xpeng", "lucid motors", "rivian",
    "concessionnaire auto", "showroom automobile",
    "vehicule electrique", "voiture electrique", "bornes de recharge",
    "moteur thermique", "moteur diesel", "moteur essence",
    "f1 ", "formule 1", "moto gp", "rallye dakar",
)

# Fast-food / restauration rapide (hors scope : LDA = production agro, pas resto)
_FILTER_FASTFOOD_MARKERS = (
    "fast food", "fast-food", "fastfood", "restauration rapide", "junk food",
    "malbouffe", "drive-in", "drive in", "fried chicken", "burger ",
    "hamburger", "cheeseburger", "nuggets", "menu enfant",
    "mcdonald", "mcdo ", "burger king", " kfc", "kfc ", "quick burger",
    "subway", "pizza hut", "domino's", "dominos pizza", "five guys",
    "starbucks", "chicken nuggets",
)

_FILTER_HEALTH_PURE_MARKERS = (
    # Pathologies / cliniques (sans lien direct alimentaire/agro/SST)
    "covid-19", "covid 19", "coronavirus", "vaccin covid", "vaccination covid",
    "vaccin grippe", "grippe saisonniere", "rougeole", "varicelle", "rubeole",
    "tuberculose", "diabete chronique", "cancer du sein", "cancer prostate",
    "cancer colorectal", "maladie cardiovasculaire", "infarctus", "avc cerebral",
    "infection nosocomiale", "alzheimer", "parkinson", "sclerose en plaques",
    "depression nerveuse", "trouble anxieux", "trouble bipolaire",
    "schizophrenie", "autisme",
    # Sante reproductive / pediatrique
    "fertilite", "pma fiv", "grossesse", "accouchement", "pediatrie",
    "obstetrique", "gynecologie",
    # Pharma medicaments
    "essai clinique", "medicament generique", "ema medicament",
    "approbation fda medicament",
)

_FILTER_HEALTH_WHITELIST_MARKERS = (
    # Si l'article mentionne ces termes, on NE filtre PAS (pertinent agro/QSE/SST)
    "alimentaire", "alimentation", "agriculture", "agricole", "agro", "elevage",
    "filiere", "production", "transformation", "rse", "qse", "sst",
    "securite au travail", "occupational health", "iso 22000", "iso 45001",
    "iso 14001", "haccp", "norme", "regulation", "reglement", "directive",
    "environnement", "climat", "energie", "eau", "export",
    "marche", "filiere agricole", "filiere viande", "filiere laitiere",
    "residus", "pesticide", "pesticides", "phytosanitaire", "contamination",
    "rappel produit", "retrait produit", "tracabilite",
)

_FILTER_OTHER_COUNTRY_MARKERS = (
    # Pays africains autres
    "egypte", "egypt", "tunisie", "algerie", "libye", "soudan", "mauritanie",
    "senegal", "cote d'ivoire", "cote d ivoire", "ivory coast", "ghana",
    "nigeria", "kenya", "ethiopie", "afrique du sud", "south africa",
    "rdc ", "republique democratique du congo", "congo ", "cameroun",
    # Ameriques
    "etats-unis", "etats unis", "usa ", "us economy", "americain", "american",
    "canada ", "canadien", "mexique", "mexico", "bresil", "brazil",
    "argentina", "argentine", "chili", "perou", "colombie", "venezuela",
    # Asie
    "chine ", "china ", "chinese", "chinois", "pekin", "shanghai", "hong kong",
    "inde ", "india ", "indien", "indian", "new delhi", "mumbai",
    "japon", "japan", "japonais", "japanese", "tokyo",
    "coree du sud", "south korea", "seoul", "coreen",
    "thailande", "vietnam", "indonesie", "malaisie", "philippines",
    "singapour", "singapore", "taiwan",
    # Europe (pays specifiques, hors UE generique)
    "russie", "russia", "russian", "russe", "moscou",
    "ukraine", "ukrainien",
    "turquie", "turkey", "turc", "istanbul", "ankara",
    # Australie / Pacifique
    "australie", "australia", "nouvelle-zelande", "new zealand",
)


def _is_french_or_english(text: str) -> bool:
    """Heuristique : detecte si un texte est en francais ou anglais.

    1. Rejette les scripts non-latins (Arabe, Chinois, Cyrillique, Hebreu, etc.)
    2. Parmi les scripts latins, exige au moins 2 stop-words FR ou EN distinctifs
    Sinon -> probable autre langue (espagnol/allemand/italien/portugais) -> rejet.
    """
    if not text or len(text.strip()) < 8:
        return True  # texte trop court : on garde par defaut
    # Detection scripts non-latins (rejet immediat)
    for ch in text[:300]:  # check les 300 premiers chars suffit
        if ch.isalpha():
            o = ord(ch)
            # Arabe (0600-06FF), Cyrillique (0400-04FF), Hebreu (0590-05FF),
            # CJK (3400+), Hiragana/Katakana, Devanagari, Thai, Coreen
            if (0x0600 <= o <= 0x06FF or 0x0400 <= o <= 0x04FF or
                0x0590 <= o <= 0x05FF or 0x3400 <= o <= 0x9FFF or
                0x3040 <= o <= 0x30FF or 0x0900 <= o <= 0x097F or
                0x0E00 <= o <= 0x0E7F or 0xAC00 <= o <= 0xD7AF):
                return False
    # Comptage stop-words FR / EN (distinctifs)
    lower = " " + text.lower() + " "
    fr_hits = sum(1 for m in _FR_STOP if m in lower)
    en_hits = sum(1 for m in _EN_STOP if m in lower)
    # Au moins 2 stop-words dans une des 2 langues
    return fr_hits >= 2 or en_hits >= 2


def _should_exclude_article(row) -> bool:
    """Filtre pre-classification : exclut les articles hors scope.

    Exclusions :
      - Langue autre que FR/EN
      - Articles de remerciement / hommages
      - News porcines (hors scope Elevage = ovin/bovin/caprin/volaille)
      - Offres d'emploi / recrutement
      - Automobile / industrie auto
      - Sante 'pure' (pathologies, vaccins) sans contexte agro/QSE/SST
      - Mentions d'ONCF (rail marocain hors scope)
      - Pour sources marocaines : articles qui parlent uniquement d'un autre pays
    Retourne True si l'article doit etre exclu.
    """
    title_raw = str(row.get("Title", ""))
    desc_raw = str(row.get("Description", ""))
    full_raw = title_raw + " " + desc_raw

    # Filtre 0 : langue (FR/EN uniquement)
    if not _is_french_or_english(full_raw):
        return True

    title = _fold_media_text(title_raw)
    desc = _fold_media_text(desc_raw)
    text = title + " " + desc

    # Filtre 0bis : commentaires de blog (flux WordPress incluant les commentaires)
    # Ex : "Commentaires sur ... par X" -> bruit, jamais un article de fond.
    if title.startswith(("commentaires sur ", "commentaire sur ", "comments on ")):
        return True

    # Filtre 1 : remerciements / hommages
    if any(m in text for m in _FILTER_REMERCIEMENT_MARKERS):
        return True

    # Filtre 2 : porc / cochon (hors scope T2 Elevage)
    # On entoure le texte d'espaces pour matcher les mots entiers
    padded = " " + text + " "
    if any(m in padded for m in _FILTER_PORC_MARKERS):
        return True

    # Filtre 2bis : autres animaux hors scope T2 (cheval, abeille, poisson, lapin,
    # chien/chat, chameau, buffle, cerf, insectes...)
    if any(m in padded for m in _FILTER_OTHER_ANIMALS_MARKERS):
        return True

    # Filtre 3 : offres d'emploi
    if any(m in text for m in _FILTER_JOB_MARKERS):
        return True

    # Filtre 4 : automobile
    if any(m in text for m in _FILTER_AUTO_MARKERS):
        return True

    # Filtre 4bis : fast-food / restauration rapide (hors scope production agro)
    if any(m in padded for m in _FILTER_FASTFOOD_MARKERS):
        return True

    # Filtre 5 : ONCF (rail Maroc hors scope LDA)
    if "oncf" in text or "office national des chemins de fer" in text:
        return True

    # Filtre 6 : sante 'pure' sans lien agro/QSE/SST
    has_pure_health = any(m in text for m in _FILTER_HEALTH_PURE_MARKERS)
    has_whitelist = any(m in text for m in _FILTER_HEALTH_WHITELIST_MARKERS)
    if has_pure_health and not has_whitelist:
        return True

    # Filtre 7 : sources marocaines parlant d'un autre pays SANS mention Maroc
    website = str(row.get("Website_name", ""))
    is_maroc_source = MEDIA_SCOUT_SOURCE_ZONES.get(website) == "MAROC"
    if is_maroc_source:
        has_other_country = any(c in text for c in _FILTER_OTHER_COUNTRY_MARKERS)
        has_maroc = any(
            m in text
            for m in ("maroc", "morocco", "marocain", "marocaine", "maghreb")
        )
        if has_other_country and not has_maroc:
            return True

    return False


# Especes betail strictement dans le scope T2 (ovins/bovins/caprins/volailles).
# Garde-fou : un article classe T2 DOIT contenir au moins UNE de ces mentions
# en titre ou description, sinon il est demote en "Autres" (evite les faux
# positifs type "oléiculteurs", "élevés" adjectif, etc.).
_T2_LIVESTOCK_SPECIES = (
    # Ovins
    "ovin", "ovins", "ovine", "mouton", "moutons", "agneau", "agneaux",
    "brebis", "belier", "beliers",
    # Bovins
    "bovin", "bovins", "bovine", "vache", "vaches", "veau", "veaux",
    "boeuf", "boeufs", "taureau", "genisse", "genisses", "cattle",
    # Caprins
    "caprin", "caprins", "caprine", "chevre", "chevres", "chevreau", "bouc",
    # Volailles
    "volaille", "volailles", "poulet", "poulets", "poule", "poules", "poussin",
    "dinde", "dindes", "canard", "canards", "oie", "oies", "pintade",
    "caille", "broiler", "poultry", "aviculture", "avicole",
    # Cheptel / generic livestock
    "cheptel", "betail", "livestock", "troupeau", "troupeaux",
    # Filiere viande
    "viande", "viandes", "meat", "abattoir", "abattoirs", "abattage",
    "slaughterhouse", "boucherie",
    # Evenement Aïd (= marche ovin)
    "aid al adha", "aid el adha", "aid el kebir", "aid kebir",
    "aid adha", "eid al adha", "eid el kebir", "fete du sacrifice",
    "sacrifice du mouton", "tabaski", "souk al kbach", "souk kbach",
    # Federations
    "anoc", "fivob", "fisa ", "fimabe", "interprovi", "sonacos",
)


def _has_livestock_species(title_folded: str, body_folded: str) -> bool:
    """True si le texte mentionne au moins une espece betail / contexte direct.

    Utilise word-boundary matching pour eviter les faux matchs.
    """
    for species in _T2_LIVESTOCK_SPECIES:
        if _keyword_in_media_text(title_folded, species):
            return True
        if _keyword_in_media_text(body_folded, species):
            return True
    return False


# Pays africains/Maghreb NON-Maroc : focus geographique non pertinent pour T2.
# Garde les articles UE / WW (qui peuvent affecter exports Maroc), mais filtre
# ceux dont le sujet principal est un pays voisin/africain autre.
_T2_AFRICA_NON_MAROC = (
    # Maghreb non-Maroc
    "mauritanie", "mauritanien", "mauritanienne", "mauritania", "mauritanian",
    "algerie", "algerien", "algerienne", "algeria", "algerian",
    "tunisie", "tunisien", "tunisienne", "tunisia", "tunisian",
    "libye", "libyen", "libyenne", "libya", "libyan",
    # Afrique de l'Ouest (marches separes du Maroc)
    "senegal", "senegalais", "senegalaise",
    "mali ", "malien", "malienne",
    "burkina faso", "burkinabe",
    "cote d'ivoire", "cote d ivoire", "ivory coast", "ivoirien", "ivoirienne",
    "niger ", "nigerien", "nigerienne",
    "ghana ", "ghaneen", "ghaneenne", "ghanaian",
    "nigeria", "nigerian",
    # Afrique subsaharienne (autres)
    "ethiopie", "ethiopien", "ethiopian",
    "kenya", "kenyan",
    "tanzanie", "tanzanien",
    "rwanda", "rwandais",
    "ouganda", "ugandan",
    "congo ", "congolais",
    "cameroun", "camerounais",
)

_T2_MAROC_MARKERS = (
    "maroc", "morocco", "marocain", "marocaine", "moroccan",
    "rabat", "casablanca", "tanger", "fes ", "marrakech", "agadir",
)


def _t2_is_foreign_focused(title_folded: str) -> bool:
    """True si le titre cible un pays etranger africain SANS focus Maroc.

    Regle : un article est "foreign focused" si :
    - Le titre contient un marker pays africain non-Maroc ; ET
    - Soit Maroc n'apparait pas du tout dans le titre ;
    - Soit le pays etranger apparait AVANT Maroc dans le titre (= sujet principal)

    Garde les articles type "Maroc importe du Senegal", "Maroc-Algerie...".
    Filtre les articles type "Mauritanie : prix moutons", "Race algerienne au Maroc".
    """
    foreign_pos = -1
    for marker in _T2_AFRICA_NON_MAROC:
        idx = title_folded.find(marker)
        if idx >= 0 and (foreign_pos < 0 or idx < foreign_pos):
            foreign_pos = idx
    if foreign_pos < 0:
        return False  # aucune mention pays africain non-MA

    maroc_pos = -1
    for marker in _T2_MAROC_MARKERS:
        idx = title_folded.find(marker)
        if idx >= 0 and (maroc_pos < 0 or idx < maroc_pos):
            maroc_pos = idx

    # Si Maroc absent du titre -> sujet est le pays etranger -> exclure
    if maroc_pos < 0:
        return True
    # Si pays etranger apparait AVANT Maroc -> sujet principal est le pays etranger
    if foreign_pos < maroc_pos:
        return True
    return False


# ── Garde-fou T1 : recentrage Agrumes / Fruits rouges / Tomates cerises ──────
# Un article classe T1 portant sur une culture HORS cible (cereale, ou autre
# maraichage : aubergine, courgette, pomme de terre...) SANS mentionner de
# culture cible NI de sujet filiere/export large qui les englobe est demote hors
# T1. Evite "Ble tendre : ...", "Aubergine : ...", tout en gardant les sujets
# globaux ("export de fruits et legumes", "Morocco Foodex"...).
_T1_TARGET_CROPS = (
    # Agrumes
    "agrume", "agrumes", "orange", "oranges", "mandarine", "mandarines",
    "clementine", "clementines", "citron", "citrons", "pamplemousse", "pamplemousses",
    "pomelo", "kumquat", "bergamote", "citrus", "navel", "valencia",
    "nadorcott", "afourer", "maroc late", "soft citrus", "maroc citrus", "agrumicole",
    # Fruits rouges
    "fruits rouges", "fruit rouge", "fraise", "fraises", "framboise", "framboises",
    "myrtille", "myrtilles", "mure", "mures", "cassis", "groseille", "groseilles",
    "berries", "berry", "strawberry", "raspberry", "blueberry", "blackberry",
    "cranberry", "petits fruits", "soft fruit", "soft fruits",
    # Tomates (cerises)
    "tomate", "tomates", "tomato", "tomatoes", "cherry tomato",
)
# Sujets filiere / export LARGES qui englobent les cultures cibles -> a garder.
_T1_SECTOR_TERMS = (
    "fruits et legumes", "fruit et legume", "primeur", "primeurs",
    "morocco foodex", "moroccan exports", "agroexport", "agro-export",
    "export agricole", "exportation agricole", "exportations agricoles",
    "fresh produce", "fruit and vegetable", "fruits and vegetables",
    "eacce", "aspam", "apefel",
)
# Cultures HORS cible (cereales / grandes cultures + autres maraichages).
_T1_OFF_TARGET_CROPS = (
    # Cereales / grandes cultures
    "ble", "ble tendre", "ble dur", "cereale", "cereales", "orge", "riz",
    "avoine", "sorgho", "tournesol", "colza", "betterave", "canne a sucre",
    "legumineuse", "legumineuses", "pois chiche", "feve", "feves",
    # Autres maraichages hors cible
    "aubergine", "aubergines", "courgette", "courgettes", "poivron", "poivrons",
    "piment", "piments", "concombre", "concombres", "salade", "laitue",
    "oignon", "oignons", "ail", "carotte", "carottes", "pomme de terre",
    "patate", "patates", "haricot", "haricots", "petit pois", "epinard", "epinards",
    "chou", "choux", "brocoli", "artichaut", "artichauts", "asperge", "asperges",
    "navet", "navets", "radis", "courge", "courges", "potiron", "melon", "melons",
    "pasteque", "pasteques", "fenouil", "poireau", "poireaux", "celeri", "gombo", "okra",
)

_T1_ORANGE_BRAND_MARKERS = (
    "orange maroc", "orange business", "orange money", "orange digital",
    "orange telecom", "orange group", "orange cyberdefense",
    "telecom", "telecommunications", "operateur telecom", "operateur telephonique",
    "telephonie", "reseau mobile", "mobile money", "fibre optique", "internet",
    "5g", "4g", "cloud", "data center", "datacenter", "cybersecurite",
    "intelligence artificielle", "ia", "digital", "numerique", "startup",
    "start-up", "innovation technologique", "made in morocco",
)
_T1_ORANGE_FRUIT_CONTEXT = (
    "agrume", "agrumes", "oranges", "citrus", "agrumicole", "filiere agrumes",
    "maroc citrus", "campagne agrumes", "verger", "vergers", "recolte",
    "cueillette", "production d'orange", "production orange", "prix de l'orange",
    "prix des oranges", "jus d'orange", "export orange", "export d'orange",
    "exportation orange", "tonnes d'orange", "tonnes d'oranges",
    "mandarine", "mandarines", "clementine", "clementines", "nadorcott",
    "afourer", "navel", "valencia", "maroc late", "soft citrus",
)


def _t1_is_orange_brand_noise(text_folded: str) -> bool:
    """Distingue la marque Orange des oranges/agrumes.

    Si Orange apparait avec un contexte telecom/IA/digital, mais sans contexte
    fruit/agrumes, l'article ne doit pas etre rattache au theme T1.
    """
    if not _keyword_in_media_text(text_folded, "orange"):
        return False
    if not any(_keyword_in_media_text(text_folded, kw) for kw in _T1_ORANGE_BRAND_MARKERS):
        return False
    if any(_keyword_in_media_text(text_folded, kw) for kw in _T1_ORANGE_FRUIT_CONTEXT):
        return False
    return True


def _t1_is_off_target(text_folded: str) -> bool:
    """True si l'article doit etre demote hors T1 : il porte sur une culture hors
    cible (cereale / autre maraichage) SANS mentionner de culture cible (agrumes /
    fruits rouges / tomate) ni de sujet filiere-export large qui les englobe.

    NB : `text_folded` = titre + description SEULEMENT (jamais le nom de source,
    sinon des sources nommees "...Agrumes...", "...Fruits..." injecteraient un mot
    cible et neutraliseraient la garde). Word-boundary matching (ble != table).
    """
    # 0) Homonyme "Orange" marque/telco -> demote si aucun contexte agrumes.
    if _t1_is_orange_brand_noise(text_folded):
        return True
    # 1) Culture cible presente -> jamais demote
    for kw in _T1_TARGET_CROPS:
        if _keyword_in_media_text(text_folded, kw):
            return False
    # 2) Sujet filiere/export large qui englobe les cibles -> garde
    for kw in _T1_SECTOR_TERMS:
        if _keyword_in_media_text(text_folded, kw):
            return False
    # 3) Hors-cible explicite (cereale / autre maraichage) -> demote
    for kw in _T1_OFF_TARGET_CROPS:
        if _keyword_in_media_text(text_folded, kw):
            return True
    return False


# ── Garde-fou T3 : recentrage Produits laitiers & Épicerie fine ──────────────
# Un article classe T3 portant sur l'EQUIPEMENT / la TECHNO de transformation
# agroalimentaire (JBT, Marel, GEA, Tetra Pak, "technologies alimentaires"...)
# est demote hors T3. Deux niveaux :
#   • Fabricant d'equipement nomme -> demote TOUJOURS (l'article est centre
#     equipement, meme s'il evoque le secteur "dairy").
#   • Terme techno/process generique -> demote SEULEMENT si aucun produit ni
#     marque laitier/epicerie n'est cite (sinon on garde, ex. "ligne de yaourt
#     chez Danone"). Les news concurrentielles (Danone, Lactalis...) restent.
_T3_EQUIP_MAKERS = (
    "jbt", "marel", "gea group", "tetra pak", "tetrapak", "sidel", "krones",
    "spx flow", "alfa laval", "buhler", "multivac",
)
_T3_EQUIP_TERMS = (
    "equipementier", "machine d'emballage", "machines d'emballage",
    "ligne de conditionnement", "ligne de production", "ligne d'embouteillage",
    "process technology", "processing equipment", "processing technology",
    "food processing equipment", "technologie alimentaire", "technologies alimentaires",
    "foodtech", "food tech", "agritech", "automatisation industrielle",
)


def _t3_is_off_target(text_folded: str) -> bool:
    """True si l'article doit etre demote hors T3 (equipement / techno de
    transformation), False sinon. Voir le commentaire ci-dessus pour la regle.
    """
    # 1) Fabricant d'equipement nomme -> centre equipement -> demote
    for kw in _T3_EQUIP_MAKERS:
        if _keyword_in_media_text(text_folded, kw):
            return True
    # 2) Terme techno/process generique : demote seulement si AUCUN produit/marque
    if any(_keyword_in_media_text(text_folded, kw) for kw in _T3_EQUIP_TERMS):
        strong = MEDIA_SCOUT_THEME_RULES["Produits laitiers & Epicerie fine"]["strong"]
        if not any(_keyword_in_media_text(text_folded, kw) for kw in strong):
            return True
    return False


# ── Garde-fou T4 : Environnement, Eau & Énergie -> Maroc OU portee mondiale ──
# Un article T4 centre sur un pays/region etranger (ex. Braskem / Ameriques,
# "China's emissions", "UK's carbon budget"...) SANS dimension Maroc ni portee
# globale (mondial, COP, GIEC, ONU, UE...) est demote. On garde : le Maroc, les
# sujets mondiaux/UE, et les sujets sans focus pays. Matching par mot entier
# (gere les possessifs anglais "china's", evite "chinatown").
_T4_MAROC_MARKERS = (
    "maroc", "morocco", "marocain", "marocaine", "maghreb", "afrique du nord",
    "rabat", "casablanca", "tanger", "marrakech", "agadir",
)
_T4_GLOBAL_MARKERS = (
    "mondial", "mondiale", "mondiaux", "monde", "planete", "planetaire",
    "cop28", "cop29", "cop30", "cop 28", "cop 29", "cop 30", "giec", "ipcc",
    "accord de paris", "nations unies", "onu", "banque mondiale", "fmi", "oms",
    "mediterranee", "mediterraneen",
    # UE / Europe : reglementation impactant les exports Maroc -> pertinent
    "union europeenne", "ue", "europe", "europeen", "europeenne", "bruxelles",
)
# Pays/regions etrangers : marqueurs nettoyes (sans espace) -> match mot entier.
_T4_FOREIGN_MARKERS = tuple(sorted(
    {m.strip() for m in _FILTER_OTHER_COUNTRY_MARKERS}
    | {"ameriques", "amerique latine", "amerique du nord", "amerique du sud",
       "amazonie", "amazon", "californie", "texas", "royaume-uni", "uk",
       "angleterre", "britannique", "british", "londres", "allemagne",
       "allemand", "espagne", "espagnol", "italie", "italien"}
))


def _t4_is_off_scope(text_folded: str) -> bool:
    """True si un article T4 doit etre demote : focus pays/region etranger (hors
    Maroc) SANS dimension Maroc ni portee globale/UE. Voir commentaire ci-dessus.
    """
    if any(_keyword_in_media_text(text_folded, m) for m in _T4_MAROC_MARKERS):
        return False
    if any(_keyword_in_media_text(text_folded, m) for m in _T4_GLOBAL_MARKERS):
        return False
    if any(_keyword_in_media_text(text_folded, m) for m in _T4_FOREIGN_MARKERS):
        return True
    return False


def _assign_media_theme(row):
    """Classification par mots-cles avec fallbacks defensifs.

    Voies de classification (du plus fort au plus faible) :
      1. Scoring keyword : au moins 1 strong OU title-medium OU 2 medium
      2. Domain override : URL host connue (onssa.gov.ma -> T1, afnor.org -> T5, etc.)
      3. Forced source theme : source mono-thematique (ex: AgriMaroc -> T1)
      4. 'Autres' (sera filtre en aval)

    Garde-fou T2 : si l'article est classe Elevage MAIS ne mentionne aucune
    espece betail dans titre/description, on le re-route (vers le 2eme best
    candidate ou "Autres"). Evite les faux positifs (oléiculteurs, etc.).
    """
    website_name = str(row.get("Website_name", ""))
    link_host = urlparse(str(row.get("Link", ""))).netloc.lower().replace("www.", "")

    source_context = _fold_media_text(" ".join([website_name, str(row.get("Link", ""))]))
    title_text = _fold_media_text(row.get("Title", ""))
    body_text = _fold_media_text(" ".join([str(row.get("Description", "")), website_name, str(row.get("Link", ""))]))
    # Texte "propre" titre + description (SANS nom de source ni lien) pour les
    # gardes T1/T3 -> evite que les sources nommees ("Agrumes...", "Lait...")
    # injectent un mot cible et faussent la garde.
    guard_text = title_text + " " + _fold_media_text(row.get("Description", ""))

    candidates = {}
    for theme in MEDIA_SCOUT_THEME_RULES:
        result = _score_media_theme(title_text, body_text, theme)
        if _has_enough_theme_signal(result, _source_has_theme_hint(source_context, theme)):
            candidates[theme] = result

    T2 = "Elevage (Ovins, Bovins, Caprins, Volailles)"
    T1 = "Agrumes, Fruits rouges & Maraichage"
    T3 = "Produits laitiers & Epicerie fine"
    T4 = "Environnement, Eau & Energie"

    # Helper : verifie qu'un candidat T2 passe les 2 gardes (especes + geo)
    def _t2_passes_guards():
        if not _has_livestock_species(title_text, body_text):
            return False
        if _t2_is_foreign_focused(title_text):
            return False
        return True

    # Garde-fou par theme : T1 recentre (cultures cibles), T2 betail,
    # T3 produits laitiers/epicerie (hors equipement/techno), T4 Maroc/mondial.
    def _guard_ok(theme):
        if theme == T2:
            return _t2_passes_guards()
        if theme == T1:
            return not _t1_is_off_target(guard_text)
        if theme == T3:
            return not _t3_is_off_target(guard_text)
        if theme == T4:
            return not _t4_is_off_scope(guard_text)
        return True

    # Une demotion GEOGRAPHIQUE (hors perimetre Maroc/monde) -> "Autres" sans
    # reroutage : un article etranger hors-scope ne doit pas atterrir dans un
    # autre theme (ex. Braskem/Ameriques ne doit pas glisser de T4 vers T3).
    # Une demotion de CONTENU (mauvais theme) autorise le reroutage.
    def _is_geo_demotion(theme):
        if theme == T4:
            return True  # seul motif de demote T4 = hors-scope geo
        if theme == T2:  # T2 geo = espece presente mais focus pays etranger
            return _has_livestock_species(title_text, body_text) and _t2_is_foreign_focused(title_text)
        return False     # T1 / T3 = gardes de contenu -> reroutage permis

    if candidates:
        sorted_candidates = sorted(
            candidates.items(),
            key=lambda item: (item[1]["strong_hits"], item[1]["medium_hits"], item[1]["score"]),
            reverse=True,
        )
        best = sorted_candidates[0][0]
        if not _guard_ok(best):
            # Hors-scope geographique -> Autres ; sinon (contenu) -> reroutage.
            if _is_geo_demotion(best):
                return "Autres"
            for cand, _ in sorted_candidates[1:]:
                if _guard_ok(cand):
                    return cand
            return "Autres"
        return best

    # Fallback 1 : override par domaine (pour les regulateurs/specialistes
    # dont 99% des articles sont sur leur theme par definition).
    for domain, theme in MEDIA_SCOUT_DOMAIN_THEME_OVERRIDES.items():
        if domain in link_host:
            # Gardes-fou (T1/T2) appliquees aussi sur le domain override
            if not _guard_ok(theme):
                continue
            return theme

    # Fallback 2 : theme force pour les sources mono-thematiques
    # (ex: AgriMaroc -> T1, ONSSA -> T1, AMMC -> T5)
    forced = MEDIA_SCOUT_FORCED_SOURCE_THEMES.get(website_name)
    if forced:
        # Gardes-fou (T1/T2) : meme une source forcee verifie sa garde.
        if not _guard_ok(forced):
            return "Autres"
        return forced

    return "Autres"


# Feeds d'intelligence concurrentielle "purpose-built" (topic-scopes laitier/
# epicerie) : leurs articles sont forces en Veille Concurrentielle (sinon les
# articles sans mot-cle business explicite — nutrition, packaging — tomberaient
# en Informative, alors qu'ils relevent de la veille concurrentielle T3).
_FORCE_CONCURRENTIELLE_SOURCES = {
    # T3 — Produits laitiers & Épicerie fine
    "GNews — Presse éco MA", "GNews — Lait International", "GNews — FMCG Retail",
    "GNews — Nutrition Santé", "GNews — Nouveautés Premium",
    # T1 — Agrumes, Fruits rouges & Tomates cerises
    "GNews — Agrumes Export MA", "GNews — Marché Agrumes Intl",
    "GNews — Marché Fruits Rouges", "GNews — Concurrents Primeurs",
    "GNews — Production Fruits MA", "GNews — Innovations Fruits",
}


def _assign_media_veille(row):
    """Classifie l'article dans l'une des 4 Veilles.

    Veille Informative est le defaut (fallback) si aucun signal des autres
    Veilles n'est suffisant. Reglementaire > Concurrentielle > Evenementielle
    en cas d'egalite de score (les regulations priment sur les annonces business).
    """
    # Sources d'intelligence concurrentielle dediees -> forcees Concurrentielle
    if str(row.get("Website_name", "")).strip() in _FORCE_CONCURRENTIELLE_SOURCES:
        return "Veille Concurrentielle"

    title_text = _fold_media_text(row.get("Title", ""))
    body_text = _fold_media_text(" ".join([
        str(row.get("Description", "")),
        str(row.get("Title", "")),
    ]))

    veille_priority = ["Veille Reglementaire", "Veille Concurrentielle", "Veille Evenementielle"]
    candidates = {}
    for veille in veille_priority:
        result = _score_media_veille(title_text, body_text, veille)
        # Une Veille est candidate s'il y a au moins un strong hit OU au moins 2 medium hits.
        if result["strong_hits"] >= 1 or result["medium_hits"] >= 2:
            candidates[veille] = result

    if not candidates:
        return "Veille Informative"

    # Tie-break: strong_hits, medium_hits, score, puis ordre de priorite
    def sort_key(item):
        veille, result = item
        return (result["strong_hits"], result["medium_hits"], result["score"],
                -veille_priority.index(veille))
    best = max(candidates.items(), key=sort_key)[0]
    return best


def _is_morocco_relevant(row):
    """Garde l'article si Maroc-relevant (direct ou impact potentiel).

    Regles :
    - Source zone MAROC -> garde toujours
    - Marqueur Maroc direct (titre/desc) -> garde
    - Marqueur portee large (UE-wide, ISO, FAO, ESG, climat...) -> garde
    - Marqueur pays-specifique (France/UK/US-state/etc.) sans marqueur positif -> drop
    - Pas de signal clair -> garde par defaut (eviter les faux negatifs)
    """
    zone = MEDIA_SCOUT_SOURCE_ZONES.get(row.get("Website_name", ""), "")
    if zone == "MAROC":
        return True

    text = _fold_media_text(" ".join([
        str(row.get("Title", "")),
        str(row.get("Description", "")),
    ]))
    if not text:
        return True

    has_maroc = any(marker in text for marker in MEDIA_SCOUT_MOROCCO_DIRECT_MARKERS)
    if has_maroc:
        return True

    has_broad_scope = any(marker in text for marker in MEDIA_SCOUT_BROAD_SCOPE_MARKERS)
    has_country_specific = any(marker in text for marker in MEDIA_SCOUT_COUNTRY_SPECIFIC_MARKERS)

    # Marqueur pays-specifique present sans portee large -> drop (news purement domestique)
    if has_country_specific and not has_broad_scope:
        return False

    # Si portee large OU rien de pays-specifique -> garde
    return True


def _should_keep_article(row):
    """Filtre combine applique apres classification theme/veille."""
    return _is_morocco_relevant(row)


# ─── Cache schedule (refresh aux heures fixes Maroc) ──────────────────────────
# Le scraping global se rafraichit a CES heures (heure locale Maroc) :
SCHEDULED_REFRESH_HOURS = [7, 19]  # 07h00 et 19h00 (modifiable)

# Fenetre de collecte : seuls les articles des N derniers jours sont conserves.
# Applique tres tot dans le pipeline (avant classification, validation LLM et
# traduction) -> reduit fortement le volume traite, le temps de refresh aux
# creneaux 07h/19h et les tokens LLM consommes. Aligne sur le date-picker de
# l'app (max 15 jours).
MEDIA_SCOUT_MAX_AGE_DAYS = 15
try:
    _TZ_MAROC = ZoneInfo("Africa/Casablanca")
except Exception:
    # Fallback Windows sans tzdata : UTC+1 fixe (Maroc reste sur UTC+1 toute l'annee)
    from datetime import timezone
    _TZ_MAROC = timezone(timedelta(hours=1), name="Africa/Casablanca")


# Bumper cette version a chaque modification de la taxonomie (themes, keywords, sources).
# Inclus dans le slot de cache -> invalide automatiquement le DataFrame en cache et
# force un re-scraping a la prochaine execution.
_TAXONOMY_VERSION = "v35"


def current_cache_slot() -> str:
    """Retourne un identifiant de creneau qui change aux heures programmees.

    Ex : entre 07h00 et 18h59 -> 'YYYY-MM-DD-07h-<version>'
         entre 19h00 et 06h59 -> 'YYYY-MM-DD-19h-<version>'

    Utilise comme parametre de cache de data_media_scout : quand le creneau OU la
    version de taxonomie change, la cle de cache change -> Streamlit re-execute
    la fonction -> nouveau scraping + re-classification.
    """
    now = _datetime_maroc()
    hour = now.hour
    passed_hours = [h for h in SCHEDULED_REFRESH_HOURS if hour >= h]
    if passed_hours:
        last_hour = max(passed_hours)
        slot_date = now.strftime("%Y-%m-%d")
    else:
        # Avant la 1ere heure du jour -> on est dans le creneau du jour precedent (derniere heure)
        last_hour = max(SCHEDULED_REFRESH_HOURS)
        slot_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    return f"{slot_date}-{last_hour:02d}h-{_TAXONOMY_VERSION}"


def _datetime_maroc() -> datetime:
    """Retourne datetime.now() en heure locale Maroc (gere les DST)."""
    return datetime.now(_TZ_MAROC)


@st.cache_data(show_spinner=False, persist="disk")  # cle = slot (meme que data_media_scout)
def media_scrape_timestamp(slot: str = "") -> datetime:
    """Horodatage reel de la derniere collecte de donnees (heure Maroc).

    Mise en cache par 'slot' (meme cle que data_media_scout) : la valeur est
    figee au PREMIER acces de chaque creneau — c.-a-d. au moment ou le scraping
    reel se produit — puis reutilisee jusqu'au prochain creneau. Reflete donc
    fidelement la derniere mise a jour effective des donnees affichees.

    A appeler avec le meme slot que data_media_scout : current_cache_slot().
    """
    return _datetime_maroc()


def format_last_update(dt: datetime) -> str:
    """Formate un datetime en 'JJ/MM/YYYY · HHhMM' pour affichage filterbar."""
    if dt is None:
        return ""
    return dt.strftime("%d/%m/%Y · %Hh%M")


@st.cache_data(show_spinner=False, persist="disk")  # TTL pilote par slot (cf. current_cache_slot)
def data_media_scout(urls=None, slot: str = ""):
    """Scraping global. La param 'slot' fait partie de la cle de cache : son
    changement (declenche a 07h00 / 19h00) force un re-scraping. Le slot a
    passer est current_cache_slot() — fournit par l'app au moment de l'appel.

    persist="disk" : le resultat est aussi ecrit sur disque -> si le conteneur
    Streamlit Cloud redemarre (reveil apres mise en veille, reboot), le cache du
    creneau courant est recharge instantanement au lieu de re-scraper."""
    urls = urls or MEDIA_SCOUT_URLS
    source_urls = [source["URL"] if isinstance(source, dict) else source for source in urls]

    # Scraping PARALLELE : les ~65 sources sont fetchees concurremment (I/O reseau
    # => le GIL est libere pendant les requetes). Une source lente/morte ne bloque
    # plus les autres. Speedup typique 5-10x vs boucle sequentielle.
    data = []
    max_workers = min(24, len(source_urls)) or 1
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for articles in executor.map(_safe_scrape_media_source, source_urls):
            data.extend(articles)

    columns = ["Date", "Title", "Description", "Link", "Website_name", "Theme", "Veille"]
    if not data:
        empty_df = pd.DataFrame(columns=columns)
        empty_df["Date"] = pd.to_datetime(empty_df["Date"])
        return empty_df

    df = pd.DataFrame(data).astype(str)
    df["Date"] = df["Date"].apply(_normalize_media_date)
    df["Date"] = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors="coerce")
    df = df.dropna(subset=["Date", "Title", "Link"])

    # ── Fenetre de collecte (15 jours) : coupe AVANT tout traitement lourd ──
    # Les articles plus vieux ne sont jamais affichables (picker max 15j) ;
    # les ecarter ici evite classification + validation LLM + traduction inutiles.
    _cutoff = pd.Timestamp(_datetime_maroc().date()) - pd.Timedelta(days=MEDIA_SCOUT_MAX_AGE_DAYS)
    df = df[df["Date"] >= _cutoff]
    if df.empty:
        empty_df = pd.DataFrame(columns=columns)
        empty_df["Date"] = pd.to_datetime(empty_df["Date"])
        return empty_df

    # Filtre pre-classification : exclure offres emploi, auto, sante pure, ONCF, non-Maroc
    # .copy() -> df autonome (evite SettingWithCopyWarning sur les ecritures de colonnes).
    df = df[~df.apply(_should_exclude_article, axis=1)].copy()
    if df.empty:
        empty_df = pd.DataFrame(columns=columns)
        empty_df["Date"] = pd.to_datetime(empty_df["Date"])
        return empty_df
    df["Theme"] = df.apply(_assign_media_theme, axis=1)
    df = df[df["Theme"].isin(MEDIA_SCOUT_THEMES)].copy()

    if df.empty:
        empty_df = pd.DataFrame(columns=columns)
        empty_df["Date"] = pd.to_datetime(empty_df["Date"])
        return empty_df

    # ── Validation LLM par theme : juge si le titre est strictement lie au theme ──
    # Cette couche capture les articles qui matchent les keywords mais sont en realite
    # off-topic. Erreur safe : si LLM echoue, on garde tout (pas de perte de donnees).
    df = _llm_validate_themes(df)

    if df.empty:
        empty_df = pd.DataFrame(columns=columns)
        empty_df["Date"] = pd.to_datetime(empty_df["Date"])
        return empty_df

    df["Veille"] = df.apply(_assign_media_veille, axis=1)

    # Filtre post-classification : pertinence Maroc (zone MAROC, marqueur Maroc
    # direct, ou portee large UE/mondiale) -> ecarte les news purement etrangeres.
    df = df[df.apply(_should_keep_article, axis=1)].copy()

    if df.empty:
        empty_df = pd.DataFrame(columns=columns)
        empty_df["Date"] = pd.to_datetime(empty_df["Date"])
        return empty_df

    df["_title_key"] = df["Title"].apply(_fold_media_text)
    df["_link_key"] = df["Link"].str.replace(r"(\?|#).*$", "", regex=True)
    df = df.drop_duplicates(subset=["_link_key"])
    df = df.drop_duplicates(subset=["_title_key"])
    df = df.drop(columns=["_title_key", "_link_key"])

    # Traduction FR des articles non-francophones (sources institutionnelles EN :
    # EFSA, DairyReporter, Climate Home, etc.). ~4% des articles. Batched + cache
    # via le slot. Garantit que TOUS les resumes affiches sont en francais.
    df = _translate_articles_to_french(df)

    df["Theme"] = pd.Categorical(df["Theme"], categories=MEDIA_SCOUT_THEMES, ordered=True)
    df["Veille"] = pd.Categorical(df["Veille"], categories=MEDIA_SCOUT_VEILLES, ordered=True)
    df = df.sort_values(["Veille", "Theme", "Date"], ascending=[True, True, False])
    return df[columns]


# ─── LLM multi-provider failover (Google Gemini + Groq) ──────────────────────
# Permet d'utiliser plusieurs providers LLM avec plusieurs cles API par provider
# (free tier limite). Priorite : Google Gemini d'abord, puis Groq. Quand une cle
# atteint son rate limit, on passe a la suivante. Apres 60s de cooldown, la cle
# epuisee redevient utilisable.
#
# Architecture :
#   - _LLM_PROVIDERS : tuple ordonne (provider, secret_name, default_model)
#   - _LLM_EXHAUSTED : dict global { secret_name -> datetime cooldown_end }
#   - _llm_chat_with_failover() : interface unifiee retournant un objet
#       OpenAI-compatible (response.choices[0].message.content)
#   - _groq_chat_with_failover : alias retro-compat -> _llm_chat_with_failover

# Ordre de priorite : Google d'abord (free tier plus genereux), Groq en backup
_LLM_PROVIDERS = (
    ("google", "GOOGLE_API_KEY",   "gemini-3.5-flash"),
    ("google", "GOOGLE_API_KEY_1", "gemini-3.5-flash"),
    ("groq",   "GROQ_API_KEY",     "llama-3.3-70b-versatile"),
    ("groq",   "GROQ_API_KEY_1",   "llama-3.3-70b-versatile"),
)

# Module-level dict (partage entre toutes les sessions Streamlit du process)
# secret_name -> datetime jusqu'auquel la cle est marquee comme epuisee
_LLM_EXHAUSTED = {}


def _get_secret_or_env(name: str):
    """Recupere une valeur depuis st.secrets en priorite, sinon os.environ."""
    try:
        v = st.secrets.get(name)
        if v:
            return v
    except Exception:
        pass
    return os.getenv(name)


def _get_available_llm_providers() -> list:
    """Liste des entrees (provider, secret_name, model, key_value) configurees.

    Filtre les entrees sans cle valable et celles dont le SDK n'est pas dispo
    (ex: google-genai non installe).
    """
    out = []
    for provider, secret_name, model in _LLM_PROVIDERS:
        if provider == "google" and not _GENAI_AVAILABLE:
            continue
        key = _get_secret_or_env(secret_name)
        if not key:
            continue
        out.append((provider, secret_name, model, key))
    return out


def _has_any_llm_key() -> bool:
    """True si au moins une cle LLM (Google ou Groq) est configuree."""
    return bool(_get_available_llm_providers())


def _is_key_available(secret_name: str) -> bool:
    """True si la cle n'est pas marquee comme epuisee (ou si cooldown expire)."""
    if secret_name not in _LLM_EXHAUSTED:
        return True
    if datetime.now() >= _LLM_EXHAUSTED[secret_name]:
        del _LLM_EXHAUSTED[secret_name]
        return True
    return False


def _mark_key_exhausted(secret_name: str, cooldown_seconds: int = 60):
    """Marque une cle comme epuisee pendant `cooldown_seconds` (defaut 60s)."""
    _LLM_EXHAUSTED[secret_name] = datetime.now() + timedelta(seconds=cooldown_seconds)


def _wrap_llm_response(content: str):
    """Wrappe un texte en objet OpenAI-compatible (response.choices[0].message.content)."""
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content or "")
            )
        ]
    )


def _is_rate_limit_error(exc: Exception) -> bool:
    """Detecte un rate-limit / quota a partir du texte d'exception."""
    err = str(exc).lower()
    return (
        "rate_limit" in err
        or "rate limit" in err
        or "ratelimit" in err
        or "429" in err
        or "too many requests" in err
        or "quota" in err
        or "resource_exhausted" in err
        or "resource exhausted" in err
        or "tokens per minute" in err
        or "requests per minute" in err
    )


def _call_groq_provider(api_key, model, messages, max_tokens, temperature, **kwargs):
    """Appel Groq retournant un objet OpenAI-compatible."""
    client = Groq(api_key=api_key)
    return client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        **kwargs,
    )


def _call_gemini_provider(api_key, model, messages, max_tokens, temperature, **kwargs):
    """Appel Google Gemini (SDK google-genai >=2.x) retournant un objet OpenAI-compatible.

    Convertit les messages OpenAI-style (role=system/user/assistant) au format
    google-genai :
      - role=system → config.system_instruction (concat de tous les system)
      - role=assistant → role=model dans `contents`
      - role=user → role=user dans `contents`
    Utilise client.models.generate_content(model=..., contents=..., config=...).
    """
    if not _GENAI_AVAILABLE:
        raise RuntimeError("google-genai non installe")

    client = _genai.Client(api_key=api_key)

    # Separe system prompt (concat de tous les role=system) du reste
    system_parts = []
    contents = []
    for m in messages:
        role = (m.get("role") or "").lower()
        content = m.get("content") or ""
        if role == "system":
            system_parts.append(content)
        elif role == "assistant":
            contents.append({"role": "model", "parts": [{"text": content}]})
        else:  # user (defaut)
            contents.append({"role": "user", "parts": [{"text": content}]})

    system_instruction = "\n\n".join(p for p in system_parts if p) or None

    # Build config (GenerateContentConfig). Le SDK accepte aussi un dict.
    config_kwargs = {
        "temperature": float(temperature) if temperature is not None else 0.4,
        "max_output_tokens": int(max_tokens) if max_tokens else 500,
    }
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction

    try:
        config = _genai_types.GenerateContentConfig(**config_kwargs)
    except Exception:
        # Fallback : dict simple si types pas dispo / signature changee
        config = config_kwargs

    # Cas trivial : 1 seul user message -> on peut passer directement le texte
    if len(contents) == 1 and contents[0]["role"] == "user":
        prompt_text = contents[0]["parts"][0]["text"]
        resp = client.models.generate_content(
            model=model,
            contents=prompt_text,
            config=config,
        )
    else:
        resp = client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

    # Extraction robuste du texte (resp.text peut etre vide / lever si bloque)
    text = ""
    try:
        text = resp.text or ""
    except Exception:
        try:
            text = "".join(
                getattr(p, "text", "") or ""
                for p in resp.candidates[0].content.parts
            )
        except Exception:
            text = ""

    return _wrap_llm_response(text)


def _llm_chat_with_failover(messages, model=None, max_tokens=500,
                            temperature=0.4, **kwargs):
    """Appel chat completion avec basculement automatique entre providers/cles.

    Ordre tente : Google Gemini (cles 1 & 2) puis Groq llama (cles 1 & 2).
    Sur rate limit (429 / quota / resource_exhausted), marque la cle epuisee
    pendant 60s et passe a la suivante. Sur erreur non-rate-limit (auth, model
    inconnu, etc.), passe quand meme a la suivante mais memorise l'erreur pour
    diagnostic (un provider invalide ne doit pas bloquer les autres).

    Note : l'argument `model` est ignore (chaque entree _LLM_PROVIDERS a son
    propre modele par defaut). Garde pour retro-compat avec les call sites.

    Returns: objet OpenAI-compatible avec response.choices[0].message.content.
    Raises: RuntimeError si aucun provider n'est configure ou si tous echouent.
    """
    available = _get_available_llm_providers()
    if not available:
        raise RuntimeError(
            "Aucune cle API LLM configuree (GOOGLE_API_KEY, GOOGLE_API_KEY_1, "
            "GROQ_API_KEY ou GROQ_API_KEY_1)"
        )

    last_error = None
    tried = 0
    for provider, secret_name, default_model, api_key in available:
        if not _is_key_available(secret_name):
            continue
        tried += 1
        try:
            if provider == "google":
                return _call_gemini_provider(
                    api_key, default_model, messages,
                    max_tokens, temperature, **kwargs,
                )
            else:  # groq
                return _call_groq_provider(
                    api_key, default_model, messages,
                    max_tokens, temperature, **kwargs,
                )
        except Exception as exc:
            last_error = exc
            if _is_rate_limit_error(exc):
                _mark_key_exhausted(secret_name, cooldown_seconds=60)
            else:
                # Erreur non-rate-limit : cooldown plus court (5s) pour eviter
                # de marteler une cle cassee, mais sans bloquer trop longtemps
                # au cas ou ce serait transitoire (network).
                _mark_key_exhausted(secret_name, cooldown_seconds=5)
            continue  # essaie le prochain provider/cle

    if last_error:
        raise last_error
    raise RuntimeError(
        "Toutes les cles API LLM sont actuellement en cooldown. "
        "Reessaye dans ~1 minute."
    )


# Alias retro-compat : ancien nom utilise par les call sites existants
_groq_chat_with_failover = _llm_chat_with_failover


# ─── Couche de validation LLM (qualite thematique) ────────────────────────────
# Apres l'assignation par keywords, le LLM scan les titres et juge si chaque
# article est REELLEMENT lie au theme assigne. Permet de retirer le bruit
# residuel (articles qui matchent les keywords mais sont off-topic en realite).
# Appel batch par theme (jusqu'a 25 titres par requete). Cache via @st.cache_data
# de data_media_scout (slot-based), donc ne s'execute que 2x/jour.

_LLM_VALIDATE_CHUNK_SIZE = 25  # nb max d'articles par batch LLM (token budget)
# Nb d'appels LLM simultanes (validation + traduction). Modere volontairement :
# assez pour diviser le temps de refresh par ~4, sans saturer les rate limits
# free tier (le failover multi-cles absorbe les 429 residuels).
_LLM_PARALLEL_WORKERS = 4


def _llm_validate_chunk(items: list, theme_label: str) -> set:
    """Envoie un batch d'articles au LLM pour validation thematique.

    Args:
        items: liste de (df_index, title)
        theme_label: nom du theme cible (FR, ex: "Agrumes, Fruits rouges & Maraichage")

    Returns:
        Set des df_index juges pertinents par le LLM. Sur erreur LLM (rate limit
        total, JSON malformed), garde tous les indices (fallback safe -> evite
        de perdre des donnees).
    """
    if not items:
        return set()

    titles_listed = "\n".join(
        f"[{i}] {title}" for i, (_, title) in enumerate(items)
    )
    prompt = (
        "Tu es expert en classification editoriale pour LES DOMAINES AGRICOLES, "
        "groupe agro-industriel marocain.\n\n"
        f"Theme cible : « {theme_label} »\n\n"
        "Tu vas evaluer une liste d'articles (titres). Pour chacun, juge si le titre "
        "est PERTINENT pour ce theme (le sujet principal OU un sujet majeur de l'article).\n\n"
        "Sois INCLUSIF et raisonnable :\n"
        "  - GARDE les articles dont le titre evoque le theme, meme indirectement\n"
        "  - GARDE les articles generiques sur l'agriculture si le theme est T1 Agrumes/FR/Maraichage\n"
        "  - GARDE les articles generiques sur l'elevage si le theme est T2 Elevage (sauf hors-scope explicite)\n"
        "  - GARDE les articles sur food industry / distribution si le theme est T3 Produits laitiers/Epicerie\n"
        "  - GARDE les articles climat / eau / energie sous tout angle pour T4\n"
        "  - GARDE les articles sur normes / RSE / gouvernance / SST / certifications pour T5\n\n"
        "REJETTE uniquement les cas FLAGRANTS :\n"
        "  - Article sans aucun rapport identifiable avec le theme\n"
        "  - Article sur un sujet completement different (ex: politique pure dans T1 agricole)\n\n"
        "Articles a evaluer (numerotes [0]..[N-1]) :\n"
        f"{titles_listed}\n\n"
        "Reponds UNIQUEMENT en JSON strict, sans markdown ni explication :\n"
        '{"relevant":[<indices entiers des articles a garder>]}'
    )

    try:
        response = _groq_chat_with_failover(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            max_tokens=400,
            temperature=0.1,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            raw = m.group(0)
        data = json.loads(raw)
        relevant_ids = data.get("relevant", [])

        # Mappe les indices locaux [0..N-1] vers les df_index
        valid = set()
        for i in relevant_ids:
            try:
                i = int(i)
                if 0 <= i < len(items):
                    valid.add(items[i][0])
            except (TypeError, ValueError):
                continue
        return valid

    except Exception:
        # Fallback safe : garder TOUS les articles (ne pas perdre de donnees)
        return {df_idx for df_idx, _ in items}


def _llm_validate_themes(df):
    """Pour chaque article du df, demande au LLM si son titre est strictement lie
    au theme assigne. Drop les articles juges off-topic.

    Cette fonction est appelee dans data_media_scout (cache par creneau 07h/19h).
    Les chunks sont envoyes en PARALLELE (les appels LLM sont de l'I/O reseau :
    le GIL est libere) -> temps de refresh divise par ~len(workers) vs boucle
    sequentielle. Chaque chunk est independant ; les resultats sont fusionnes
    dans le thread principal (aucune ecriture concurrente sur df / keep_mask).
    Avec failover multi-cles, un rate limit sur une cle bascule sur la suivante.
    """
    if not _has_any_llm_key() or df.empty:
        return df

    # Construit la liste plate des chunks (theme, items) a valider
    chunks = []
    for theme in MEDIA_SCOUT_THEMES:
        theme_rows = df[df["Theme"] == theme]
        if theme_rows.empty:
            continue
        items = [
            (idx, str(row["Title"])[:200])
            for idx, row in theme_rows.iterrows()
        ]
        for chunk_start in range(0, len(items), _LLM_VALIDATE_CHUNK_SIZE):
            chunks.append((items[chunk_start:chunk_start + _LLM_VALIDATE_CHUNK_SIZE], theme))

    if not chunks:
        return df

    # Appels LLM en parallele (pool modere : respecte les rate limits free tier,
    # le failover multi-cles absorbe les 429 ponctuels).
    with ThreadPoolExecutor(max_workers=min(_LLM_PARALLEL_WORKERS, len(chunks))) as executor:
        results = list(executor.map(
            lambda cw: (cw[0], _llm_validate_chunk(cw[0], cw[1])), chunks
        ))

    # Fusion des verdicts dans le thread principal
    keep_mask = pd.Series(True, index=df.index)
    for chunk_items, valid_df_indices in results:
        for df_idx, _ in chunk_items:
            if df_idx not in valid_df_indices:
                keep_mask[df_idx] = False

    return df[keep_mask].copy()


# ─── Application des outputs LLM en francais ────────────────────────────────
# Marqueurs DISTINCTIFS francais (pas de faux-amis avec l'anglais)
# Note : on evite les suffixes generiques (-tion, -ment, -es) qui matchent
# aussi des mots anglais (regulation, government, laboratories...).
_FR_STRONG_TOKENS = (
    # Articles et determinants
    " le ", " la ", " les ", " un ", " une ", " du ", " des ", " de ",
    " au ", " aux ", " ce ", " cet ", " cette ", " ces ",
    # Pronoms et conjonctions
    " et ", " ou ", " ni ", " mais ", " donc ", " car ", " puis ",
    " qui ", " que ", " quoi ", " dont ", " ou ",
    # Prepositions distinctives
    " avec ", " pour ", " dans ", " sur ", " par ", " sans ", " sous ",
    " entre ", " vers ", " chez ", " contre ", " parmi ",
    # Verbes etre/avoir/faire conjugues
    " est ", " sont ", " etait ", " etaient ", " sera ", " seront ",
    " a ete ", " ont ete ", " etre ", " ete ",
    " ainsi ", " selon ", " aussi ", " encore ", " toujours ", " deja ",
    " plus ", " moins ", " tres ", " trop ",
    # Negation
    " ne ", " pas ", " plus ", " jamais ", " rien ", " aucun ",
    # Possessifs/demonstratifs
    " son ", " sa ", " ses ", " leur ", " leurs ", " notre ", " votre ",
    # Elisions (signature francaise tres forte)
    " l'", " d'", " s'", " c'", " j'", " m'", " t'", " n'", " qu'",
)

_EN_STRONG_TOKENS = (
    " the ", " of ", " and ", " is ", " are ", " was ", " were ",
    " with ", " for ", " on ", " by ", " to ", " this ", " that ",
    " these ", " those ", " has ", " have ", " had ", " will ",
    " would ", " could ", " should ", " between ", " through ",
    " during ", " however ", " regarding ", " whereas ", " among ",
    " their ", " they ", " them ", " which ", " from ", " into ",
    " upon ", " about ", " over ", " under ", " above ", " below ",
    " when ", " where ", " while ", " because ", " although ",
    " an ", " any ", " all ", " new ", " more ", " less ",
)


def _looks_french(text: str) -> bool:
    """Detecte si le texte est predominantely en francais.

    Heuristique : compare le nombre de tokens FR vs EN distinctifs +
    presence de diacritics francais (é/è/ê/à/ç/...). Texte court (<35 chars)
    -> True par defaut (titre).
    """
    if not text or len(text.strip()) < 35:
        return True
    raw = text.lower()
    # Bonus important si presence de diacritics francais (signature claire FR)
    has_diacritics = any(c in raw for c in "éèêëàâäîïôöùûüÿœæç")
    padded = " " + raw + " "
    fr = sum(1 for m in _FR_STRONG_TOKENS if m in padded)
    en = sum(1 for m in _EN_STRONG_TOKENS if m in padded)
    if has_diacritics:
        fr += 4
    return fr >= en


def _force_french_translate(text: str, kind: str = "phrase") -> str:
    """Traduit un texte en francais via LLM. Retourne l'original si echec.

    Args:
        text: texte a traduire (sera fallback inchange si echec ou deja FR)
        kind: 'titre' (court) ou 'phrase' (libre) ou 'puce' (puce factuelle)
    """
    if not text or not text.strip():
        return text
    if _looks_french(text):
        return text
    # Prompt minimal pour traduction rapide
    if kind == "titre":
        instruction = (
            "Traduis ce TITRE en francais correct, 10-14 mots maximum. "
            "Reponds UNIQUEMENT par le titre francais, rien d'autre."
        )
    elif kind == "puce":
        instruction = (
            "Traduis cette PUCE de veille en francais correct. "
            "Garde le prefixe (MA :, EU :, WW :) si present. "
            "Maximum 28 mots. Reponds UNIQUEMENT par la puce traduite, rien d'autre."
        )
    else:
        instruction = (
            "Traduis ce texte en francais correct, fluide, style journalistique. "
            "Garde la longueur similaire. Reponds UNIQUEMENT par la traduction, "
            "sans introduction ni guillemets."
        )
    try:
        resp = _llm_chat_with_failover(
            messages=[
                {"role": "system", "content": "Tu es un traducteur professionnel anglais->francais. Tu rends UNIQUEMENT du francais correct, jamais d'anglais."},
                {"role": "user", "content": f"{instruction}\n\nTexte:\n{text[:1500]}"},
            ],
            max_tokens=400,
            temperature=0.2,
        )
        translated = (resp.choices[0].message.content or "").strip()
        # Nettoie les guillemets d'enrobage parfois ajoutes par le LLM
        translated = translated.strip('"\'').strip()
        # Verifie que la traduction est plausible et bien en FR
        if translated and _looks_french(translated):
            return translated
    except Exception:
        pass
    return text


@st.cache_data(ttl=43200, show_spinner=False)
def translate_titles_to_french(titles: tuple) -> tuple:
    """Traduit en francais une petite liste de titres (saute ceux deja FR).

    Utilisee par le fallback d'affichage des cadres (liste de titres bruts) afin
    de GARANTIR le francais meme si la synthese LLM n'a pas pu s'executer et si
    la traduction au scraping a ete limitee (rate limit free tier).

    Cache par contenu (TTL 12h) -> chaque titre n'est traduit qu'une fois puis
    reutilise sur tous les reruns (auto-correction au fil des interactions).
    Fail-safe : retourne les titres originaux si aucune cle LLM ou echec.
    """
    if not _has_any_llm_key():
        return titles
    out = []
    for t in titles:
        t = str(t)
        if t and not _looks_french(t):
            out.append(_force_french_translate(t, kind="titre"))
        else:
            out.append(t)
    return tuple(out)


# Taille de lot pour la traduction batchee des articles (token budget)
_TRANSLATE_CHUNK_SIZE = 12


def _translate_articles_to_french(df):
    """Traduit en francais le Titre + Description des articles non-francophones.

    N'agit que sur les lignes dont le titre OU la description n'est pas deja en
    francais (sources institutionnelles EN : EFSA, DairyReporter, Climate Home,
    Carbon Brief, Fairtrade, etc. — environ 4% du corpus). Traduction par lots
    pour limiter le nombre d'appels LLM. Mis en cache via data_media_scout (slot).

    Fail-safe : sur erreur LLM (rate limit, JSON casse), garde le texte original.
    """
    if not _has_any_llm_key() or df.empty:
        return df

    # Identifie les lignes a traduire (titre OU description non-FR)
    todo = []
    for idx, row in df.iterrows():
        title = str(row.get("Title", ""))
        desc = str(row.get("Description", ""))
        title_non_fr = bool(title) and not _looks_french(title)
        desc_non_fr = len(desc) > 30 and not _looks_french(desc)
        if title_non_fr or desc_non_fr:
            todo.append((idx, title, desc))

    if not todo:
        return df

    def _translate_chunk(chunk):
        """Traduit un lot. Retourne [(df_idx, titre_fr, resume_fr), ...] —
        l'ecriture dans df se fait dans le thread principal (thread-safe)."""
        listed = "\n".join(
            f"[{i}] TITRE: {t[:200]}\n    RESUME: {d[:400]}"
            for i, (_, t, d) in enumerate(chunk)
        )
        prompt = (
            "Traduis en FRANCAIS correct le titre et le resume de chaque article "
            "ci-dessous. Conserve le sens et les chiffres. Si un champ est deja en "
            "francais, reformule-le legerement. Acronymes (ISO, RSE, EFSA, UE...) "
            "inchanges.\n\n"
            f"{listed}\n\n"
            "Reponds UNIQUEMENT en JSON strict, sans markdown :\n"
            '{"articles":[{"i":<num>,"titre":"<titre FR>","resume":"<resume FR>"}, ...]}'
        )
        out = []
        try:
            resp = _llm_chat_with_failover(
                messages=[
                    {"role": "system", "content": "Tu es un traducteur professionnel vers le francais. Tu rends UNIQUEMENT du francais correct."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1800,
                temperature=0.2,
            )
            raw = (resp.choices[0].message.content or "").strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)
            mm = re.search(r"\{[\s\S]*\}", raw)
            if mm:
                raw = mm.group(0)
            data = json.loads(raw)
            for art in data.get("articles", []):
                try:
                    i = int(art.get("i"))
                except (TypeError, ValueError):
                    continue
                if not (0 <= i < len(chunk)):
                    continue
                out.append((
                    chunk[i][0],
                    str(art.get("titre", "")).strip(),
                    str(art.get("resume", "")).strip(),
                ))
        except Exception:
            # Fail-safe : lot ignore -> textes originaux conserves
            pass
        return out

    chunks = [
        todo[start:start + _TRANSLATE_CHUNK_SIZE]
        for start in range(0, len(todo), _TRANSLATE_CHUNK_SIZE)
    ]
    # Traduction des lots en PARALLELE (I/O reseau -> GIL libere)
    with ThreadPoolExecutor(max_workers=min(_LLM_PARALLEL_WORKERS, len(chunks))) as executor:
        all_results = list(executor.map(_translate_chunk, chunks))

    # Application des traductions dans le thread principal
    for results in all_results:
        for df_idx, titre_fr, resume_fr in results:
            if titre_fr:
                df.loc[df_idx, "Title"] = titre_fr
            if resume_fr:
                df.loc[df_idx, "Description"] = resume_fr

    return df


@st.cache_data(ttl=1800, show_spinner=False)
def compute_signal_du_jour(articles_context: tuple) -> dict:
    """Identifie le 'Signal du jour' : l'article le plus critique a mettre en alerte forte.

    Args:
        articles_context: tuple de chaines decrivant les articles
            (Titre|Source|Date|Theme|Veille|Resume|Lien)

    Returns:
        {
          'eyebrow': str (ex: "Reglementaire · UE"),
          'headline': str,
          'body': str,
          'source_url': str (URL de l'article retenu, validee),
          'available': bool
        }
    """
    if not articles_context:
        return {"available": False}

    # Verifie qu'au moins UNE cle LLM (Google ou Groq) est configuree
    if not _has_any_llm_key():
        return {"available": False}

    # Liste blanche des URLs autorisees (anti-hallucination)
    allowed_urls = set()
    for entry in articles_context:
        m = re.search(r"Lien:\s*(https?://\S+)", entry)
        if m:
            allowed_urls.add(m.group(1).strip())

    articles_text = "\n".join(f"- {a}" for a in articles_context[:25])

    prompt = (
        "[LANGUE DE SORTIE = FRANCAIS UNIQUEMENT — instruction non-negociable] "
        "Tous les champs (eyebrow, headline, body) DOIVENT etre rediges en francais correct, "
        "MEME si l'article source est en anglais. Dans ce cas, traduis ET reformule en francais. "
        "Aucun mot anglais autorise dans la sortie sauf les acronymes etablis (UE, ISO, RSE, GHG, "
        "CSRD, BRC, etc.). JAMAIS de phrase en anglais.\n\n"
        "Tu es analyste de veille pour LES DOMAINES AGRICOLES (LDA), groupe agro-industriel "
        "marocain integrant : agrumes, fruits rouges, maraichage, elevage (ovin/bovin/caprin/"
        "volaille/aquaculture), produits laitiers, epicerie fine, exports UE/Afrique/Moyen-Orient. "
        "Standards QSE : GlobalGAP, IFS, BRC, FSSC 22000, ISO 14001/22000/26000/45001, Codex, "
        "ONSSA, Halal/Bio.\n\n"
        "Articles captures :\n\n"
        f"{articles_text}\n\n"
        "INSTRUCTION OBLIGATOIRE : tu DOIS choisir UN article parmi ceux fournis ci-dessus "
        "(jamais retourner vide). Choisis L'ARTICLE LE PLUS PERTINENT pour LDA.\n\n"
        "Criteres de selection (en ordre de priorite) :\n"
        "  1. Decision reglementaire / normative impactant exports ou production\n"
        "  2. Crise sanitaire / epizootie / retrait produit / alerte hydrique-climat\n"
        "  3. Accord commercial export, mouvement concurrentiel marque, audit QSE\n"
        "  4. Innovation technologique pertinente pour la filiere agro\n"
        "  5. A defaut, l'article LE PLUS RECENT du corpus\n\n"
        "Le BODY (3 a 4 phrases, 55-75 mots, EN FRANCAIS) :\n"
        "  - Decris d'abord ce qui se passe (acteur / decision / chiffre cle / date)\n"
        "  - Explique EXPLICITEMENT le mecanisme d'impact sur LDA (production vegetale, "
        "elevage, transformation, exports, supply chain, conformite QSE)\n"
        "  - Ne JAMAIS terminer par 'Impact sur LDA :' ou 'Impact :'. L'impact doit etre tisse "
        "naturellement dans le texte\n"
        "  - Pas de bullet points, pas de markdown, style journalistique fluide\n\n"
        "RAPPEL FINAL : tous les champs de sortie EN FRANCAIS, sans exception.\n\n"
        "Reponds en JSON STRICT (rien d'autre, pas de markdown). Tous les champs OBLIGATOIRES, "
        "AUCUN ne doit etre vide :\n"
        '{"eyebrow":"<Veille · Zone, EN FRANCAIS>",'
        '"headline":"<titre 10-14 mots EN FRANCAIS, oriente impact>",'
        '"body":"<3 a 4 phrases EN FRANCAIS, texte continu fluide, 55-75 mots>",'
        '"source_url":"<URL EXACTE choisie dans la liste fournie>"}'
    )
    # Fallback : prend le 1er article du corpus et tente une traduction LLM en francais
    def _parse_article_fields(article_str: str) -> dict:
        fields = {}
        for part in article_str.split(" | "):
            if ":" in part:
                key, val = part.split(":", 1)
                fields[key.strip().lower()] = val.strip()
        return fields

    def _build_fallback_signal():
        """Signal de repli (LLM principal en echec) avec FRANCAIS GARANTI :
        titre via le traducteur cache + garde-fou _looks_french, et a defaut une
        formulation francaise generique. Aucun texte anglais brut n'est affiche.
        """
        if not articles_context:
            return {"available": False}
        first = articles_context[0]
        fields = _parse_article_fields(first)
        headline_raw = fields.get("titre", "")
        resume_raw = _strip_rss_artifacts(fields.get("resume", ""))
        source = fields.get("source", "")
        theme = fields.get("theme", "")
        veille_short = fields.get("veille", "Informative").replace("Veille ", "")

        # Titre : traducteur cache fiable -> garde-fou -> sinon titre generique FR.
        headline_fr = ""
        if headline_raw:
            headline_fr = (translate_titles_to_french((headline_raw,))[0] or "").strip()
            if not _looks_french(headline_fr):
                headline_fr = _force_french_translate(headline_fr, kind="titre")
        # Garde STRICTE (preuve positive de francais) : _looks_french est neutre
        # sur un titre EN sans stopwords courants ("Investor climate group closes
        # down...") -> ici, derniere ligne de defense avant affichage, on exige
        # un diacritique OU un stopword FR, sinon titre generique francais.
        def _french_evidence(t: str) -> bool:
            raw = (t or "").lower()
            if any(c in raw for c in "éèêëàâäîïôöùûüÿœæç"):
                return True
            padded = " " + raw + " "
            return any(m in padded for m in _FR_STRONG_TOKENS)
        if not headline_fr or not _looks_french(headline_fr) or not _french_evidence(headline_fr):
            headline_fr = f"Signal de veille — {source}" if source else "Signal de veille du jour"
        headline_fr = headline_fr[:160]

        # Corps : resume traduit en FR ; si toujours pas francais -> phrase generique FR.
        body = ""
        if resume_raw:
            body_fr = _force_french_translate(resume_raw, kind="phrase")
            if _looks_french(body_fr):
                words = body_fr.split()
                body = " ".join(words[:70]) + ("…" if len(words) > 70 else "")
        if not body:
            ctx = f"Article identifié via {source} sur le périmètre {theme}. " if (source or theme) else ""
            body = ctx + (
                "Sujet à surveiller pour ses implications potentielles sur les activités "
                "du groupe (production, transformation, exports ou conformité)."
            )

        return {
            "eyebrow": f"{veille_short} · {theme}" if theme else veille_short,
            "headline": headline_fr,
            "body": body,
            "source_url": fields.get("lien", ""),
            "available": bool(headline_fr),
        }

    try:
        response = _groq_chat_with_failover(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Tu es analyste de veille pour LES DOMAINES AGRICOLES. "
                        "REGLE ABSOLUE : tous tes outputs DOIVENT etre en francais "
                        "correct, JAMAIS en anglais ni dans une autre langue. "
                        "Meme si les articles sources sont en anglais, tu TRADUIS et "
                        "REFORMULES en francais. Acronymes anglais autorises (ISO, RSE, "
                        "GHG, CSRD, BRC). Aucune phrase complete en anglais."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            model="llama-3.3-70b-versatile",
            max_tokens=500,
            temperature=0.4,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        # Extract JSON object even if wrapped in extra prose
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            raw = m.group(0)
        parsed = json.loads(raw)
        headline = str(parsed.get("headline", "")).strip()
        body = str(parsed.get("body", "")).strip()
        eyebrow = str(parsed.get("eyebrow", "")).strip()
        # Si le LLM a retourne JSON valide mais headline/body vides -> fallback
        if not headline or not body:
            return _build_fallback_signal()
        # GARDE-FOU LANGUE : verifie chaque champ + retraduit si pas en francais
        if not _looks_french(headline):
            headline = _force_french_translate(headline, kind="titre")
        if not _looks_french(body):
            body = _force_french_translate(body, kind="phrase")
        if eyebrow and not _looks_french(eyebrow):
            eyebrow = _force_french_translate(eyebrow, kind="titre")
        url = str(parsed.get("source_url", "")).strip()
        # Validation : l'URL doit etre dans la liste passee (anti-hallucination)
        if url and url not in allowed_urls:
            url = ""
        return {
            "eyebrow": eyebrow,
            "headline": headline,
            "body": body,
            "source_url": url,
            "available": True,
        }
    except Exception:
        # En cas d'erreur LLM (timeout, JSON parse, network, etc.) : fallback heuristique
        return _build_fallback_signal()
