# Veille LDA

**L'essentiel de l'actualité agricole, agroalimentaire et RSE, au même endroit.**

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.53.1-FF4B4B?logo=streamlit&logoColor=white)
![Intelligence artificielle](https://img.shields.io/badge/IA-Gemini%20%2B%20Groq-2E7D32)

Veille LDA est un tableau de bord conçu pour suivre les actualités utiles aux **Domaines Agricoles**. L'application rassemble des articles de sources marocaines, européennes et internationales, les classe par thème et met en avant les informations à fort impact potentiel pour les activités du groupe.

L'objectif : passer moins de temps à chercher l'information et davantage à comprendre ce qu'elle implique.

## Ce que l'on peut faire

- **Choisir un thème et une période** pour retrouver les actualités pertinentes sur les 15 derniers jours.
- **Lire le Signal du jour**, une synthèse générée par l'IA lorsqu'un article du thème et de la période justifie une mise en avant par son impact concret.
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
- Normes & Conformité : ESG, QSE et SST, mises en avant au centre de la sélection des thèmes.

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

Pendant la navigation, une seule copie des données est chargée par session et par créneau de collecte. Le Signal est réutilisé lorsque les articles sélectionnés ne changent pas, y compris lors d'un changement de thème visuel ou d'un aller-retour vers les sources. Les titres encore en anglais sont traduits par lots. En cas de timeout ou de panne du fournisseur, ses clés sont mises en pause pendant une minute et le relais est essayé directement ; une erreur limitée à une clé n'empêche pas d'essayer les autres.

Le classement s'appuie sur le sujet du titre et du résumé ; les noms de flux, les URL et les intitulés complets des ministères ne constituent pas des preuves thématiques. Les publications **ONSSA** sont rattachées à **Normes : ESG, QSE & SST**, y compris lorsqu'elles citent une filière. La rubrique Aquaculture exige un lien explicite avec les activités aquacoles ou les produits de la mer.

Pour le Signal du jour, les articles du **Maroc**, de l'**Union européenne** ou de **portée mondiale** sont évalués avant de retenir jusqu'à **25 candidats**, avec une place réservée à chaque type de veille présent. Les actualités locales d'un pays tiers exigent un lien explicite avec le Maroc, l'UE ou le marché mondial. L'origine « WORLD/WW » d'un flux et une simple mention ISO, HACCP ou halal ne suffisent pas. Ce filtre s'applique aussi au signal de repli lorsque l'IA échoue ; une portée géographique indéterminée ne justifie pas une mise en avant. L'impact documenté, le lien avec le thème et la fraîcheur guident ensuite la sélection. Le réglementaire n'est pas prioritaire par défaut et l'IA peut conclure qu'aucun signal ne se justifie.

Le résumé décrit **l'article lui-même** : faits, acteurs ou produits concernés, changement et dates utiles, sans extrapoler un impact pour LDA. Seule la publication retenue est consultée sur les sites de référence autorisés ; si son texte est inaccessible, l'extrait collecté sert de source. Les textes et générations réussis sont mis en cache pendant 12 heures. Si la génération échoue, un extrait français existant est affiché comme tel, ou une indisponibilité est signalée avec le lien d'origine, sans fabriquer de résumé générique.

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

Après une mise à jour du projet, relancez `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`, puis redémarrez Streamlit. Modifier `requirements.txt` ne met pas automatiquement à jour un environnement local déjà créé. Une erreur `TypeError` liée à un paramètre Groq peut provenir d'un SDK ancien, même avec une clé valide.

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

### Source AGRINFO / COLEAD

Une seule entrée [AGRINFO](https://agrinfo.eu/) couvre les nouveautés de ses rubriques éditoriales, découvertes depuis l'accueil :

- Derniers rapports et recherche générale, tous sujets confondus.
- Rapports de non-conformité : contrôles, notifications et fraudes.
- Consultations réglementaires en cours.
- Dossiers explicatifs (« Explainers »).
- Publications et guides, avec liens vers les PDF d'origine.
- Webinaires et ressources associées, sans se limiter au PPWR.
- Bulletins « AGRINFO Updates ».
- Tracker des LMR de pesticides, via ses rapports associés.

La collecte suit les mêmes horaires de 7 h et 19 h et la fenêtre de 15 jours. Un ancien rapport révisé récemment est repris à sa date de révision. Les dates d'application des limites ou de clôture des consultations ne sont pas utilisées comme dates de publication. Les webinaires gardent la date réelle de leur première session, sans répétition annuelle ; les sessions futures ne sont pas présentées comme des actualités déjà publiées.

Les rubriques sont parcourues avec quatre requêtes simultanées au maximum par étape. La pagination s'arrête dès qu'une page ne contient plus de contenu dans la période, avec une limite de sécurité de dix pages par rubrique. Un même rapport présent dans plusieurs rubriques est regroupé avant le traitement IA. Les pages institutionnelles, formulaires d'inscription et annuaires de liens externes ne sont pas explorés.

Lorsque seule une date mensuelle est disponible, le premier jour du mois sert de repère conservateur et l'absence de jour précis est indiquée dans la description. Le tracker reste la référence pour consulter l'intégralité des tableaux de valeurs LMR ; l'application collecte ses rapports liés, pas une copie de la base réglementaire.
