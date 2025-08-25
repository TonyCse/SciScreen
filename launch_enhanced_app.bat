@echo off
echo ========================================
echo    Recherche & Analyse Bibliographique
echo ========================================
echo.
echo Lancement de l'application améliorée...
echo.
echo Cette application permet de :
echo - Rechercher sur PubMed (simulation)
echo - Transformer vos fichiers Excel existants
echo - Ajouter des colonnes d'analyse étendues
echo.

cd /d "%~dp0"

REM Vérifier que les dépendances sont installées
echo Vérification des dépendances...
python -c "import pandas, streamlit, openpyxl" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Installation des dépendances manquantes...
    pip install pandas streamlit openpyxl
)

REM Lancer l'application améliorée
echo Démarrage de l'application améliorée...
python -m streamlit run app/enhanced_research_app.py --server.port 8503

REM Si Python n'est pas trouvé
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERREUR: Python n'est pas installé ou accessible.
    echo Veuillez installer Python depuis python.org
    echo.
    pause
)
