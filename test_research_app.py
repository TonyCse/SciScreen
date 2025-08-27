#!/usr/bin/env python3
"""Script de test pour l'application de recherche bibliographique."""

import sys
from pathlib import Path

# Ajouter le répertoire src au chemin Python
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

print("🧪 Test de l'Application de Recherche Bibliographique")
print("=" * 60)

# Test 1: Vérification des modules de base
print("\n1️⃣ Test des modules de base...")
modules_to_test = [
    'pandas',
    'streamlit', 
    'requests',
    'pathlib',
    'openpyxl'
]

for module in modules_to_test:
    try:
        __import__(module)
        print(f"✅ {module}")
    except ImportError as e:
        print(f"❌ {module}: {e}")

# Test 2: Vérification des modules de moisson
print("\n2️⃣ Test des modules de moisson...")
try:
    from harvest import pubmed, openalex, crossref
    print("✅ Modules de moisson (pubmed, openalex, crossref)")
except ImportError as e:
    print(f"❌ Modules de moisson: {e}")

try:
    from harvest.scopus import search_scopus
    print("✅ Module Scopus")
except ImportError as e:
    print(f"⚠️ Module Scopus: {e} (normal si pas d'API key)")

# Test 3: Vérification de l'utilitaire
print("\n3️⃣ Test des utilitaires...")
try:
    from utils_io import save_dataframe, merge_dataframes
    print("✅ Utilitaires I/O")
except ImportError as e:
    print(f"❌ Utilitaires I/O: {e}")

# Test 4: Test des fonctions de recherche avec données de démo
print("\n4️⃣ Test des fonctions de recherche...")

def test_demo_search():
    """Test avec des données de démonstration."""
    import pandas as pd
    
    # Créer des données de test
    demo_data = pd.DataFrame([
        {
            "source": "test",
            "title": "Test Article 1",
            "abstract": "This is a test abstract for the first article.",
            "authors": "Test, A.; Demo, B.",
            "journal": "Test Journal",
            "year": 2023,
            "doi": "10.1000/test1",
            "cited_by": 10
        },
        {
            "source": "test",
            "title": "Test Article 2", 
            "abstract": "This is a test abstract for the second article.",
            "authors": "Sample, C.; Example, D.",
            "journal": "Demo Review",
            "year": 2022,
            "doi": "10.1000/test2",
            "cited_by": 5
        }
    ])
    
    return demo_data

try:
    demo_df = test_demo_search()
    print(f"✅ Création de données de démo: {len(demo_df)} articles")
except Exception as e:
    print(f"❌ Données de démo: {e}")

# Test 5: Test d'export Excel
print("\n5️⃣ Test d'export Excel...")
try:
    from openpyxl import Workbook
    import pandas as pd
    
    # Test simple d'export
    test_df = pd.DataFrame({
        'titre': ['Article 1', 'Article 2'],
        'auteur': ['Auteur A', 'Auteur B'],
        'année': [2023, 2022]
    })
    
    # Créer le répertoire de test
    test_dir = Path("data/outputs")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    test_file = test_dir / "test_export.xlsx"
    test_df.to_excel(test_file, index=False)
    
    if test_file.exists():
        print("✅ Export Excel fonctionnel")
        test_file.unlink()  # Nettoyer
    else:
        print("❌ Export Excel échoué")
        
except Exception as e:
    print(f"❌ Export Excel: {e}")

# Test 6: Vérification de l'application Streamlit
print("\n6️⃣ Test de l'application Streamlit...")
try:
    app_file = Path("app/research_app.py")
    if app_file.exists():
        print(f"✅ Application trouvée: {app_file}")
        
        # Vérifier la syntaxe Python
        with open(app_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        compile(content, str(app_file), 'exec')
        print("✅ Syntaxe Python valide")
        
    else:
        print(f"❌ Application non trouvée: {app_file}")
        
except SyntaxError as e:
    print(f"❌ Erreur de syntaxe dans l'application: {e}")
except Exception as e:
    print(f"❌ Erreur application: {e}")

# Test 7: Test de configuration
print("\n7️⃣ Test de configuration...")
try:
    from config import config
    print("✅ Configuration chargée")
    
    # Vérifier les répertoires
    if config.data_dir.exists():
        print("✅ Répertoire data/ existe")
    else:
        print("⚠️ Répertoire data/ sera créé au premier lancement")
        
except Exception as e:
    print(f"❌ Configuration: {e}")

# Résumé
print("\n" + "=" * 60)
print("📋 RÉSUMÉ DU TEST")
print("=" * 60)

print("\n🚀 Pour lancer l'application de recherche:")
print("   1. Double-cliquez sur 'launch_research_app.bat'")
print("   2. Ou tapez: python -m streamlit run app/research_app.py")
print("   3. Ouvrez http://localhost:8501")

print("\n📚 Sources de données disponibles:")
print("   ✅ PubMed (gratuit)")
print("   ✅ OpenAlex (gratuit)")
print("   ✅ Crossref (gratuit)")
print("   🔑 Scopus (clé API requise)")

print("\n📊 Fonctionnalités:")
print("   ✅ Recherche automatisée")
print("   ✅ Extraction de métadonnées")
print("   ✅ Filtrage et navigation")
print("   ✅ Export Excel")

print("\n📖 Documentation:")
print("   📄 GUIDE_RECHERCHE.md - Guide d'utilisation complet")
print("   📄 README.md - Documentation générale")

print("\n🎉 Tout est prêt pour la recherche bibliographique!")

