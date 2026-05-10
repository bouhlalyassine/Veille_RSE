import base64
import json
import os
from pathlib import Path
import requests
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import html
import os
import re
import unicodedata
import warnings
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from groq import Groq

try:
    from bs4 import MarkupResemblesLocatorWarning
    warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)
except ImportError:
    pass


current_dir = Path(__file__).parent if "__file__" in locals() else Path.cwd()
TITLE = "Taskforce IA"

config_APP = current_dir / "files" / "hash_APP.yaml"
css_file = current_dir / "main.css"

img_logo_name_ico = current_dir / "files" / "logo_name.png"
img_logo_ico = str(img_logo_name_ico) if img_logo_name_ico.exists() else None
lottie_warning = current_dir / "files" / "warning.json"
lottie_robot = current_dir / "files" / "AI_Robot.json"


def get_base64_of_bin_file(bin_file):
    with open(bin_file, "rb") as f:
        return base64.b64encode(f.read()).decode()


def get_img(local_img_path, width):
    local_img_path = str(local_img_path)
    img_format = os.path.splitext(local_img_path)[-1].replace(".", "").lower()
    bin_str = get_base64_of_bin_file(local_img_path)
    return f"""
        <div style='display:flex; justify-content:center; align-items:center;'>
            <img src='data:image/{img_format};base64,{bin_str}' width='{width}'>
        </div>
    """


