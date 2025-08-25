#!/usr/bin/env python3
"""Script de test pour vérifier que l'installation fonctionne."""

import sys
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")

# Test des imports essentiels
modules_to_test = [
    'pandas',
    'streamlit', 
    'requests',
    'pathlib',
    'json'
]

print("\n=== Test des modules ===")
for module in modules_to_test:
    try:
        __import__(module)
        print(f"✅ {module}")
    except ImportError as e:
        print(f"❌ {module}: {e}")

# Test du chemin du projet
from pathlib import Path
project_root = Path(__file__).parent
print(f"\n📁 Répertoire du projet: {project_root}")

# Vérifier les dossiers
folders_to_check = ['app', 'src', 'data']
print("\n=== Vérification des dossiers ===")
for folder in folders_to_check:
    folder_path = project_root / folder
    if folder_path.exists():
        print(f"✅ {folder}/")
    else:
        print(f"❌ {folder}/ (manquant)")

# Test de Streamlit
print("\n=== Test de Streamlit ===")
try:
    import streamlit as st
    print(f"✅ Streamlit version: {st.__version__}")
    
    # Vérifier que l'app simple existe
    simple_app = project_root / "app" / "simple_streamlit_app.py"
    if simple_app.exists():
        print(f"✅ Application simplifiée trouvée: {simple_app}")
        print("\n🚀 Pour lancer l'application, exécutez:")
        print(f"   python -m streamlit run {simple_app}")
        print("   ou double-cliquez sur launch_app.bat")
    else:
        print(f"❌ Application simplifiée non trouvée: {simple_app}")
        
except ImportError as e:
    print(f"❌ Erreur Streamlit: {e}")

print("\n" + "="*50)
print("Test terminé!")
