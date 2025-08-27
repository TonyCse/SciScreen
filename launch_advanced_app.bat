@echo off
echo ========================================
echo    RECHERCHE BIBLIOGRAPHIQUE AVANCEE
echo ========================================
echo.
echo Application ultra-avancee avec :
echo ✅ Vraies APIs scientifiques (OpenAlex, Semantic Scholar, PubMed, Crossref)
echo ✅ Import/customisation/export Excel complet
echo ✅ Edition interactive avec suppression de lignes
echo ✅ Export personnalise multi-feuilles
echo.

cd /d "%~dp0"

REM Vérifier que les dépendances sont installées
echo Verification des dependances...
python -c "import pandas, streamlit, openpyxl, requests, xml.etree.ElementTree" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Installation des dependances manquantes...
    pip install pandas streamlit openpyxl requests
)

REM Lancer l'application avancée
echo.
echo Demarrage de l'application avancee...
echo Acces: http://localhost:8530
echo.
python -m streamlit run app/advanced_research_app.py --server.port 8530

REM Si Python n'est pas trouvé
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERREUR: Python n'est pas installe ou accessible.
    echo Veuillez installer Python depuis python.org
    echo.
    pause
)
