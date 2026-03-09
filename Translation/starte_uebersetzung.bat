@echo off
chcp 65001 >nul
cd /d "%~dp0"
setlocal EnableDelayedExpansion

:: ================================================================
:MENU
cls
title  PokeMMO - DeepL Uebersetzer

echo.
echo  +======================================================+
echo  ^|       POKEMMO  -  DeepL Uebersetzer                 ^|
echo  +======================================================+
echo  ^|                                                      ^|
echo  ^|  [1]  Uebersetzen  MIT  DeepL API-Key               ^|
echo  ^|       Offiziell - 500.000 Zeichen/Monat kostenlos   ^|
echo  ^|                                                      ^|
echo  ^|  [2]  Uebersetzen  OHNE  API-Key                    ^|
echo  ^|       Inoffiziell - kein Key benoetigt              ^|
echo  ^|                                                      ^|
echo  ^|  [3]  Nur PokeAPI-Korrekturen anwenden              ^|
echo  ^|       Namen, Attacken, Items automatisch fixen       ^|
echo  ^|                                                      ^|
echo  ^|  [4]  german.dat aus bearbeiteter CSV bauen          ^|
echo  ^|       CSV vorher in Excel anpassen, dann hier bauen  ^|
echo  ^|                                                      ^|
echo  ^|  [5]  PokeAPI-Cache aktualisieren                   ^|
echo  ^|                                                      ^|
echo  ^|  [6]  Beenden                                        ^|
echo  ^|                                                      ^|
echo  +======================================================+
echo.
set /p "WAHL=  Auswahl (1-6) > "

if "!WAHL!"=="1" goto MIT_KEY
if "!WAHL!"=="2" goto OHNE_KEY
if "!WAHL!"=="3" goto FIX_ONLY
if "!WAHL!"=="4" goto BAUEN
if "!WAHL!"=="5" goto CACHE
if "!WAHL!"=="6" exit /b 0

echo.
echo  [!] Ungueltige Auswahl. Bitte 1-6 eingeben.
timeout /t 2 >nul
goto MENU


:: ================================================================
:MIT_KEY
call :CHECK_PYTHON  || goto ENDE
call :CHECK_DAT     || goto ENDE

python -c "import deepl" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [*] deepl-Paket wird installiert...
    pip install deepl
    echo.
)
set "PY_LABEL=Uebersetze MIT API-Key"
set "PY_CMD=translate_deepl.py"
call :RUN
goto ENDE

:: ================================================================
:OHNE_KEY
call :CHECK_PYTHON  || goto ENDE
call :CHECK_DAT     || goto ENDE

set "PY_LABEL=Uebersetze OHNE API-Key"
set "PY_CMD=translate_deepl.py --no-key"
call :RUN
goto ENDE

:: ================================================================
:FIX_ONLY
call :CHECK_PYTHON  || goto ENDE

if not exist "translations.csv" (
    call :ERROR "translations.csv nicht gefunden! Bitte zuerst uebersetzen (Option 1 oder 2)."
    goto ENDE
)
set "PY_LABEL=PokeAPI-Korrekturen anwenden"
set "PY_CMD=translate_deepl.py --fix-only"
call :RUN
goto ENDE

:: ================================================================
:BAUEN
call :CHECK_PYTHON  || goto ENDE

if not exist "translations.csv" (
    call :ERROR "translations.csv nicht gefunden! Bitte zuerst uebersetzen (Option 1 oder 2)."
    goto ENDE
)
set "PY_LABEL=Baue german.dat aus CSV"
set "PY_CMD=translate_deepl.py --build"
call :RUN
goto ENDE

:: ================================================================
:CACHE
call :CHECK_PYTHON  || goto ENDE

set "PY_LABEL=PokeAPI-Cache aktualisieren"
set "PY_CMD=translate_deepl.py --fix-only --refresh-cache"
call :RUN
goto ENDE


:: ================================================================
:RUN
cls
title  PokeMMO - %PY_LABEL% [laeuft...]

echo.
echo  +======================================================+
echo  ^|  Starte: !PY_LABEL!
echo  ^|  Fenster NICHT schliessen - Ausgabe erscheint unten
echo  +======================================================+
echo.

python %PY_CMD%
set "EXITCODE=!errorlevel!"

echo.
if !EXITCODE!==0 (
    title  PokeMMO - Fertig!
    echo  +======================================================+
    echo  ^|  FERTIG! german.dat wurde erfolgreich erstellt.
    echo  +======================================================+
) else (
    title  PokeMMO - Fehler
    echo  +======================================================+
    echo  ^|  FEHLER! Programm mit Code !EXITCODE! beendet.
    echo  ^|  Bitte Ausgabe oben pruefen.
    echo  +======================================================+
)
exit /b !EXITCODE!


:: ================================================================
:CHECK_PYTHON
python --version >nul 2>&1
if errorlevel 1 (
    call :ERROR "Python nicht gefunden. Bitte installieren: https://www.python.org/downloads/"
    exit /b 1
)
exit /b 0

:CHECK_DAT
if not exist "messange.dat" (
    call :ERROR "messange.dat nicht gefunden! Bitte in diesen Ordner legen: %~dp0"
    exit /b 1
)
exit /b 0

:ERROR
echo.
echo  +======================================================+
echo  ^|  FEHLER: %~1
echo  +======================================================+
echo.
pause
exit /b 0


:: ================================================================
:ENDE
echo.
echo  Druecke eine Taste um zum Menue zurueckzukehren...
pause >nul
goto MENU
