# Literature Review Pipeline

🔬 **Pipeline automatisé pour revues de littérature scientifique**

Un système complet et reproductible pour automatiser le processus de revue de littérature, de la recherche bibliographique jusqu'à l'intégration Zotero, en passant par le tri intelligent et la génération de rapports PRISMA.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Poetry](https://img.shields.io/badge/dependency%20management-poetry-blue)](https://python-poetry.org/)

## ✨ Fonctionnalités

### 🔍 Moisson multi-sources
- **OpenAlex**: Base bibliographique complète et ouverte
- **Crossref**: Métadonnées académiques
- **PubMed**: Littérature biomédicale
- **Unpaywall**: Informations sur l'accès ouvert

### 🧹 Traitement intelligent
- **Normalisation** automatique des métadonnées
- **Déduplication** avancée (DOI/PMID exact + titres similaires)
- **Filtrage** configurable (langue, type, année, etc.)
- **Enrichissement** avec métadonnées complémentaires

### 🤖 Tri assisté par IA
- **Modèle ML** entraînable (TF-IDF + LogisticRegression)
- **Scoring automatique** basé sur la pertinence
- **Interface Streamlit** pour tri manuel
- **Raisons explicites** pour chaque recommandation

### 📊 Reporting PRISMA
- **Diagramme PRISMA** auto-généré
- **Rapport complet** en Markdown/HTML
- **Statistiques détaillées** (journaux, auteurs, citations)
- **Métriques de qualité** du processus

### 🔗 Intégration Zotero
- **Création automatique** de collections
- **Import structuré** des références
- **Gestion des tags** et métadonnées
- **Attachement PDF** automatique

## 🚀 Installation rapide

### Prérequis
- Python 3.11+
- Poetry (recommandé) ou pip
- R 4.0+ (optionnel)

### Installation avec Poetry
```bash
# Cloner le projet
git clone https://github.com/votre-repo/lit-review-pipeline.git
cd lit-review-pipeline

# Installer les dépendances
make setup
# ou manuellement:
poetry install
poetry run pre-commit install
```

### Installation avec pip
```bash
pip install -r requirements.txt  # À générer depuis pyproject.toml
```

## ⚙️ Configuration

### 1. Variables d'environnement
Copiez `.env.example` vers `.env` et configurez vos API :

```bash
cp env.example .env
```

```env
# APIs requises
UNPAYWALL_EMAIL=votre.email@domaine.com
CROSSREF_MAILTO=votre.email@domaine.com
PUBMED_EMAIL=votre.email@domaine.com

# Zotero (optionnel)
ZOTERO_USER_ID=votre_user_id
ZOTERO_API_KEY=votre_api_key

# Paramètres par défaut
QUERY="cognitive behavioral therapy AND depression"
YEAR_FROM=2015
YEAR_TO=2025
LANGS=en,fr
```

### 2. Obtenir les clés API

#### Zotero
1. Allez sur [zotero.org/settings/keys](https://www.zotero.org/settings/keys)
2. Créez une nouvelle clé avec accès lecture/écriture
3. Trouvez votre User ID dans l'URL de votre profil

#### Emails requis
- **Unpaywall/Crossref**: Email pour identifier les requêtes (gratuit)
- **PubMed**: Email pour le rate limiting (gratuit)

## 🎯 Utilisation

### Workflow complet (1 commande)
```bash
make run QUERY="machine learning AND healthcare" YEAR_FROM=2020 YEAR_TO=2024
```

### Étapes individuelles

#### 1. Moisson des articles
```bash
# Recherche multi-sources
make harvest QUERY="votre requête" YEAR_FROM=2020 YEAR_TO=2024

# Ou avec la CLI
poetry run python -m src.cli harvest \
  --query "deep learning AND medical diagnosis" \
  --year-from 2020 --year-to 2024 \
  --langs en,fr --top-n 1000
```

#### 2. Traitement des données
```bash
# Pipeline complet (normalisation → déduplication → filtrage → scoring)
make process

# Ou avec options
poetry run python -m src.cli process --allow-preprints false
```

#### 3. Tri manuel (Streamlit)
```bash
# Lance l'interface web
make screen

# Accédez à http://localhost:8501
```

#### 4. Intégration Zotero
```bash
# Pousse les articles retenus
make zotero ZOTERO_COLLECTION="Ma Revue 2024"

# Ou avec la CLI
poetry run python -m src.cli zotero-push \
  --collection "Systematic Review 2024" \
  --tags "systematic-review,included"
```

#### 5. Génération des rapports
```bash
# Génère PRISMA + rapport complet
make report

# Fichiers créés :
# - data/outputs/prisma.png
# - data/outputs/report.md
# - data/outputs/report.html
```

## 📁 Structure du projet

```
lit-review-pipeline/
├── data/
│   ├── raw/           # Données brutes par source
│   ├── interim/       # Données intermédiaires
│   ├── processed/     # Données finales nettoyées
│   ├── outputs/       # Excel, rapports, PRISMA
│   └── logs/          # Logs détaillés
├── models/
│   └── screening_model.joblib  # Modèle ML entraîné
├── src/
│   ├── harvest/       # Modules de moisson
│   ├── pipeline/      # Traitement des données
│   ├── zotero/        # Intégration Zotero
│   ├── config.py      # Configuration centralisée
│   └── cli.py         # Interface ligne de commande
├── app/
│   └── streamlit_app.py  # Interface de tri
├── r/
│   └── dedup.R        # Alternative R (optionnel)
└── tests/             # Tests unitaires
```

## 🔬 Exemples de requêtes

### Recherches biomédicales
```bash
# Thérapie cognitivo-comportementale
QUERY="cognitive behavioral therapy AND (depression OR anxiety)"

# IA en santé
QUERY="artificial intelligence AND healthcare AND diagnosis"

# Interventions numériques
QUERY="digital health interventions AND mental health"
```

### Recherches technologiques
```bash
# Machine learning
QUERY="machine learning AND (prediction OR classification)"

# Réseaux de neurones
QUERY="neural networks AND deep learning"
```

### Syntaxe avancée
```bash
# Exclusions
QUERY="therapy AND depression NOT medication"

# Recherche exacte
QUERY="\"systematic review\" AND \"meta-analysis\""

# Proximité
QUERY="cognitive NEAR/3 behavioral"
```

## 🎛️ Interface Streamlit

L'interface web permet un tri interactif des articles :

### Fonctionnalités
- **Navigation fluide** entre les articles
- **Filtres dynamiques** (année, source, confiance IA)
- **Décisions rapides** : ✅ Inclure / ❌ Exclure / 🤷 Incertain
- **Notes personnalisées** par article
- **Progression en temps réel**
- **Export automatique** des décisions

### Captures d'écran
- Affichage détaillé des métadonnées
- Liens directs vers DOI/PDF
- Recommandations IA avec explications
- Tableau de bord des statistiques

## 🤖 Machine Learning

### Modèle par défaut
- **Vectorisation** : TF-IDF (titres + résumés)
- **Classificateur** : Régression logistique
- **Features** : Unigrammes + bigrammes
- **Équilibrage** : Pondération automatique des classes

### Entraînement personnalisé
Placez vos données d'entraînement dans `data/processed/labeled_history.csv` :

```csv
title,abstract,label,year,journal
"Efficacy of CBT for depression","CBT shows significant...",1,2023,"J Clinical Psych"
"Database optimization","Query performance...",0,2022,"ACM Computing"
```

Le modèle se réentraîne automatiquement si ce fichier existe.

### Fallback intelligent
Sans modèle entraîné, utilise la similarité TF-IDF avec la requête de recherche.

## 📊 Métriques et reporting

### Métriques collectées
- **Moisson** : nombre d'articles par source
- **Déduplication** : doublons exacts/fuzzy supprimés
- **Filtrage** : exclusions par règle
- **Enrichissement** : métadonnées ajoutées
- **Tri** : recommandations IA vs décisions manuelles

### Diagramme PRISMA automatique
Génération conforme aux guidelines PRISMA 2020 :
- Identification (sources multiples)
- Screening (automatique + manuel)
- Eligibilité (critères d'inclusion)
- Inclusion finale

### Rapports détaillés
- **Méthodologie** complète
- **Statistiques descriptives**
- **Top journaux/auteurs**
- **Analyse des citations**
- **Distribution temporelle**

## 🔧 Alternative R

Pour les utilisateurs R, un script de déduplication est disponible :

```bash
# Utilisation directe
Rscript r/dedup.R data/raw/papers.csv data/processed/deduplicated.csv 0.85

# Intégration dans le pipeline
make r-dedup
```

### Fonctionnalités R
- Déduplication exacte (DOI/PMID)
- Similarité de titres (Jaro-Winkler)
- Sélection du meilleur enregistrement
- Export CSV compatible

## 🧪 Tests et qualité

### Lancer les tests
```bash
# Tests complets
make test

# Tests avec couverture
poetry run pytest --cov=src tests/

# Tests spécifiques
poetry run pytest tests/test_deduplicate.py -v
```

### Outils de qualité
```bash
# Linting et formatage
make lint
make format

# Pré-commit automatique
poetry run pre-commit run --all-files
```

## 🔍 Dépannage

### Problèmes courants

#### Erreurs d'API
```bash
# Vérifiez votre configuration
python -c "from src.config import config; print(config.validate_api_credentials())"

# Test de connexion Zotero
python -c "from src.zotero.zotero_client import test_zotero_connection; test_zotero_connection()"
```

#### Mémoire insuffisante
```python
# Réduisez la taille des lots dans .env
BATCH_SIZE=50
MAX_WORKERS=2
TOP_N=500
```

#### Performance lente
```python
# Optimisations
RATE_LIMIT_DELAY=0.5  # Requêtes plus rapides (attention aux limites)
USE_CROSSREF=false    # Désactiver l'enrichissement Crossref
USE_UNPAYWALL=false   # Désactiver l'enrichissement Unpaywall
```

### Logs détaillés
```bash
# Logs en temps réel
tail -f data/logs/pipeline.log

# Niveau de debug
export LOG_LEVEL=DEBUG
```

## 🤝 Contribution

### Setup développeur
```bash
# Installation complète
poetry install --dev
pre-commit install

# Lancement des tests
make test

# Vérification qualité
make lint
```

### Guidelines
1. **Tests** : Ajoutez des tests pour nouvelles fonctionnalités
2. **Documentation** : Mettez à jour docstrings et README
3. **Formatage** : Utilisez black/isort (automatique avec pre-commit)
4. **Commits** : Messages descriptifs en anglais

### Structure des contributions
- `src/harvest/` : Nouveaux connecteurs API
- `src/pipeline/` : Algorithmes de traitement
- `app/` : Améliorations interface
- `tests/` : Tests unitaires
- `docs/` : Documentation additionnelle

## 📝 Licence

MIT License - voir [LICENSE](LICENSE) pour détails.

## 📚 Références

### APIs utilisées
- [OpenAlex](https://openalex.org/) - Base bibliographique ouverte
- [Crossref](https://www.crossref.org/documentation/retrieve-metadata/) - Métadonnées académiques
- [PubMed E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/) - Littérature biomédicale
- [Unpaywall](https://unpaywall.org/products/api) - Accès ouvert
- [Zotero Web API](https://www.zotero.org/support/dev/web_api/v3/start) - Gestion bibliographique

### Standards suivis
- [PRISMA 2020](http://www.prisma-statement.org/) - Reporting des revues systématiques
- [OpenAPI 3.0](https://swagger.io/specification/) - Documentation API
- [Semantic Versioning](https://semver.org/) - Versioning
- [Conventional Commits](https://www.conventionalcommits.org/) - Format des commits

## 💬 Support

### Documentation
- 📖 [Wiki complet](https://github.com/votre-repo/lit-review-pipeline/wiki)
- 🎥 [Tutoriels vidéo](https://youtube.com/playlist?list=...)
- 📋 [Exemples d'usage](https://github.com/votre-repo/lit-review-pipeline/tree/main/examples)

### Communauté
- 💬 [Discussions GitHub](https://github.com/votre-repo/lit-review-pipeline/discussions)
- 🐛 [Issues & bugs](https://github.com/votre-repo/lit-review-pipeline/issues)
- 📧 Email : support@votre-domaine.com

---

**🎉 Automatisez vos revues de littérature et concentrez-vous sur l'analyse !**

*Développé avec ❤️ pour la communauté de recherche scientifique*
#   S c i S c r e e n 
 
 