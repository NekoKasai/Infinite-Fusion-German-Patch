#!/usr/bin/env bash
# =============================================================
#  Pokémon Infinite Fusion – Deutsch-Patch
#  Linux/macOS Version
# =============================================================
cd "$(dirname "$(realpath "$0")")" || exit 1

echo ""
echo "============================================================"
echo "  Pokemon Infinite Fusion - Deutsch-Patch"
echo "============================================================"
echo ""

# Python-Befehl ermitteln (python3 bevorzugt)
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[FEHLER] Python ist nicht installiert oder nicht im PATH."
    echo ""
    echo "Bitte Python 3 installieren:"
    echo "  Ubuntu/Debian:  sudo apt install python3"
    echo "  Arch:           sudo pacman -S python"
    echo "  macOS:          brew install python3"
    echo ""
    read -rp "Enter druecken zum Beenden..."
    exit 1
fi

echo "Python gefunden ($($PYTHON --version 2>&1)). Starte Patcher..."
echo ""

"$PYTHON" "$(dirname "$0")/apply_patch.py" "$@"
EXIT=$?

echo ""
read -rp "Enter druecken zum Schliessen..."
exit $EXIT
