# 🔍 Guide de Recherche Bibliographique Automatisée

## 🚀 Démarrage rapide

### 1. Lancer l'application
Double-cliquez sur `launch_research_app.bat` ou tapez :
```bash
python -m streamlit run app/research_app.py
```

### 2. Accéder à l'interface
Ouvrez votre navigateur sur **http://localhost:8501**

## 📋 Fonctionnalités

### ✅ **Sources de données supportées**
- **📚 PubMed** (gratuit) - Littérature biomédicale
- **🌐 OpenAlex** (gratuit) - Base bibliographique ouverte  
- **📖 Crossref** (gratuit) - Métadonnées académiques
- **🔬 Scopus** (clé API requise) - Base Elsevier

### 🔍 **Recherche automatisée**
1. **Saisissez votre requête** en anglais
2. **Choisissez la période** (années)
3. **Sélectionnez les sources** à interroger
4. **Cliquez sur "Lancer la recherche"**

### 📊 **Extraction automatique**
L'application extrait automatiquement :
- ✅ **Titre** complet
- ✅ **Résumé/Abstract**
- ✅ **Auteurs** (formatés)
- ✅ **Journal/Revue**
- ✅ **Année** de publication
- ✅ **DOI** (identifiant)
- ✅ **Nombre de citations**
- ✅ **Statut Open Access**

### 📥 **Export Excel**
- **Feuille "Résultats"** : Tous les articles
- **Feuille "Statistiques"** : Métriques de la recherche
- **Téléchargement direct** depuis l'interface

## 💡 Exemples de requêtes

### 🧠 **Recherches en psychologie/santé mentale**
```
cognitive behavioral therapy depression
mindfulness intervention anxiety
PTSD treatment veterans
eating disorders adolescents
```

### 🏥 **Recherches médicales**
```
artificial intelligence medical diagnosis
machine learning radiology
telemedicine rural healthcare
COVID-19 vaccine effectiveness
```

### 🎓 **Recherches éducatives**
```
online learning effectiveness
distance education students
educational technology impact
virtual classroom engagement
```

### 💊 **Recherches pharmacologiques**
```
antidepressant drug interactions
personalized medicine genomics
clinical trial methodology
drug discovery artificial intelligence
```

## 🔑 Configuration Scopus (optionnel)

### Obtenir une clé API Scopus
1. Allez sur **https://dev.elsevier.com/**
2. Créez un compte développeur
3. Demandez une clé API Scopus
4. Saisissez la clé dans l'interface ou le fichier `.env`

### Avantages Scopus
- ✅ **Couverture étendue** (sciences, médecine, ingénierie)
- ✅ **Métadonnées riches** (affiliations, références)
- ✅ **Métriques avancées** (h-index, impact)

## 📈 **Optimisation des recherches**

### 🎯 **Conseils pour de meilleurs résultats**
1. **Utilisez l'anglais** pour les requêtes
2. **Combinez avec AND/OR** : `therapy AND depression`
3. **Limitez la période** pour des résultats récents
4. **Testez plusieurs formulations** de la même requête

### ⚡ **Limites par source**
- **PubMed** : 200 résultats max par requête
- **OpenAlex** : 2000 résultats max
- **Crossref** : 2000 résultats max  
- **Scopus** : 200 résultats max (limite API)

### 🔍 **Syntaxe de recherche avancée**

#### PubMed
```
"systematic review"[Publication Type] AND depression
autism[MeSH Terms] AND intervention
therapy AND (anxiety OR stress)
```

#### Scopus
```
TITLE-ABS-KEY(machine AND learning AND healthcare)
AUTH(smith) AND PUBYEAR > 2020
JOURNAL("nature medicine") AND PUBYEAR = 2023
```

## 📊 **Analyse des résultats**

### 📈 **Métriques disponibles**
- **Total d'articles** trouvés
- **Répartition par source**
- **Couverture temporelle**
- **Articles avec DOI/résumé**
- **Total des citations**

### 🔍 **Filtres d'affichage**
- **Par source** : Voir seulement PubMed, Scopus, etc.
- **Par année** : Limiter à une période spécifique
- **Navigation** : Parcourir article par article

### 📖 **Détails d'articles**
- **Résumé complet** extensible
- **Liens directs** vers DOI
- **Métadonnées complètes**

## 🛠️ **Dépannage**

### ❌ **Problèmes courants**

#### "Aucun résultat trouvé"
- ✅ Vérifiez l'orthographe de la requête
- ✅ Élargissez la période de recherche
- ✅ Simplifiez les mots-clés
- ✅ Essayez des synonymes

#### "Erreur API Scopus"
- ✅ Vérifiez la clé API Scopus
- ✅ Contrôlez les quotas (limite journalière)
- ✅ Vérifiez la connexion internet

#### "Export Excel impossible"
- ✅ Fermez Excel s'il est ouvert
- ✅ Vérifiez les permissions du dossier
- ✅ Changez le nom du fichier de sortie

### 🔧 **Optimisation des performances**
- **Réduisez le nombre max** de résultats par source
- **Limitez le nombre de sources** simultanées
- **Utilisez des requêtes spécifiques** plutôt que générales

## 💾 **Sauvegarde et organisation**

### 📁 **Structure des fichiers**
```
data/
├── outputs/           # Fichiers Excel exportés
├── raw/              # Données brutes par source
└── logs/             # Journaux de recherche
```

### 📝 **Recommandations**
1. **Nommez vos exports** avec des noms descriptifs
2. **Datez vos recherches** pour le suivi
3. **Sauvegardez régulièrement** vos résultats
4. **Documentez vos requêtes** pour la reproductibilité

## 🔗 **Intégration avec d'autres outils**

### 📚 **Import dans Zotero**
Les fichiers Excel peuvent être importés dans Zotero via :
1. **Plugin Excel** pour Zotero
2. **Conversion en BibTeX** (outils tiers)
3. **Import manuel** par DOI

### 📊 **Analyse dans R/Python**
Les CSV exportés sont compatibles avec :
- **R** : `read.csv()`
- **Python** : `pandas.read_csv()`
- **SPSS/SAS** : Import direct

---

## 📞 **Support**

Pour toute question ou problème :
1. 📖 Consultez d'abord ce guide
2. 🔍 Vérifiez les messages d'erreur dans l'interface
3. 📝 Documentez les problèmes rencontrés

**🎉 Bonne recherche bibliographique !**
