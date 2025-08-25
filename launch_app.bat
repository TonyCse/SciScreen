@echo off
echo ========================================
echo    Literature Review Pipeline
echo ========================================
echo.
echo Lancement de l'application Streamlit...
echo.

cd /d "%~dp0"

REM Essayer d'abord la version simplifiée
echo Tentative avec la version simplifiée...
python -m streamlit run app/simple_streamlit_app.py

REM Si ça ne marche pas, essayer la version complète
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Tentative avec la version complète...
    python -m streamlit run app/streamlit_app.py
)

REM Si Python n'est pas trouvé
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERREUR: Python n'est pas installé ou accessible.
    echo Veuillez installer Python depuis python.org
    echo.
    pause
)