def load_lottiefile(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def load_lottieurl(url):
    response = requests.get(url, timeout=10)
    if response.status_code != 200:
        return None
    return response.json()


def load_css():
    with open(css_file, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def load_auth_config():
    with open(config_APP, encoding="utf-8") as file:
        return yaml.load(file, Loader=SafeLoader)


def build_authenticator(config):
    return stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
        config["preauthorized"],
    )


def require_authenticated_user():
    config = load_auth_config()
    authenticator = build_authenticator(config)
    load_css()

    name, authentication_status, username = authenticator.login("Login", "main")
    users = config["credentials"]["usernames"]

    if authentication_status is False:
        st.error("Username/password is incorrect")
        st.stop()

    if authentication_status is None:
        st.warning("Please enter your username and password")
        st.stop()

    if username not in users:
        st.warning("Vous n'avez pas acces a ce module")
        st.stop()

    return authenticator, name, username





MEDIA_SCOUT_ALLOWED_THEMES = [
    "RSE & Referentiels",
    "Eau",
    "Energie",
    "Environnement",
    "Autres",
]

MEDIA_SCOUT_SOURCE_CATALOG = [
    {"Journal": "AgriMaroc", "URL": "https://www.agrimaroc.ma/actualite-agricole/", "Couverture": "Maroc - eau, climat, agriculture durable"},
    {"Journal": "EcoActu", "URL": "https://ecoactu.ma/developpement-durable/", "Couverture": "Maroc - developpement durable, environnement, RSE"},
    {"Journal": "FNH - Finances News Hebdo", "URL": "https://fnh.ma/articles/developpement-durable", "Couverture": "Maroc - developpement durable, RSE"},
    {"Journal": "CGEM", "URL": "https://cgem.ma/actualites/", "Couverture": "Maroc - entreprises, RSE, climat des affaires"},
    {"Journal": "Le360", "URL": "https://fr.le360.ma/economie/", "Couverture": "Maroc - economie filtree energie/RSE/environnement"},
    {"Journal": "Le Vert", "URL": "https://levert.ma/category/transition-energetique/", "Couverture": "Maroc - transition energetique"},
    {"Journal": "Le Vert", "URL": "https://levert.ma/category/developpement-durable/", "Couverture": "Maroc - developpement durable"},
    {"Journal": "Medias24", "URL": "https://medias24.com/categorie/environnement/", "Couverture": "Maroc - environnement"},
    {"Journal": "MAP News", "URL": "https://www.mapnews.ma/fr/actualites/economie", "Couverture": "Maroc - institutions, energie, environnement"},
    {"Journal": "Ministere Transition Energetique", "URL": "https://www.mem.gov.ma/Pages/actualites.aspx", "Couverture": "Maroc - energie, mines, transition"},
    {"Journal": "Ministere Equipement et Eau", "URL": "https://www.equipement.gov.ma/Actualites/Pages/Actualites.aspx", "Couverture": "Maroc - eau, barrages, infrastructures"},
    {"Journal": "Departement Environnement", "URL": "https://www.environnement.gov.ma/fr/actualites", "Couverture": "Maroc - environnement, climat"},
    {"Journal": "Actu-Environnement", "URL": "https://www.actu-environnement.com/actualites/", "Couverture": "France/International - eau, energie, environnement, RSE"},
    {"Journal": "Novethic", "URL": "https://www.novethic.fr/actualite/rse", "Couverture": "France/Europe - RSE, CSRD, finance durable"},
    {"Journal": "UN Global Compact", "URL": "https://unglobalcompact.org/news", "Couverture": "Officiel - RSE, droits humains, anti-corruption, SDGs, Communication on Progress"},
    {"Journal": "OECD RBC", "URL": "https://www.oecd.org/en/topics/responsible-business-conduct.html", "Couverture": "Officiel - conduite responsable, devoir de vigilance, lignes directrices OCDE"},
    {"Journal": "ISO News", "URL": "https://www.iso.org/news.html", "Couverture": "Officiel - normes ISO, durabilite, ISO 26000, ISO 14001"},
    {"Journal": "ISO 26000", "URL": "https://www.iso.org/iso-26000-social-responsibility.html", "Couverture": "Officiel - responsabilite societale, ISO 26000"},
    {"Journal": "ISO 14001", "URL": "https://www.iso.org/standard/14001", "Couverture": "Officiel - ISO 14001, systeme de management environnemental, dechets, performance environnementale"},
    {"Journal": "ISO 14000 Family", "URL": "https://www.iso.org/iso-14001-environmental-management.html", "Couverture": "Officiel - famille ISO 14000, ISO 14001, management environnemental, dechets"},
    {"Journal": "AFNOR ISO 14001", "URL": "https://www.afnor.org/actualites/protection-environnement/nouvelle-norme-iso-14001/", "Couverture": "France - ISO 14001 version 2026, management environnemental, dechets, cycle de vie"},
    {"Journal": "AFNOR Certification ISO 14001", "URL": "https://certification.afnor.org/environnement/certification-afaq-iso-14001", "Couverture": "France - certification ISO 14001, performance environnementale, recyclage, valorisation des dechets"},
    {"Journal": "EU EMAS", "URL": "https://green-business.ec.europa.eu/eco-management-and-audit-scheme-emas_en", "Couverture": "Officiel UE - EMAS, management environnemental, audit, reporting environnemental"},
    {"Journal": "Basel Convention", "URL": "https://www.basel.int/Implementation/Publications/LatestNews/tabid/2310/Default.aspx", "Couverture": "Officiel - dechets dangereux, conventions internationales, mouvements transfrontieres de dechets"},
    {"Journal": "Ellen MacArthur Foundation", "URL": "https://www.ellenmacarthurfoundation.org/news", "Couverture": "International - economie circulaire, dechets, referentiels et cadres circularite"},
    {"Journal": "B Lab Global", "URL": "https://www.bcorporation.net/en-us/news/", "Couverture": "Officiel - B Corp, standards B Lab, entreprises a impact"},
    {"Journal": "B Lab Standards", "URL": "https://www.bcorporation.net/en-us/standards/", "Couverture": "Officiel - referentiel B Corp, standards sociaux/environnementaux/gouvernance"},
    {"Journal": "EcoVadis", "URL": "https://ecovadis.com/newsroom/", "Couverture": "International - notation RSE, achats responsables, supply chain ESG"},
    {"Journal": "PRI", "URL": "https://public.unpri.org/news-and-press", "Couverture": "Officiel - investissement responsable, ESG, stewardship"},
    {"Journal": "AMMC Finance Durable", "URL": "https://www.ammc.ma/fr/node/45550", "Couverture": "Maroc - finance durable, reporting ESG, marches de capitaux"},
    {"Journal": "GRI", "URL": "https://www.globalreporting.org/news/news-center/", "Couverture": "Officiel - GRI Standards"},
    {"Journal": "EFRAG", "URL": "https://www.efrag.org/en/news-and-calendar/news", "Couverture": "Officiel - CSRD, ESRS"},
    {"Journal": "IFRS / ISSB", "URL": "https://www.ifrs.org/news-and-events/updates/issb/", "Couverture": "Officiel - IFRS S1/S2, ISSB"},
    {"Journal": "IFRS / SASB", "URL": "https://www.ifrs.org/issued-standards/sasb-standards/", "Couverture": "Officiel - SASB Standards, IFRS S1/S2, reporting sectoriel"},
    {"Journal": "ESMA Sustainable Finance", "URL": "https://www.esma.europa.eu/press-news/esma-news", "Couverture": "Officiel UE - finance durable, ESG, supervision, reporting"},
    {"Journal": "European Commission Sustainable Finance", "URL": "https://finance.ec.europa.eu/sustainable-finance_en", "Couverture": "Officiel UE - taxonomie, CSRD, finance durable, SFDR"},
    {"Journal": "TNFD", "URL": "https://tnfd.global/news/", "Couverture": "Officiel - nature, biodiversite"},
    {"Journal": "SBTi", "URL": "https://sciencebasedtargets.org/news", "Couverture": "Officiel - climat, objectifs SBT"},
    {"Journal": "CDP", "URL": "https://www.cdp.net/en/articles", "Couverture": "Officiel - reporting climat/eau/forets"},
    {"Journal": "GHG Protocol", "URL": "https://ghgprotocol.org/blog-type/press-release", "Couverture": "Officiel - comptabilite carbone, Scope 1/2/3"},
    {"Journal": "UNEP", "URL": "https://www.unep.org/news-and-stories", "Couverture": "International - environnement, climat, biodiversite"},
    {"Journal": "WRI", "URL": "https://www.wri.org/news", "Couverture": "International - climat, ressources, eau, energie"},
    {"Journal": "IEA", "URL": "https://www.iea.org/news", "Couverture": "International - energie, transition energetique"},
    {"Journal": "IRENA", "URL": "https://www.irena.org/News", "Couverture": "International - energies renouvelables"},
    {"Journal": "MAP Ecology", "URL": "https://mapecology.ma/", "Couverture": "Maroc - ecologie, environnement, climat"},
    {"Journal": "Le Matin", "URL": "https://lematin.ma/economie", "Couverture": "Maroc - climat, eau, energie, transition"},
]

MEDIA_SCOUT_URLS = [source["URL"] for source in MEDIA_SCOUT_SOURCE_CATALOG]
MEDIA_SCOUT_URL_TO_NAME = {source["URL"]: source["Journal"] for source in MEDIA_SCOUT_SOURCE_CATALOG}

MEDIA_SCOUT_REFERENTIAL_SOURCE_DOMAINS = [
    "globalreporting.org",
    "efrag.org",
    "ifrs.org",
    "tnfd.global",
    "cdp.net",
    "sciencebasedtargets.org",
    "ghgprotocol.org",
    "unglobalcompact.org",
    "oecd.org",
    "iso.org",
    "afnor.org",
    "certification.afnor.org",
    "green-business.ec.europa.eu",
    "basel.int",
    "ellenmacarthurfoundation.org",
    "bcorporation.net",
    "ecovadis.com",
    "unpri.org",
    "ammc.ma",
    "esma.europa.eu",
    "finance.ec.europa.eu",
]

MEDIA_SCOUT_THEME_RULES = {
    "Referentiels RSE": {
        "strong": [
            "gri", "csrd", "esrs", "efrag", "issb", "ifrs s1", "ifrs s2", "tnfd", "tcfd",
            "ghg protocol", "cdp", "sbti", "iso 14001", "iso 50001", "iso 26000",
            "b corp", "ecovadis", "taxonomie europeenne", "taxonomie verte", "sfdr",
            "devoir de vigilance", "supply chain act", "lksg", "csddd",
            "pacte mondial", "global compact", "ungc",
        ],
        "medium": [
            "reporting", "assurance", "materiality", "standards", "norme", "referentiel",
            "indicateur esg", "notation esg", "due diligence", "certification", "labellisation",
            "audit esg", "reporting durabilite", "rapport durabilite", "reporting extra-financier",
            "divulgation", "disclosure", "transparence extra-financiere",
            "taxonomie", "classification durable", "label rse", "label vert",
            "notation extra-financiere", "agence de notation", "score esg",
        ],
        "weak": [
            "scope 1", "scope 2", "scope 3", "kpi", "indicateur", "benchmark",
            "standard", "framework", "conformite",
        ],
    },
    "Eau": {
        "strong": [
            "stress hydrique", "ressources en eau", "dessalement", "barrage", "secheresse",
            "nappe phreatique", "water scarcity", "gestion de l'eau", "eau potable",
            "assainissement", "qualite de l'eau", "penurie d'eau", "gestion hydraulique",
            "ressource hydrique", "eau souterraine", "retenue d'eau", "transfert d'eau",
            "bassin hydraulique", "amenagement hydraulique", "plan national de l'eau",
            "crise hydrique", "deficit hydrique", "mobilisation de l'eau",
            "retenue collinaire", "transfert inter-bassins", "programme eau",
            "penurie eau", "acces a l'eau potable",
        ],
        "medium": [
            "hydrique", "irrigation", "nappe", "drought", "inondation", "precipitation",
            "fleuve", "riviere", "lac", "bassin versant", "aquifere", "pluvial",
            "debordement", "crue", "hydraulique", "oued", "ressource en eau",
            "approvisionnement en eau", "distribution d'eau", "traitement de l'eau",
            "epuration", "debit", "pluviometrie", "reseau d'eau", "branchement eau",
            "desserte en eau", "pompage", "station d'epuration", "station de traitement",
            "onee", "onep", "amenagement hydro",
        ],
        "weak": [
            "eau", "water", "pluie", "hydrologie", "meteorologie", "pluies",
        ],
    },
    "Energie": {
        "strong": [
            "transition energetique", "efficacite energetique", "energies renouvelables",
            "renewable energy", "hydrogene vert", "panneau solaire", "panneaux solaires",
            "eolienne", "eoliennes", "photovoltaique", "mix energetique", "stockage energie",
            "energie solaire", "energie eolienne", "energie propre", "clean energy",
            "independance energetique", "souverainete energetique", "decarbonation energetique",
            "reseau electrique intelligent", "smart grid", "centrale solaire",
            "parc solaire", "parc eolien", "centrale eolienne", "energie hydraulique",
            "hydroelectricite", "puissance renouvelable installee",
        ],
        "medium": [
            "energie", "energetique", "electricite", "renouvelable", "solaire", "hydrogene",
            "energy", "solar", "wind", "centrale electrique", "puissance installee",
            "capacite installee", "kwh", "mwh", "gwh", "twh", "biogaz", "biomasse",
            "petrole", "gaz naturel", "charbon", "decarbonation", "electrification",
            "interconnexion electrique", "reseau de transport", "tarif electricite",
            "facture energetique", "consommation energetique", "production electrique",
            "offshore", "onshore", "watt", "megawatt", "gigawatt",
            "masen", "noor", "onee", "iresen", "aderee",
            "combustible", "carburant", "fossile", "nucleaire", "thermique",
            "puissance installee", "capacite energetique", "transition bas carbone",
            "reseau electrique", "infrastructure energetique", "power",
        ],
        "weak": [
            "led", "kilowatt", "turbine", "generateur", "raccordement electrique",
            "compteur", "voltage",
        ],
    },
    "Environnement": {
        "strong": [
            "changement climatique", "climate change", "biodiversite", "pollution",
            "dechets", "recyclage", "neutralite carbone", "rechauffement climatique",
            "deforestation", "qualite de l'air", "bilan carbone", "empreinte carbone",
            "zero dechet", "economie circulaire", "accord de paris", "cop",
            "perte de biodiversite", "espece menacee", "extinction", "desertification",
            "microplastique", "pollution plastique", "gaz a effet de serre",
            "transition ecologique", "neutralite climatique", "net zero",
            "carbon neutral", "economie verte", "green economy",
            "pollution atmospherique", "pollution marine", "pollution des sols",
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
            "programme forestier", "hceflcd", "developpement durable",
        ],
        "weak": [
            "durable", "durabilite", "ecologique", "vert", "verdure", "sustainable",
        ],
    },
    "Responsabilite Sociale des Entreprises": {
        "strong": [
            "responsabilite sociale", "responsabilite societale", "rse", "csr", "esg",
            "devoir de vigilance", "rapport rse", "strategie rse", "politique rse",
            "droits humains", "droits fondamentaux", "travail decent", "travail force",
            "chaine d'approvisionnement responsable", "achats responsables",
            "green bond", "obligation verte", "finance verte", "investissement vert",
            "indice de durabilite", "maroc rse", "cgem rse",
        ],
        "medium": [
            "gouvernance durable", "conditions de travail", "sante securite",
            "egalite professionnelle", "inclusion", "diversite",
            "parite", "formation professionnelle", "impact social",
            "parties prenantes", "audit social", "bilan social", "bien-etre",
            "qualite de vie au travail", "qvt", "engagement des salaries",
            "mecenat", "economie sociale", "impact positif",
            "entreprise responsable", "finance durable", "investissement responsable",
            "isr", "impact investing", "entreprise citoyenne", "engagement societal",
            "rapport de durabilite", "communication rse", "programme rse",
            "charte sociale", "accord collectif", "dialogue social",
        ],
        "weak": [
            "gouvernance", "social", "solidarite", "equite", "ethique", "engagement",
        ],
    },
}

# Sources strictement mono-thematiques : fallback quand aucun mot-cle ne matche.
# Critere d'inclusion : la source ne couvre QU'UN seul theme (organisme dedie ou URL specialisee).
# A NE PAS inclure : sources multi-thematiques (AgriMaroc=agriculture large, Actu-Environnement,
# WRI, CGEM, Ministere Equipement et Eau qui couvre aussi l'infrastructure, etc.)
MEDIA_SCOUT_FORCED_SOURCE_THEMES = {
    "Ministere Transition Energetique": "Energie",        # mem.gov.ma : 100% energie/mines
    "Departement Environnement":        "Environnement",  # environnement.gov.ma : 100% env
    "IEA":                              "Energie",        # International Energy Agency
    "IRENA":                            "Energie",        # International Renewable Energy
    "UNEP":                             "Environnement",  # UN Environment Programme
    "MAP Ecology":                      "Environnement",  # site dedie ecologie
    "Novethic":                         "RSE & Referentiels",  # /actualite/rse : 100% RSE
    "UN Global Compact":                "RSE & Referentiels",
    "OECD RBC":                         "RSE & Referentiels",
    "ISO 26000":                        "RSE & Referentiels",
    "ISO 14001":                        "RSE & Referentiels",
    "ISO 14000 Family":                 "RSE & Referentiels",
    "AFNOR ISO 14001":                  "RSE & Referentiels",
    "AFNOR Certification ISO 14001":     "RSE & Referentiels",
    "EU EMAS":                          "RSE & Referentiels",
    "Basel Convention":                 "RSE & Referentiels",
    "Ellen MacArthur Foundation":        "RSE & Referentiels",
    "B Lab Global":                     "RSE & Referentiels",
    "B Lab Standards":                  "RSE & Referentiels",
    "EcoVadis":                         "RSE & Referentiels",
    "PRI":                              "RSE & Referentiels",
    "AMMC Finance Durable":             "RSE & Referentiels",
    "IFRS / SASB":                      "RSE & Referentiels",
    "ESMA Sustainable Finance":         "RSE & Referentiels",
    "European Commission Sustainable Finance": "RSE & Referentiels",
}

MEDIA_SCOUT_SOURCE_THEME_HINTS = {
    "Eau": [
        "eau", "water", "equipement.gov.ma", "hydrique",
        "agrimaroc", "irrigation", "barrage",
    ],
    "Energie": [
        "energie", "energy", "iea", "irena", "transition-energetique", "mem.gov.ma",
        "le vert", "levert", "energetique", "renouvelable", "masen", "noor",
    ],
    "Environnement": [
        "environnement", "environment", "ecology", "climate", "unep", "wri", "mapecology",
        "le vert", "levert", "medias24", "actu-environnement", "actu environnement",
        "map ecology", "developpement-durable", "developpement durable",
    ],
    "Responsabilite Sociale des Entreprises": [
        "rse", "csr", "esg", "cgem", "novethic", "ecoactu", "fnh", "finances news",
        "unglobalcompact", "global compact", "oecd", "responsible business conduct",
        "bcorporation", "b corp", "b lab", "ecovadis", "unpri", "pri", "ammc",
    ],
    "Referentiels RSE": [
        "globalreporting", "efrag", "ifrs", "tnfd", "cdp", "sciencebasedtargets", "ghgprotocol",
        "iso", "iso 26000", "iso 14001", "sasb", "issb", "esma", "taxonomy", "taxonomie",
        "sfdr", "csrd", "esrs", "finance.ec.europa", "sustainable finance",
        "iso 14000", "management environnemental", "systeme de management environnemental",
        "environmental management system", "emas", "afnor", "basel convention",
        "convention de bale", "dechets dangereux", "waste management standard",
        "audit environnemental", "certification environnementale", "cycle de vie",
        "circular economy framework", "economie circulaire", "referentiel dechets",
        "norme dechets", "valorisation des dechets", "recyclage",
    ],
}

MEDIA_SCOUT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    )
}


