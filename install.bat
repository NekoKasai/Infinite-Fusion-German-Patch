@echo off
chcp 65001 > nul
title Pok├®mon Infinite Fusion ÔÇô Deutsch-Patch

echo.
echo ÔòöÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòù
echo Ôòæ   Pok├®mon Infinite Fusion ÔÇô Deutsch-Patch       Ôòæ
echo ÔòÜÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòØ
echo.

:: Pr├╝fen ob Python installiert ist
python --version > nul 2>&1
if errorlevel 1 (
    echo [FEHLER] Python ist nicht installiert oder nicht im PATH.
    echo.
    echo Bitte Python 3 von https://www.python.org/downloads/ herunterladen
    echo und bei der Installation "Add Python to PATH" aktivieren.
    echo.
    pause
    exit /b 1
)

echo Python gefunden. Starte Patcher...
echo.

python "%~dp0apply_patch.py" %*

:: Falls apply_patch.py ohne --dry-run keinen Fehler warf, sind wir fertig.
:: Das finally-Block im Python-Script macht selbst "Dr├╝cke Enter".
