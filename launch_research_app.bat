@echo off
echo ========================================
echo    Recherche Bibliographique Automatisée
echo ========================================
echo.
echo Lancement de l'application de recherche...
echo.

cd /d "%~dp0"

REM Lancer l'application de recherche
echo Démarrage de l'application...
python -m streamlit run app/research_app.py

REM Si Python n'est pas trouvé
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERREUR: Python n'est pas installé ou accessible.
    echo Veuillez installer Python depuis python.org
    echo.
    pause
)
