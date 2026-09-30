# Veille LDA

**L'essentiel de l'actualité agricole, agroalimentaire et RSE, au même endroit.**

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.53.1-FF4B4B?logo=streamlit&logoColor=white)
![Intelligence artificielle](https://img.shields.io/badge/IA-Gemini%20%2B%20Groq-2E7D32)

Veille LDA est un tableau de bord conçu pour suivre les actualités utiles aux **Domaines Agricoles**. L'application rassemble des articles de sources marocaines, européennes et internationales, les classe par thème et met en avant les informations à fort impact potentiel pour les activités du groupe.

L'objectif : passer moins de temps à chercher l'information et davantage à comprendre ce qu'elle implique.

## Ce que l'on peut faire

- **Choisir un thème et une période** pour retrouver les actualités pertinentes sur les 15 derniers jours.
- **Lire le Signal du jour**, une synthèse générée par l'IA à partir d'une sélection d'articles de la période choisie.
- **Explorer les articles** avec leur date, leur source, leur description et un lien vers la publication d'origine.
- **Consulter les événements à venir** : salons, conférences et rendez-vous thématiques.
- **Parcourir les sources de référence** et télécharger leur catalogue au format Excel.
- **Adapter l'affichage** avec le mode clair ou sombre et une barre de filtres fixe ou défilante.

### Quatre regards sur l'actualité

| Type de veille | Ce que l'on suit |
| --- | --- |
| Réglementaire | Réglementations, normes, certifications et exigences à surveiller. |
| Informative | Actualités sectorielles, innovations et évolutions des marchés. |
| Événementielle | Salons, rencontres professionnelles et journées thématiques. |
| Concurrentielle | Actualités des acteurs et produits concurrents, selon le thème concerné. |

### Six thèmes couverts

- Agrumes, fruits rouges et maraîchage, notamment les tomates cerises.
- Produits laitiers et épicerie fine.
- Élevage : ovins, bovins, caprins et volailles.
- Aquaculture : élevage et transformation.
- Environnement, eau et énergie.
- Normes : ESG, QSE et SST.

## Comment ça fonctionne

```text
Sites web et flux RSS
        |
        v
Collecte, filtrage et suppression des doublons
        |
        v
Classement par thème et type de veille
        |
        v
Enrichissement IA et affichage dans le tableau de bord
```

L'IA aide à vérifier la pertinence des articles, à traduire les contenus en français et à produire le Signal du jour. Les modèles configurés sont :

| Fournisseur | Modèle | Priorité |
| --- | --- | --- |
| Google Gemini | `gemini-3.5-flash-lite` | Premier choix, si une clé valide est disponible. |
| Groq | `openai/gpt-oss-120b` | Relais si Gemini est indisponible ou limité. |

Les articles hors périmètre et les doublons sont écartés avant l'enrichissement IA. Les traitements sont regroupés par lots et les réponses réussies sont mises en cache pendant **12 heures**, pour limiter les appels répétés aux API.

> Les contenus générés par l'IA restent une aide à la lecture. Vérifiez les informations importantes et les dates des événements auprès des sources d'origine avant de prendre une décision.

## Quand les données sont-elles actualisées ?

La collecte est programmée à **7 h et 19 h**, dans le fuseau **`Africa/Casablanca`**. L'heure de la dernière collecte terminée est affichée dans l'application.

> [!IMPORTANT]
> L'actualisation aux heures prévues nécessite un serveur actif. Streamlit Community Cloud peut mettre l'application en veille lorsqu'elle n'est pas consultée. À sa reprise, les données sont actualisées si le créneau a changé. Une exécution garantie à heure fixe nécessiterait une planification externe. Voir la [documentation sur la mise en veille](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app#app-hibernation).

## Lancer l'application en local

### 1. Installer les dépendances

Exemple sous Windows avec Python 3.11 installé, depuis le dossier du projet :

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. Configurer les clés API

Créez le fichier `.streamlit/secrets.toml` et renseignez les clés des fournisseurs que vous souhaitez utiliser. **Une seule clé valide suffit** pour activer les fonctions IA ; supprimez les lignes des fournisseurs non utilisés.

```toml
GOOGLE_API_KEY = "votre-cle-gemini"
GROQ_API_KEY = "votre-cle-groq"

# Facultatif : clés supplémentaires prises en charge
# GOOGLE_API_KEY_1 = "votre-deuxieme-cle-gemini"
# GROQ_API_KEY_1 = "votre-deuxieme-cle-groq"
```

Les mêmes noms peuvent être utilisés comme variables d'environnement. Sans clé API, la collecte et le classement par règles restent disponibles, mais pas le Signal du jour ni l'enrichissement IA.

> [!WARNING]
> Ne publiez jamais vos clés API sur GitHub. Le fichier `.streamlit/secrets.toml` est exclu du dépôt par `.gitignore`.

### 3. Démarrer le tableau de bord

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Ouvrez ensuite [localhost:8501](http://localhost:8501). Le premier chargement peut prendre un peu de temps pendant la collecte et le traitement des sources.

## Héberger sur Streamlit Community Cloud

1. Publiez le projet dans un dépôt GitHub accessible à votre compte Streamlit.
2. Depuis [Streamlit Community Cloud](https://share.streamlit.io), créez une application en sélectionnant le dépôt, la branche **`master`** et le fichier **`app.py`**.
3. Dans les paramètres avancés, choisissez Python **3.11** pour reprendre l'environnement de l'exemple local, puis renseignez les clés API dans **Secrets**.
4. Lancez le déploiement : les dépendances sont installées depuis `requirements.txt`.

Le fichier de secrets local ne doit pas être envoyé dans le dépôt. Retrouvez les étapes dans les documentations officielles de [déploiement](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) et de [gestion des secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).

## Se repérer dans le projet

| Fichier | Rôle |
| --- | --- |
| `app.py` | Interface Streamlit, filtres, tableau de bord et affichage des sources. |
| `Settings.py` | Sources, règles de classement, collecte, horaires et appels aux modèles IA. |
| `requirements.txt` | Dépendances Python de l'application. |
| `.streamlit/config.toml` | Configuration visuelle de Streamlit. |
| `.gitignore` | Exclusion des secrets, environnements locaux et fichiers temporaires. |

Les sources, thèmes et horaires de collecte peuvent être adaptés dans `Settings.py`.
