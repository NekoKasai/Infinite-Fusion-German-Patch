#!/usr/bin/env bash
# =============================================================
#  DeepL Uebersetzer – Pokémon Infinite Fusion DE-Patch
#  Linux/macOS Version
# =============================================================
cd "$(dirname "$(realpath "$0")")" || exit 1

# Python-Befehl ermitteln (python3 bevorzugt)
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

check_python() {
    if [ -z "$PYTHON" ]; then
        echo "FEHLER: Python nicht gefunden. Bitte installieren:"
        echo "  Ubuntu/Debian:  sudo apt install python3"
        echo "  Arch:           sudo pacman -S python"
        echo "  macOS:          brew install python3"
        echo ""
        read -rp "Enter druecken zum Beenden..."
        exit 1
    fi
}

check_dat() {
    if [ ! -f "messange.dat" ]; then
        echo "FEHLER: messange.dat nicht gefunden!"
        echo "Bitte messange.dat in diesen Ordner legen:"
        echo "  $(pwd)"
        echo ""
        read -rp "Enter druecken um zum Menue zurueckzukehren..."
        return 1
    fi
    return 0
}

run_python() {
    local label="$1"
    shift
    echo ""
    echo "  ================================================================"
    echo "   Starte: $label"
    echo "   Terminal NICHT schliessen - Ausgabe erscheint direkt unten!"
    echo "  ================================================================"
    echo ""
    "$PYTHON" "$@"
    local exitcode=$?
    echo ""
    if [ $exitcode -eq 0 ]; then
        echo "  ================================================================"
        echo "   Fertig!"
        echo "  ================================================================"
    else
        echo "  ================================================================"
        echo "   FEHLER: Programm mit Code $exitcode beendet."
        echo "   Bitte Ausgabe oben pruefen."
        echo "  ================================================================"
    fi
    echo ""
    read -rp "Enter druecken um zum Menue zurueckzukehren..."
}

menu() {
    while true; do
        clear
        echo "================================================================"
        echo " DeepL Uebersetzer"
        echo " Ordner: $(pwd)"
        echo "================================================================"
        echo ""
        echo " [1] Uebersetzen MIT DeepL API-Key"
        echo "     (offizielle API, 500.000 Zeichen/Monat kostenlos)"
        echo ""
        echo " [2] Uebersetzen OHNE API-Key"
        echo "     (inoffizieller Endpunkt, kein Key noetig)"
        echo ""
        echo " [3] Nur PokeAPI-Korrekturen anwenden"
        echo "     (Poke-Namen, Attacken, Items automatisch fixen)"
        echo ""
        echo " [4] german.dat aus bearbeiteter CSV bauen"
        echo "     (CSV vorher in LibreOffice/Excel anpassen und als CSV speichern!)"
        echo ""
        echo " [5] PokeAPI-Cache aktualisieren"
        echo ""
        echo " [6] Beenden"
        echo ""
        read -rp "Auswahl eingeben (1-6): " WAHL

        case "$WAHL" in
            1)
                check_python || continue
                check_dat || continue
                if ! "$PYTHON" -c "import deepl" &>/dev/null; then
                    echo "deepl-Paket wird installiert..."
                    pip3 install deepl || pip install deepl
                    echo ""
                fi
                run_python "Uebersetze mit API-Key" translate_deepl.py
                ;;
            2)
                check_python || continue
                check_dat || continue
                run_python "Uebersetze ohne API-Key" translate_deepl.py --no-key
                ;;
            3)
                check_python || continue
                if [ ! -f "translations.csv" ]; then
                    echo "FEHLER: translations.csv nicht gefunden!"
                    echo "Bitte zuerst uebersetzen (Option 1 oder 2)."
                    echo ""
                    read -rp "Enter druecken..."
                    continue
                fi
                run_python "PokeAPI-Korrekturen anwenden" translate_deepl.py --fix-only
                ;;
            4)
                check_python || continue
                if [ ! -f "translations.csv" ]; then
                    echo "FEHLER: translations.csv nicht gefunden!"
                    echo "Bitte zuerst uebersetzen (Option 1 oder 2)."
                    echo ""
                    read -rp "Enter druecken..."
                    continue
                fi
                run_python "Baue german.dat aus CSV" translate_deepl.py --build
                ;;
            5)
                check_python || continue
                run_python "PokeAPI-Cache aktualisieren" translate_deepl.py --fix-only --refresh-cache
                ;;
            6)
                echo "Tschuess!"
                exit 0
                ;;
            *)
                echo "Ungueltige Auswahl."
                sleep 1
                ;;
        esac
    done
}

check_python
menu
