#  .venv/Scripts/Activate.ps1
#  python -m streamlit run app.py
#  git add .    # git commit -m "Màj"   # git push -u origin master


from datetime import date, timedelta
from html import escape

import pandas as pd
import streamlit as st
from streamlit_lottie import st_lottie

from Settings import require_authenticated_user, load_lottiefile, lottie_robot
from Settings import (
    MEDIA_SCOUT_SOURCE_CATALOG,
    MEDIA_SCOUT_URLS,
    data_media_scout,
    summarize_scout_themes,
)


st.set_page_config(layout="wide")

authenticator, name, username = require_authenticated_user()

with st.sidebar:
    st.markdown(
        "<h1 style='text-align:center; font-size:34px; font-weight:bold; padding:0rem 0px 0.15rem; margin-bottom:0.15rem'>Veille RSE/ESG</h1>",
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.markdown("<div class='thick-divider'></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    today = date.today()
    days_ago = today - timedelta(days=2)
    date_select = st.date_input(
        label="Selectionner la periode souhaitee :",
        value=(days_ago, today),
        max_value=today,
        min_value=today - timedelta(days=90),
        label_visibility="collapsed",
        format="DD/MM/YYYY",
        help="Selectionner la periode souhaitee",
    )
    answer_togg = st.toggle("Activate Agent", key="Search_togg", width="stretch")

    st.markdown("<br>", unsafe_allow_html=True)
    st_lottie(load_lottiefile(lottie_robot), speed=1, reverse=False, loop=True, quality="high", height=200)
    st.markdown("<br><br>", unsafe_allow_html=True)



#st.markdown("<div class='thick-divider'></div>", unsafe_allow_html=True)

# ── Configuration visuelle de la synthese interactive ─────────────────────────
_THEME_EMOJI = {
    "RSE & Referentiels": "🏛️",
    "Eau":                "💧",
    "Energie":            "⚡",
    "Environnement":      "🌿",
    #"Autres":             "",
}

_MOIS_FR = {
    "January": "Janvier", "February": "Fevrier", "March": "Mars",
    "April": "Avril", "May": "Mai", "June": "Juin",
    "July": "Juillet", "August": "Aout", "September": "Septembre",
    "October": "Octobre", "November": "Novembre", "December": "Decembre",
}

def _scout_css():
    return """
<style>
div[data-testid="stAppViewContainer"] main .block-container {
    padding-top: 0rem !important;
}
.scout-main-grid {
    max-width: 1180px;
    margin: -1.75rem auto 0;
}
div[data-testid="stElementContainer"]:has(.scout-card-marker) {
    display: none !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.scout-card-marker),
div[data-testid="stVerticalBlockBorderWrapper"]:has(.scout-card-marker) div[data-testid="stVerticalBlock"] {
    background: transparent !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.scout-event-marker) {
    min-height: 88px;
    padding: 0.65rem 0.9rem !important;
    border: 1px solid rgba(56, 142, 60, 0.28) !important;
    border-radius: 20px !important;
    background:
        radial-gradient(circle at top right, rgba(67, 160, 71, 0.28), transparent 34%),
        linear-gradient(135deg, #f2fbef 0%, #dff3e4 100%) !important;
    box-shadow: 0 14px 30px rgba(1, 67, 128, 0.08) !important;
    margin-bottom: 0.45rem !important;
}
.st-key-scout-card-event,
.st-key-scout-card-rse,
.st-key-scout-card-eau,
.st-key-scout-card-energie,
.st-key-scout-card-environnement {
    border-radius: 20px !important;
    box-shadow: 0 10px 24px rgba(16, 37, 30, 0.06) !important;
    transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
}
.st-key-scout-card-event {
    padding-bottom: 1.25rem !important;
}
.st-key-scout-card-event,
.st-key-scout-card-event > div,
.st-key-scout-card-event [data-testid="stVerticalBlock"],
.st-key-scout-card-event [data-testid="stVerticalBlockBorderWrapper"] {
    background: #efe2ff !important;
    border-color: rgba(126, 87, 194, 0.32) !important;
}
.st-key-scout-card-rse,
.st-key-scout-card-rse > div,
.st-key-scout-card-rse [data-testid="stVerticalBlock"],
.st-key-scout-card-rse [data-testid="stVerticalBlockBorderWrapper"] {
    background: #e7f0ff !important;
}
.st-key-scout-card-eau,
.st-key-scout-card-eau > div,
.st-key-scout-card-eau [data-testid="stVerticalBlock"],
.st-key-scout-card-eau [data-testid="stVerticalBlockBorderWrapper"] {
    background: #dcf3fb !important;
}
.st-key-scout-card-energie,
.st-key-scout-card-energie > div,
.st-key-scout-card-energie [data-testid="stVerticalBlock"],
.st-key-scout-card-energie [data-testid="stVerticalBlockBorderWrapper"] {
    background: #ffedc9 !important;
}
.st-key-scout-card-environnement,
.st-key-scout-card-environnement > div,
.st-key-scout-card-environnement [data-testid="stVerticalBlock"],
.st-key-scout-card-environnement [data-testid="stVerticalBlockBorderWrapper"] {
    background: #e1f3e2 !important;
}
.st-key-scout-card-event:hover,
.st-key-scout-card-rse:hover,
.st-key-scout-card-eau:hover,
.st-key-scout-card-energie:hover,
.st-key-scout-card-environnement:hover {
    transform: translateY(-2px);
    border-color: rgba(13, 92, 107, 0.42) !important;
    box-shadow: 0 15px 32px rgba(16, 37, 30, 0.11) !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.scout-event-marker) div[data-testid="stButton"] > button[kind="tertiary"] {
    margin-bottom: 0.35rem !important;
}
.scout-event-title {
    color: #0d5c6b;
    font-size: 13px;
    font-weight: 850;
    letter-spacing: 0.08em;
    margin-bottom: 0.25rem;
    text-transform: uppercase;
}
.scout-event-list {
    display: grid;
    gap: 0.35rem;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    padding-bottom: 0.75rem;
}
.scout-event-item {
    background: rgba(255, 255, 255, 0.62);
    border: 1px solid rgba(13, 92, 107, 0.1);
    border-radius: 13px;
    padding: 0.45rem 0.55rem;
}
.scout-event-date {
    color: #0d5c6b;
    font-size: 12px;
    font-weight: 850;
    text-transform: uppercase;
}
.scout-event-name {
    color: #10251e;
    font-size: 14px;
    font-weight: 800;
    line-height: 1.28;
}
.scout-event-meta {
    color: #60716b;
    font-size: 12px;
    font-weight: 650;
}
.scout-calendar-grid {
    display: grid;
    gap: 0.55rem;
    grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
}
.scout-calendar-card {
    border: 1px solid rgba(13, 92, 107, 0.14);
    border-radius: 16px;
    background: #ffffff;
    padding: 0.75rem;
}
.scout-calendar-card a,
.scout-event-item a {
    color: inherit !important;
    display: block;
    text-decoration: none !important;
}
.scout-calendar-card a:hover .scout-event-name,
.scout-event-item a:hover .scout-event-name {
    color: #0d5c6b;
    text-decoration: underline;
    text-decoration-color: rgba(13, 92, 107, 0.45);
    text-underline-offset: 3px;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.scout-theme-rse),
div[data-testid="stVerticalBlockBorderWrapper"]:has(.scout-theme-eau),
div[data-testid="stVerticalBlockBorderWrapper"]:has(.scout-theme-energie),
div[data-testid="stVerticalBlockBorderWrapper"]:has(.scout-theme-environnement) {
    min-height: 232px;
    padding: 0.95rem 1.05rem !important;
    border: 1px solid rgba(56, 142, 60, 0.22) !important;
    border-radius: 20px !important;
    box-shadow: 0 10px 24px rgba(16, 37, 30, 0.06) !important;
    transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.scout-theme-rse) {
    background:
        radial-gradient(circle at top left, rgba(1, 67, 128, 0.18), transparent 36%),
        linear-gradient(135deg, #f0f6ff 0%, #dfeaff 100%) !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.scout-theme-eau) {
    background:
        radial-gradient(circle at top left, rgba(21, 101, 192, 0.22), transparent 36%),
        linear-gradient(135deg, #edfaff 0%, #d8f0fb 100%) !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.scout-theme-energie) {
    background:
        radial-gradient(circle at top left, rgba(245, 124, 0, 0.22), transparent 36%),
        linear-gradient(135deg, #fff8ea 0%, #ffe8c2 100%) !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.scout-theme-environnement) {
    background:
        radial-gradient(circle at top left, rgba(56, 142, 60, 0.24), transparent 36%),
        linear-gradient(135deg, #f0fbef 0%, #dcf1df 100%) !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.scout-theme-rse):hover,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.scout-theme-eau):hover,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.scout-theme-energie):hover,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.scout-theme-environnement):hover,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.scout-event-marker):hover {
    transform: translateY(-2px);
    border-color: rgba(13, 92, 107, 0.42);
    box-shadow: 0 15px 32px rgba(16, 37, 30, 0.11);
}
.scout-card-disabled {
    cursor: not-allowed;
    opacity: 0.72;
}
.scout-theme-title {
    color: #014380;
    font-size: 22px;
    font-weight: 800;
    margin-bottom: 0.45rem;
    text-decoration: underline;
    text-decoration-color: rgba(67, 160, 71, 0.34);
    text-underline-offset: 4px;
}
.scout-theme-count {
    color: #60716b;
    font-size: 15px;
    font-weight: 650;
    margin-bottom: 0.5rem;
}
.scout-theme-summary {
    color: #243b33;
    display: -webkit-box;
    font-size: 15.2px;
    line-height: 1.42;
    margin-bottom: 0.45rem;
    overflow: hidden;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 5;
}
.scout-theme-summary ul {
    margin: 0;
    list-style: none;
    padding-left: 0;
}
.scout-theme-summary li {
    margin-bottom: 0.25rem;
    padding-left: 1rem;
    position: relative;
}
.scout-theme-summary li::before {
    color: #0d5c6b;
    content: "•";
    font-weight: 900;
    left: 0;
    position: absolute;
}
.scout-other-wrap {
    margin: 0.15rem auto 0;
    max-width: 360px;
}
.scout-article-card {
    margin: 0.75rem 0;
    padding: 0.95rem 1rem;
    border: 1px solid rgba(1, 67, 128, 0.14);
    border-radius: 15px;
    background: #ffffff;
    box-shadow: 0 8px 22px rgba(1, 67, 128, 0.06);
}
.scout-article-meta {
    color: #6a7773;
    font-size: 12px;
    font-weight: 750;
    letter-spacing: 0.02em;
    margin-bottom: 0.32rem;
    text-transform: uppercase;
}
.scout-article-title {
    color: #10251e;
    font-size: 16px;
    font-weight: 800;
    line-height: 1.35;
    margin-bottom: 0.45rem;
}
.scout-article-desc {
    color: #243b33;
    font-size: 14px;
    line-height: 1.55;
    margin-bottom: 0.6rem;
}
.scout-article-link {
    color: #0d5c6b;
    font-size: 13px;
    font-weight: 800;
    text-decoration: none;
}
.scout-article-link:hover {
    color: #388e3c;
    text-decoration: underline;
}
div[data-testid="stButton"] > button {
    border: 1px solid rgba(13, 92, 107, 0.28);
    border-radius: 999px;
    background: #0d5c6b;
    color: #ffffff;
    cursor: pointer;
    font-weight: 800;
    transition: transform 160ms ease, background 160ms ease, box-shadow 160ms ease;
}
div[data-testid="stButton"] > button[kind="tertiary"] {
    background: transparent !important;
    border: 0 !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    color: #014380 !important;
    cursor: pointer;
    font-size: 22px !important;
    font-weight: 800 !important;
    justify-content: flex-start !important;
    padding: 0 0 0.25rem 0 !important;
    text-align: left !important;
    text-decoration: underline !important;
    text-decoration-color: rgba(67, 160, 71, 0.34) !important;
    text-underline-offset: 4px;
    transform: none !important;
}
div[data-testid="stButton"] > button[kind="tertiary"] *,
div[data-testid="stButton"] > button[kind="tertiary"] p,
div[data-testid="stButton"] > button[kind="tertiary"] div,
div[data-testid="stButton"] > button[kind="tertiary"] span {
    background: transparent !important;
    box-shadow: none !important;
}
div[data-testid="stButton"] > button[kind="tertiary"]:hover {
    background: transparent !important;
    color: #0d5c6b !important;
    text-decoration-color: rgba(13, 92, 107, 0.58) !important;
}
div[data-testid="stButton"] > button:hover {
    border-color: #43a047;
    background: #0e6e81;
    color: #ffffff;
    transform: translateY(-1px);
    box-shadow: 0 9px 18px rgba(13, 92, 107, 0.16);
}
@media (max-height: 820px) {
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.scout-theme-rse),
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.scout-theme-eau),
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.scout-theme-energie),
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.scout-theme-environnement) {
        min-height: 210px;
        padding: 0.82rem 0.95rem !important;
    }
    .scout-theme-summary {
        -webkit-line-clamp: 4;
        font-size: 14.5px;
        line-height: 1.42;
    }
}
</style>
"""


def _format_date_fr(value):
    if pd.isna(value):
        return "Date non disponible"

    date_str = pd.Timestamp(value).strftime("%d %B %Y")
    for eng, fr in _MOIS_FR.items():
        date_str = date_str.replace(eng, fr)
    return date_str


def _render_article(row):
    date_str = _format_date_fr(row.get("Date"))
    title = escape(str(row.get("Title", "")).strip())
    source = escape(str(row.get("Website_name", "")).strip())
    desc = escape(str(row.get("Description", "")).strip())
    link = escape(str(row.get("Link", "")).strip(), quote=True)
    link_html = (
        f"<a class='scout-article-link' href='{link}' target='_blank' rel='noopener'>Lire l'article original</a>"
        if link
        else ""
    )
    desc_html = f"<div class='scout-article-desc'>{desc}</div>" if desc else ""

    st.markdown(
        (
            '<div class="scout-article-card">'
            f'<div class="scout-article-meta">{date_str} &nbsp;|&nbsp; {source}</div>'
            f'<div class="scout-article-title">{title}</div>'
            f'{desc_html}'
            f'{link_html}'
            '</div>'
        ),
        unsafe_allow_html=True,
    )


def _theme_summary_text(summaries, theme):
    text = str(summaries.get(theme, "") or "").strip()
    return text if text else "Aucun resume disponible pour cette thematique sur la periode selectionnee."


def _theme_card_class(theme):
    return {
        "RSE & Referentiels": "scout-theme-rse",
        "Eau": "scout-theme-eau",
        "Energie": "scout-theme-energie",
        "Environnement": "scout-theme-environnement",
    }.get(theme, "")


def _theme_card_key(theme):
    return {
        "RSE & Referentiels": "rse",
        "Eau": "eau",
        "Energie": "energie",
        "Environnement": "environnement",
    }.get(theme, "theme")


def _summary_to_html(summary_text):
    cleaned_lines = []
    for line in str(summary_text).splitlines():
        line = line.strip()
        if not line:
            continue
        cleaned_lines.append(line.lstrip("-•* ").strip())

    if not cleaned_lines:
        cleaned_lines = [str(summary_text).strip()]

    items = "".join(f"<li>{escape(line)}</li>" for line in cleaned_lines if line)
    return f"<ul>{items}</ul>" if items else ""


_ESG_EVENT_CATALOG = [
    {"month": 1, "day": 24, "name": "Journee internationale de l'education", "category": "Social / ODD 4", "url": "https://www.unesco.org/en/days/education"},
    {"month": 2, "day": 20, "name": "Journee mondiale de la justice sociale", "category": "Social / droits humains", "url": "https://www.un.org/en/observances/social-justice-day"},
    {"month": 3, "day": 8, "name": "Journee internationale des droits des femmes", "category": "Diversite / egalite", "url": "https://www.un.org/en/observances/womens-day"},
    {"month": 3, "day": 22, "name": "Journee mondiale de l'eau", "category": "Eau / ressources", "url": "https://www.un.org/en/observances/water-day"},
    {"month": 4, "day": 7, "name": "Journee mondiale de la sante", "category": "Sante / social", "url": "https://www.who.int/campaigns/world-health-day"},
    {"month": 4, "day": 22, "name": "Journee de la Terre", "category": "Environnement / climat", "url": "https://www.earthday.org/earth-day-2026/"},
    {"month": 4, "day": 28, "name": "Journee mondiale securite et sante au travail", "category": "SST / social", "url": "https://www.ilo.org/safework/events/safeday"},
    {"month": 5, "day": 1, "name": "Journee internationale des travailleurs", "category": "Social / travail", "url": "https://www.ilo.org/"},
    {"month": 5, "day": 19, "name": "ChangeNOW Summit", "category": "Salon / solutions durables / ESG", "url": "https://www.changenow.world/"},
    {"month": 5, "day": 20, "name": "Journee mondiale des abeilles", "category": "Biodiversite", "url": "https://www.un.org/en/observances/bee-day"},
    {"month": 5, "day": 22, "name": "Journee internationale de la biodiversite", "category": "Biodiversite / nature", "url": "https://www.un.org/en/observances/biological-diversity-day"},
    {"month": 6, "day": 5, "name": "Journee mondiale de l'environnement", "category": "Environnement", "url": "https://www.worldenvironmentday.global/"},
    {"month": 6, "day": 8, "name": "Journee mondiale de l'ocean", "category": "Ocean / biodiversite", "url": "https://www.un.org/en/observances/oceans-day"},
    {"month": 6, "day": 12, "name": "Journee mondiale contre le travail des enfants", "category": "Droits humains / supply chain", "url": "https://www.ilo.org/ipec/Campaignandadvocacy/wdacl"},
    {"month": 6, "day": 17, "name": "Journee lutte contre desertification et secheresse", "category": "Climat / sols / eau", "url": "https://www.un.org/en/observances/desertification-day"},
    {"month": 6, "day": 27, "name": "Journee des micro, petites et moyennes entreprises", "category": "PME / economie inclusive", "url": "https://www.un.org/en/observances/micro-small-medium-businesses-day"},
    {"month": 7, "day": 11, "name": "Journee mondiale de la population", "category": "Social / developpement", "url": "https://www.un.org/en/observances/world-population-day"},
    {"month": 8, "day": 9, "name": "Journee internationale des peuples autochtones", "category": "Droits humains", "url": "https://www.un.org/en/observances/indigenous-day"},
    {"month": 9, "day": 7, "name": "Journee internationale de l'air pur", "category": "Pollution / sante", "url": "https://www.un.org/en/observances/clean-air-day"},
    {"month": 9, "day": 16, "name": "Journee internationale de la couche d'ozone", "category": "Climat / atmosphere", "url": "https://www.un.org/en/observances/ozone-day"},
    {"month": 9, "day": 18, "name": "Journee internationale de l'egalite de remuneration", "category": "Diversite / social", "url": "https://www.un.org/en/observances/equal-pay-day"},
    {"month": 9, "day": 22, "name": "UN Global Compact Leaders Summit", "category": "Meeting / RSE / Global Compact", "url": "https://www.globalcompactusa.org/events-and-webinars/leaders-summit-2026"},
    {"month": 10, "day": 7, "name": "Journee mondiale du travail decent", "category": "Social / travail", "url": "https://www.ituc-csi.org/world-day-for-decent-work"},
    {"month": 10, "day": 13, "name": "European Sustainable Industry Summit", "category": "Meeting / industrie durable / ESG", "url": "https://www.csreurope.org/calendar/european-sustainable-industry-2026"},
    {"month": 10, "day": 13, "name": "Journee reduction des risques de catastrophe", "category": "Resilience / climat", "url": "https://www.un.org/en/observances/disaster-reduction-day"},
    {"month": 10, "day": 16, "name": "Journee mondiale de l'alimentation", "category": "Agriculture / social", "url": "https://www.fao.org/world-food-day"},
    {"month": 10, "day": 17, "name": "Journee elimination de la pauvrete", "category": "Social / inclusion", "url": "https://www.un.org/en/observances/day-for-eradicating-poverty"},
    {"month": 11, "day": 19, "name": "Journee mondiale des toilettes", "category": "Eau / assainissement", "url": "https://www.un.org/en/observances/toilet-day"},
    {"month": 11, "day": 20, "name": "Journee mondiale de l'enfance", "category": "Droits humains", "url": "https://www.un.org/en/observances/world-childrens-day"},
    {"month": 11, "day": 25, "name": "Journee elimination violence faite aux femmes", "category": "Droits humains / genre", "url": "https://www.un.org/en/observances/ending-violence-against-women-day"},
    {"month": 12, "day": 3, "name": "Journee internationale des personnes handicapees", "category": "Inclusion / diversite", "url": "https://www.un.org/en/observances/day-of-persons-with-disabilities"},
    {"month": 12, "day": 5, "name": "Journee mondiale des sols", "category": "Sols / biodiversite", "url": "https://www.fao.org/world-soil-day"},
    {"month": 12, "day": 10, "name": "Journee des droits de l'homme", "category": "Droits humains", "url": "https://www.un.org/en/observances/human-rights-day"},
]


def _event_date(event, year):
    return date(year, event["month"], event["day"])


def _events_between(start_date, end_date):
    events = []
    for year in range(start_date.year, end_date.year + 1):
        for event in _ESG_EVENT_CATALOG:
            event_date = _event_date(event, year)
            if start_date <= event_date <= end_date:
                events.append({**event, "date": event_date})
    return sorted(events, key=lambda item: item["date"])


def _event_card_html(events, empty_message):
    if not events:
        return f'<div class="scout-event-empty scout-event-meta">{escape(empty_message)}</div>'

    items = []
    for event in events[:6]:
        event_url = escape(event["url"], quote=True)
        items.append(
            '<div class="scout-event-item">'
            f'<a href="{event_url}" target="_blank" rel="noopener">'
            f'<div class="scout-event-date">{_format_date_fr(event["date"])}</div>'
            f'<div class="scout-event-name">{escape(event["name"])}</div>'
            f'<div class="scout-event-meta">{escape(event["category"])}</div>'
            '</a>'
            '</div>'
        )
    return f'<div class="scout-event-list">{"".join(items)}</div>'


def _render_esg_event_watch(events):
    with st.container(border=True, key="scout-card-event"):
        st.markdown('<span class="scout-card-marker scout-event-marker"></span>', unsafe_allow_html=True)
        if st.button("Veille Evenementielle RSE/ESG", key="open_esg_event_calendar", type="tertiary"):
            st.session_state["scout_show_event_calendar"] = True
        st.markdown(
            _event_card_html(events, "Aucun evenement ESG/RSE majeur identifie sur cette periode."),
            unsafe_allow_html=True,
        )


@st.dialog("Calendrier evenementiel RSE/ESG", width="large")
def _show_esg_event_calendar(calendar_start):
    calendar_end = calendar_start + timedelta(days=183)
    events = _events_between(calendar_start, calendar_end)
    st.markdown(f"### Du {_format_date_fr(calendar_start)} au {_format_date_fr(calendar_end)} (6 Mois)")
    if not events:
        st.info("Aucun evenement ESG/RSE majeur identifie sur cette periode elargie.")
        return

    cards = []
    for event in events:
        event_url = escape(event["url"], quote=True)
        cards.append(
            '<div class="scout-calendar-card">'
            f'<a href="{event_url}" target="_blank" rel="noopener">'
            f'<div class="scout-event-date">{_format_date_fr(event["date"])}</div>'
            f'<div class="scout-event-name">{escape(event["name"])}</div>'
            f'<div class="scout-event-meta">{escape(event["category"])}</div>'
            '</a>'
            '</div>'
        )
    st.markdown(f'<div class="scout-calendar-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


@st.dialog("Details des articles", width="large")
def _show_theme_details(theme, group):
    emoji = _THEME_EMOJI.get(theme, "")
    st.markdown(f"### {emoji} {theme}")
    st.caption(f"{len(group)} article(s) associe(s) a ce theme.")
    for _, row in group.sort_values("Date", ascending=False).iterrows():
        _render_article(row)


st.markdown(_scout_css(), unsafe_allow_html=True)
st.markdown(
    """<style>div[data-testid="stMarkdownContainer"] { text-align: left }</style>""",
    unsafe_allow_html=True,
)

# ── Date du jour en francais ───────────────────────────────────────────────────
# ── Contenu principal ──────────────────────────────────────────────────────────
if answer_togg:
    if len(date_select) != 2 or None in date_select or "" in date_select:
        st.warning("Veuillez selectionner deux dates")
    else:
        with st.spinner("Recherche d'actualites..."):
            media_data_df = data_media_scout(MEDIA_SCOUT_URLS)
            start_date, end_date = (
                date_select if isinstance(date_select, tuple) else (date_select, date_select)
            )
            filtered_df = media_data_df[
                (media_data_df["Date"] >= pd.Timestamp(start_date))
                & (media_data_df["Date"] <= pd.Timestamp(end_date))
            ]

        if filtered_df.empty:
            st.info("Aucune actualite pertinente trouvee sur la periode selectionnee.")
        else:
            # ── Cartes thematiques interactives ────────────────────────────────
            themes_to_summarize = [t for t in filtered_df["Theme"].unique() if t != "Autres"]
            theme_articles = {}
            for theme in themes_to_summarize:
                theme_rows = filtered_df[filtered_df["Theme"] == theme].head(10)
                theme_articles[theme] = tuple(
                    " | ".join(
                        part
                        for part in [
                            f"Titre: {str(row.get('Title', '')).strip()}",
                            f"Source: {str(row.get('Website_name', '')).strip()}",
                            f"Date: {_format_date_fr(row.get('Date'))}",
                            f"Resume: {str(row.get('Description', '')).strip()}",
                        ]
                        if part and not part.endswith(": ")
                    )
                    for _, row in theme_rows.iterrows()
                )
            with st.spinner("Synthese en cours..."):
                summaries = summarize_scout_themes(theme_articles)

            grouped_df = dict(tuple(filtered_df.groupby("Theme", observed=True)))
            ordered_themes = ["RSE & Referentiels", "Eau", "Energie", "Environnement"]
            empty_theme_df = filtered_df.iloc[0:0]
            selected_theme = st.session_state.get("scout_selected_theme")
            period_events = _events_between(start_date, end_date)

            st.markdown("<div class='scout-main-grid'>", unsafe_allow_html=True)
            _render_esg_event_watch(period_events)
            if st.session_state.get("scout_show_event_calendar"):
                _show_esg_event_calendar(start_date)
                st.session_state.pop("scout_show_event_calendar", None)
            top_cols = st.columns(2, gap="medium")
            bottom_cols = st.columns(2, gap="medium")
            theme_slots = [top_cols[0], top_cols[1], bottom_cols[0], bottom_cols[1]]

            for idx, theme in enumerate(ordered_themes):
                group = grouped_df.get(theme, empty_theme_df)
                emoji = _THEME_EMOJI.get(theme, "")
                summary = _summary_to_html(_theme_summary_text(summaries, theme))
                with theme_slots[idx]:
                    with st.container(border=True, key=f"scout-card-{_theme_card_key(theme)}"):
                        st.markdown(
                            f'<span class="scout-card-marker {_theme_card_class(theme)}"></span>',
                            unsafe_allow_html=True,
                        )
                        if group.empty:
                            st.markdown(
                                f'<div class="scout-theme-title">{emoji} {escape(theme)}</div>',
                                unsafe_allow_html=True,
                            )
                        elif st.button(f"{emoji} {theme}", key=f"open_theme_title_{idx}", type="tertiary"):
                            st.session_state["scout_selected_theme"] = theme
                            selected_theme = theme

                        st.markdown(
                            f"""
                            <div class="scout-theme-count">{len(group)} article(s) detecte(s)</div>
                            <div class="scout-theme-summary">{summary}</div>
                            """,
                            unsafe_allow_html=True,
                        )

            if selected_theme in ordered_themes:
                selected_group = grouped_df.get(selected_theme, empty_theme_df)
                if not selected_group.empty:
                    _show_theme_details(selected_theme, selected_group)
                    st.session_state.pop("scout_selected_theme", None)

            #autres_df = grouped_df.get("Autres")
            #st.markdown("<div class='scout-other-wrap'>", unsafe_allow_html=True)
            #if autres_df is not None and not autres_df.empty:
            #    if st.button("Autres News", key="open_theme_autres", width="stretch"):
            #        _show_theme_details("Autres News", autres_df)
            #else:
            #    st.button("Autres News", key="open_theme_autres_disabled", width="stretch", disabled=True)
            #st.markdown("</div>", unsafe_allow_html=True)
            #st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

else:
    #st.markdown("<div class='thick-divider'></div>", unsafe_allow_html=True)
    #st.markdown("<br>", unsafe_allow_html=True)

    st.write(
        """
        <div style="background-color:#ddeee3; color:#167232; padding:15px; border-radius:5px; margin-bottom:15px">
            <span style="font-size:18px;"><u><b>Presentation :</b></u></span>
            <ul style="list-style-type:none; margin:0;">
                <li><span style="font-size:17px;"><b>Cet Agent IA est specialisé dans l'actualite. Il fournit des resumes sources au Maroc et a l'international, strictement lies aux thematiques Eau, Energie, Environnement, RSE et Referentiels RSE.</b></span></li>
                <li><span style="font-size:17px;"><i>Modele Groq : llama-3.3-70b-versatile</i></span></li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write(
        """
        <div style="background-color:#dce7f0; color:#014380; padding:15px; border-radius:5px; margin-bottom:15px">
            <span style="font-size:18px;"><u><b>Tester l'Agent :</b></u></span>
            <ul style="list-style-type:none; margin:0;">
                <li><span style="font-size:17px;">1 - Selectionner la periode souhaitee, jusqu'a 90 jours</span></li>
                <li><span style="font-size:17px;">2 - Activer le toggle button "Activate Agent"</span></li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    #st.markdown("<div class='thick-divider'></div>", unsafe_allow_html=True)

    df_urls = pd.DataFrame(MEDIA_SCOUT_SOURCE_CATALOG).reindex(columns=["Journal", "Couverture", "URL"])
    st.markdown(
        "<h1 style='text-align:center; font-size:18px; font-weight:bold; padding:0rem 0px 0.5rem'>Liste des sources incluses dans les recherches</h1>",
        unsafe_allow_html=True,
    )

    _, col_sources, _ = st.columns([5, 90, 5])
    with col_sources:
        st.dataframe(
            df_urls.style.format(na_rep="No Data", precision=0),
            column_config={
                "URL": st.column_config.LinkColumn(
                    "URL",
                    validate=r"^https?://.*$",
                    max_chars=100,
                    display_text="Ouvrir",
                ),
            },
            hide_index=True,
            width="stretch",
        )


with st.sidebar:
    _, col = st.columns([33, 67], vertical_alignment="center")
    with col:
        authenticator.logout("Logout")