def _clean_media_text(value):
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


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


def _article_record(source_url, title, description, link, date_value):
    title = _clean_media_text(title)
    description = _clean_media_text(description)
    link = urljoin(source_url, _clean_media_text(link))
    date_text = _normalize_media_date(date_value) or _date_from_url(link)
    if not title or len(title) < 8 or not link or not date_text:
        return None
    return {
        "Date": date_text,
        "Title": title,
        "Description": description,
        "Link": link,
        "Website_name": _source_name_from_url(source_url, link),
    }


def _fetch_media_url(url):
    try:
        response = requests.get(url, headers=MEDIA_SCOUT_HEADERS, timeout=14)
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


def _extract_card_date(card):
    time_node = card.find("time")
    if time_node:
        return time_node.get("datetime") or time_node.get_text(" ", strip=True)
    for class_fragment in ["date", "time", "published", "meta", "itemdate"]:
        date_node = card.find(attrs={"class": re.compile(class_fragment, re.IGNORECASE)})
        if date_node:
            return date_node.get_text(" ", strip=True)
    return ""


def _extract_html_articles(soup, source_url):
    articles = []
    selectors = [
        "article",
        "div.timeline-content",
        "div.article-list-item",
        "div.card",
        "div.post",
        "div[class*='article']",
        "div[class*='news']",
        "li[class*='article']",
        "li[class*='news']",
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


def _keyword_in_media_text(text, keyword):
    keyword = _fold_media_text(keyword)
    return bool(keyword and re.search(r"(?<!\w)" + re.escape(keyword) + r"(?!\w)", text))


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
    if result["strong_hits"] > 0:
        return result["score"] >= 4
    if result["title_medium_hits"] >= 1:
        return result["score"] >= 3
    if result["medium_hits"] >= 2:
        return result["score"] >= 4
    # Avec source hint : un seul mot-cle medium en body (2 pts) ou deux weak (2 pts) suffisent
    if source_hint:
        return result["score"] >= 2
    return False


def _assign_media_theme(row):
    website_name = str(row.get("Website_name", ""))
    link_host = urlparse(str(row.get("Link", ""))).netloc.lower().replace("www.", "")
    if any(domain in link_host for domain in MEDIA_SCOUT_REFERENTIAL_SOURCE_DOMAINS):
        return "RSE & Referentiels"

    source_context = _fold_media_text(" ".join([website_name, str(row.get("Link", ""))]))
    title_text = _fold_media_text(row.get("Title", ""))
    body_text = _fold_media_text(" ".join([str(row.get("Description", "")), website_name, str(row.get("Link", ""))]))

    candidates = {}
    for theme in MEDIA_SCOUT_THEME_RULES:
        result = _score_media_theme(title_text, body_text, theme)
        if _has_enough_theme_signal(result, _source_has_theme_hint(source_context, theme)):
            candidates[theme] = result

    if not candidates:
        # Fallback : thematique forcee pour les sources 100% specialisees
        forced = MEDIA_SCOUT_FORCED_SOURCE_THEMES.get(website_name)
        return forced if forced else "Autres"

    best = max(candidates.items(), key=lambda item: (item[1]["strong_hits"], item[1]["medium_hits"], item[1]["score"]))[0]
    if best in ("Referentiels RSE", "Responsabilite Sociale des Entreprises"):
        return "RSE & Referentiels"
    return best


@st.cache_data(ttl=1800, show_spinner=False)
def data_media_scout(urls=None):
    urls = urls or MEDIA_SCOUT_URLS
    source_urls = [source["URL"] if isinstance(source, dict) else source for source in urls]

    data = []
    for source_url in source_urls:
        data.extend(_scrape_media_source(source_url))

    columns = ["Date", "Title", "Description", "Link", "Website_name", "Theme"]
    if not data:
        empty_df = pd.DataFrame(columns=columns)
        empty_df["Date"] = pd.to_datetime(empty_df["Date"])
        return empty_df

    df = pd.DataFrame(data).astype(str)
    df["Date"] = df["Date"].apply(_normalize_media_date)
    df["Date"] = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors="coerce")
    df = df.dropna(subset=["Date", "Title", "Link"])
    df["Theme"] = df.apply(_assign_media_theme, axis=1)
    df = df[df["Theme"].isin(MEDIA_SCOUT_ALLOWED_THEMES)]

    if df.empty:
        empty_df = pd.DataFrame(columns=columns)
        empty_df["Date"] = pd.to_datetime(empty_df["Date"])
        return empty_df

    df["_title_key"] = df["Title"].apply(_fold_media_text)
    df["_link_key"] = df["Link"].str.replace(r"(\?|#).*$", "", regex=True)
    df = df.drop_duplicates(subset=["_link_key"])
    df = df.drop_duplicates(subset=["_title_key"])
    df = df.drop(columns=["_title_key", "_link_key"])
    df["Theme"] = pd.Categorical(df["Theme"], categories=MEDIA_SCOUT_ALLOWED_THEMES, ordered=True)
    df = df.sort_values(["Theme", "Date"], ascending=[True, False])
    return df[columns]


