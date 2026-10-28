# Veille LDA

**L'essentiel de l'actualité agricole, agroalimentaire et RSE, au même endroit.**

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.53.1-FF4B4B?logo=streamlit&logoColor=white)
![Intelligence artificielle](https://img.shields.io/badge/IA-Gemini%20%2B%20Groq-2E7D32)

Veille LDA est un tableau de bord conçu pour suivre les actualités utiles aux **Domaines Agricoles**. L'application rassemble des articles de sources marocaines, européennes et internationales, les classe par thème et met en avant les informations à fort impact potentiel pour les activités du groupe.

L'objectif : passer moins de temps à chercher l'information et davantage à comprendre ce qu'elle implique.

## Ce que l'on peut faire

- **Choisir un thème et une période** pour retrouver les actualités pertinentes sur les 15 derniers jours.
- **Consulter les Signaux dans les cadres de l'accueil** : les six cadres de même taille présentent chacun le résumé du **Signal** de leur thème, avec les niveaux **Prioritaire** et **À la une**. **Normes & Conformité** occupe la dernière place, en bas à droite sur ordinateur. Un clic sur un cadre ouvre le détail du thème et ses sources.
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

L'IA aide à vérifier la pertinence des articles, à traduire les contenus en français et à produire le Signal. Les modèles configurés sont :

| Fournisseur | Modèle | Priorité |
| --- | --- | --- |
| Google Gemini | `gemini-3.5-flash-lite` | Premier choix, si une clé valide est disponible. |
| Groq | `openai/gpt-oss-120b` | Relais si Gemini est indisponible ou limité. |

Les articles hors périmètre et les doublons sont écartés avant l'enrichissement IA. Les traitements sont regroupés par lots et les réponses réussies sont mises en cache pendant **12 heures**, pour limiter les appels répétés aux API.

Pendant la navigation, une seule copie des données est chargée par session et par créneau de collecte. La recherche des actualités et la préparation des signaux sont regroupées derrière un écran de chargement unique ; la barre de filtres et les cadres sont affichés une fois la préparation terminée. La période choisie est mémorisée pour pouvoir calculer les résumés avant de créer les filtres. Les signaux de tous les thèmes sont préparés ensemble dès le chargement, après une mise à jour des données ou un changement de période, avec au plus deux analyses simultanées. L'accueil et les pages thématiques partagent le même instantané ; un clic sur un thème ne lance plus son analyse. Les échecs temporaires sont retentés automatiquement après leur délai de reprise (au minimum une minute), via la vérification périodique de la session. Les titres encore en anglais sont traduits par lots. En cas de timeout ou de panne du fournisseur, ses clés sont mises en pause pendant une minute et le relais est essayé directement ; une erreur limitée à une clé n'empêche pas d'essayer les autres.

Le classement s'appuie sur le sujet du titre et du résumé ; les noms de flux, les URL et les intitulés complets des ministères ne constituent pas des preuves thématiques. Les publications **ONSSA** sont rattachées à **Normes : ESG, QSE & SST**, y compris lorsqu'elles citent une filière. La rubrique Aquaculture exige un lien explicite avec les activités aquacoles ou les produits de la mer.

Pour le Signal, les articles du **Maroc**, de l'**Union européenne** ou de **portée mondiale** sont évalués avant de retenir jusqu'à **25 candidats**, avec une place réservée à chaque type de veille présent. Les actualités locales d'un pays tiers exigent un lien explicite avec le Maroc, l'UE ou le marché mondial. L'origine « WORLD/WW » d'un flux et une simple mention ISO, HACCP ou halal ne suffisent pas. Ce filtre s'applique aussi au signal de repli lorsque l'IA échoue ; une portée géographique indéterminée ne justifie pas une mise en avant. Le lien avec le thème, l'utilité et la fraîcheur guident ensuite la sélection, sans priorité automatique au réglementaire.

Deux niveaux permettent une veille quotidienne plus régulière : **Prioritaire** pour une décision ou alerte à impact concret, **À la une** pour une consultation, une évolution de marché ou une actualité sectorielle documentée, même sans urgence. Si l'IA ne retient rien ou est indisponible, le meilleur candidat disposant d'un titre et d'un extrait français suffisamment informatif peut être présenté **À la une**, avec la mention **Extrait de l'article**. Faute d'extrait, lorsque l'IA répond sans juger aucun article significatif, les meilleurs candidats sont résumés au niveau **À la une**. Un titre seul, sa répétition avec un nom de cabinet, un slogan ou un contenu hors périmètre ne suffisent pas. Les offres de services, publireportages et pages de prospection ou d'optimisation fiscale individuelle sont exclus du Signal, y compris du repli. Les analyses factuelles et les actualités commerciales sectorielles restent admissibles. La sélection respecte toujours le thème et la période choisis.

Le résumé décrit **l'article lui-même** : faits, acteurs ou produits concernés, changement et dates utiles, sans extrapoler un impact pour LDA. La publication retenue est consultée sur les sites de référence autorisés ; si son texte est inaccessible, un extrait collecté suffisamment informatif peut servir de source. Une page intermédiaire Google Actualités et un extrait répétant simplement le titre ne constituent pas un texte d'article : aucun résumé n'est généré depuis ce seul titre. Si la source choisie est inexploitable, jusqu'à quatre autres candidats déjà filtrés sont examinés au niveau **À la une** (cinq articles au total). En dernier recours, hors erreur temporaire, le cadre du thème présente sa actualité la plus récente au niveau **À la une** (titre seul, sans résumé) plutôt qu'un cadre vide. Les fiches de cotation sans actualité sont exclues. Les textes et générations réussis sont mis en cache pendant 12 heures. Une source inaccessible ou insuffisante est distinguée d'une absence d'actualité et d'une panne IA ; seules les erreurs temporaires sont relancées, en respectant le délai de reprise communiqué par le fournisseur. Les journaux indiquent l'étape, la catégorie et le code d'erreur sans afficher les clés API.

> Les contenus générés par l'IA restent une aide à la lecture. Vérifiez les informations importantes et les dates des événements auprès des sources d'origine avant de prendre une décision.

## Quand les données sont-elles actualisées ?

La collecte est programmée à **7 h et 19 h**, dans le fuseau **`Africa/Casablanca`**. L'heure de la dernière collecte terminée est affichée dans l'application.

Si une collecte échoue ou ne renvoie aucun article exploitable, les dernières données valides sont conservées avec leur date réelle. Un avertissement apparaît et une nouvelle tentative est possible après une minute, partagée entre les utilisateurs. Une sauvegarde locale permet également ce repli après un redémarrage, tant que le disque du serveur est conservé. Une reconstruction du conteneur peut supprimer cette sauvegarde.

Les requêtes de sources sont limitées à huit en parallèle, avec au plus deux connexions simultanées par domaine. Un timeout, une erreur de connexion transitoire ou un HTTP 5xx peut déclencher une seule reprise. Les refus 403, quotas HTTP 429 et erreurs de certificat ne sont pas contournés ; le code HTTP ou le type d'erreur est précisé dans les journaux.

Le Vert, MAP Ecology et l'ONSSA sont collectés en priorité à partir des publications de leur propre domaine indexées par le moteur d'actualités. Cela évite de recommencer à chaque collecte les requêtes directes régulièrement refusées ou trop lentes ; les sites officiels restent un recours si l'entrée privilégiée ne fournit rien. La Vie Éco utilise directement sa page d'accueil et ne sollicite pas son flux lorsque ce listing fournit des articles datés exploitables.

Pour les autres sources, lorsqu'un flux échoue ou ne contient aucun article daté exploitable, la collecte essaie la page d'accueil du même site. Les recherches thématiques conservent leur requête et ne basculent jamais vers une page d'accueil généraliste. Le nom de la source et les dates de publication sont conservés, puis la fenêtre de quinze jours est appliquée normalement : un ancien résultat indexé ne devient pas une nouvelle actualité. Les flux de commentaires et les métadonnées oEmbed/RSD ne sont pas collectés comme des articles.

Sur les listings, les dates relatives explicites de publication (« il y a deux heures », présentées numériquement par le site) sont rapportées à l'heure de Casablanca ; l'absence de date n'est pas remplacée par la date du jour. Les cartes Carbon Brief utilisent le lien vers l'article plutôt que leur lien de rubrique.

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

Les mêmes noms peuvent être utilisés comme variables d'environnement. Sans clé API, la collecte et le classement par règles restent disponibles. Le Signal peut afficher un extrait français existant au niveau **À la une** ; la sélection et la synthèse par IA nécessitent une clé valide.

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

## Héberger sur Azure

L'infrastructure est décrite dans `infra/main.bicep` (groupe de ressources **`RG-LDA-Veille`**) :

| Ressource | Rôle |
| --- | --- |
| App Service Linux B1, Python 3.11 | Héberge Streamlit, avec Always On actif pour la collecte de 7 h et 19 h. |
| Identité managée de l'app | Accès sans mot de passe à Key Vault et à Azure SQL. |
| Key Vault (stratégies d'accès, sans RBAC) | Clés API (`GOOGLE-API-KEY`, `GROQ-API-KEY`…) et paramètres SQL. |
| Azure SQL Basic, authentification Entra ID uniquement | Conserve le résultat de chaque collecte, réutilisé après un redémarrage. |

La seule variable de l'application est `KEY_VAULT_URL`, qui n'est pas un secret. Dans Key Vault, les `_` des noms de secrets deviennent des `-`.

```powershell
az login
winget install Microsoft.Sqlcmd
.\infra\deploy.ps1                                  # ressources, utilisateur SQL, profil de publication GitHub
.\infra\set-api-keys.ps1 -KeyVault <nom-du-coffre>  # saisie masquée des clés API
```

Chaque push sur `master` déclenche ensuite `.github/workflows/azure-webapp.yml`, qui déploie l'application avec le profil de publication (secret GitHub `AZURE_WEBAPP_PUBLISH_PROFILE`). Après une modification des clés dans Key Vault, redémarrez l'App Service.

## Se repérer dans le projet

| Fichier | Rôle |
| --- | --- |
| `app.py` | Interface Streamlit, filtres, tableau de bord et affichage des sources. |
| `Settings.py` | Sources, règles de classement, collecte, horaires, appels aux modèles IA et export Excel des sources (généré au clic puis mis en cache). |
| `azure_services.py` | Lecture des secrets Key Vault et stockage des collectes dans Azure SQL. |
| `infra/`, `.github/workflows/` | Infrastructure Azure et déploiement continu. |
| `requirements.txt` | Dépendances Python de l'application. |
| `.streamlit/config.toml` | Configuration visuelle de Streamlit. |
| `.gitignore` | Exclusion des secrets, environnements locaux et fichiers temporaires. |

Les sources, thèmes et horaires de collecte peuvent être adaptés dans `Settings.py`.

### Couverture Aquaculture (élevage et transformation)

La veille combine les recherches de presse avec six flux spécialisés publics :

- [ANDA](https://anda.gov.ma/) pour les projets et annonces institutionnelles au Maroc.
- [Commission européenne — Pêche et Aquaculture](https://oceans-and-fisheries.ec.europa.eu/news_en) pour les politiques, financements et évolutions réglementaires européennes.
- [The Fish Site](https://thefishsite.com/) pour la production, la recherche et les technologies aquacoles.
- [Aquafeed.com](https://www.aquafeed.com/) pour les aliments, ingrédients et procédés de nutrition aquacole.
- [Global Seafood Alliance — Advocate](https://www.globalseafood.org/advocate/) pour la production, la durabilité et la transformation.
- [Fish Farmer](https://www.fishfarmermagazine.com/) pour les poissons d'élevage, coquillages et innovations du secteur.

Les quatre recherches complémentaires ciblent les quinze derniers jours dès la requête pour éviter que des archives occupent les résultats. La recherche marocaine sur la filière halieutique couvre aussi la production et la transformation sans imposer le mot « aquaculture » dans chaque article. Les termes techniques anglais sont reconnus, et les titres courts des flux anglophones vérifiés ne sont plus écartés faute de mots grammaticaux.

La date de publication reste celle du flux d'origine : une institution qui publie peu, comme l'ANDA, peut donc ne rien apporter sur une période courte. Le classement exige un sujet aquacole explicite. Le Signal conserve ses critères Maroc, UE ou portée mondiale documentée, sans utiliser le nom de l'éditeur comme preuve géographique ; les contenus promotionnels restent exclus. Les flux anglais suivent le circuit de traduction existant ; sans fournisseur IA disponible, leurs textes restent dans la langue d'origine.

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