MEDIA_SCOUT_WEATHER_CITIES = {
    "Oujda":      (34.68, -1.91),
    "Fes":        (34.04, -5.00),
    "Casablanca": (33.59, -7.62),
    "Marrakech":  (31.63, -8.00),
    "Agadir":     (30.43, -9.60),
    "Dakhla":     (23.71, -15.94),
}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_scout_weather() -> dict:
    """Temperatures min/max et pluviometrie du jour via Open-Meteo."""
    results = {}
    for city, (lat, lon) in MEDIA_SCOUT_WEATHER_CITIES.items():
        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}"
                f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
                f"&timezone=Africa%2FCasablanca&forecast_days=1"
            )
            resp = requests.get(url, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            results[city] = {
                "min":    round(data["daily"]["temperature_2m_min"][0]),
                "max":    round(data["daily"]["temperature_2m_max"][0]),
                "precip": round(data["daily"]["precipitation_sum"][0], 1),
            }
        except Exception:
            pass
    return results


def _get_groq_api_key():
    try:
        value = st.secrets.get("GROQ_API_KEY")
        if value:
            return value
    except Exception:
        pass
    return os.getenv("GROQ_API_KEY")


@st.cache_data(ttl=1800, show_spinner=False)
def summarize_scout_themes(theme_articles: dict) -> dict:
    """Genere une synthese KPI-first par thematique a partir du contenu article disponible.

    Args:
        theme_articles: {theme: tuple of article context strings}

    Returns:
        {theme: summary string}
    """
    api_key = _get_groq_api_key()
    if not api_key:
        return {}

    client = Groq(api_key=api_key)
    summaries = {}

    for theme, articles in theme_articles.items():
        if not articles:
            continue
        articles_text = "\n".join(f"- {article}" for article in articles)
        prompt = (
            f"Voici {len(articles)} articles recents sur la thematique \"{theme}\". "
            "Chaque entree contient le titre, la source, la date et le resume/description disponible :\n"
            f"{articles_text}\n\n"
            "Produis une synthese en francais sous forme de 2 a 3 bullet points courts, centres sur les points "
            "importants ou signaux recurrents qui ressortent du contenu global des articles, et non sur un seul titre isole. "
            "Priorise les KPIs, chiffres, dates, acteurs concernes, evolutions, tendances mesurables ou signaux operationnels "
            "lorsqu'ils existent, mais ne cree pas de bullet point sur le volume d'articles analyses. "
            "Si aucun chiffre explicite n'est disponible, formule les points comme des indicateurs qualitatifs observables, "
            "sans inventer de donnees. "
            "Format obligatoire: chaque ligne commence par '- '. Pas d'introduction, pas de conclusion."
        )
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=180,
                temperature=0.3,
            )
            summaries[theme] = response.choices[0].message.content.strip()
        except Exception:
            summaries[theme] = ""

    return summaries
