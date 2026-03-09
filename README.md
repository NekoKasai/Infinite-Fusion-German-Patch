# Pokémon Infinite Fusion – Deutsch-Patch

> ⚠️ **ALPHA-VERSION** – Dieser Patch befindet sich noch in der frühen Entwicklung.
> Fehler in der Übersetzung sind zu erwarten. Ich übernehme **keinerlei Garantie** für
> Korrektheit, Vollständigkeit oder Spielbarkeit. **Erstellt immer ein Backup eures
> Spielstands und Spielordners, bevor ihr den Patch anwendet!**

Installiert die **deutsche Übersetzung** automatisch in dein InfiniteFusion-Spielverzeichnis.

## Getestete Version

Dieser Patch wurde ausschließlich mit **Pokémon Infinite Fusion v6.7.2** getestet.  
Andere Versionen können funktionieren, werden aber nicht offiziell unterstützt.
Abweichungen oder Fehler bei anderen Versionen sind möglich.

## Voraussetzungen

- **Python 3.10 oder neuer** (https://www.python.org/downloads/)  
  → Bei der Installation bitte **"Add Python to PATH"** aktivieren!  
  → Empfohlen: Python 3.11 oder 3.12 für beste Kompatibilität

## Backup erstellen (Wichtig!)

Bevor du den Patch installierst, sichere deinen Spielordner:

1. Den gesamten `InfiniteFusion`-Ordner kopieren und irgendwo sicher ablegen
2. Speicherstände befinden sich unter `savefiles/` – diese ebenfalls separat sichern

Das Install-Script legt zwar automatisch `.bak`-Dateien an, aber ein vollständiges
Backup schützt vor unvorhergesehenen Problemen.

## Installation (Einfach)

1. Diesen Ordner (`DE_Patch`) irgendwo auf deinem PC ablegen
2. **`install.bat`** doppelklicken
3. Pfad zum Spielordner eingeben (z.B. `C:\Games\InfiniteFusion`)
4. Fertig – das Spiel startet jetzt auf Deutsch!

## Was wird geändert?

| Datei | Änderung |
|-------|----------|
| `Data/german.dat` | Deutsche Übersetzung (wird kopiert) |
| `Data/english.dat` | Englisch-Stub (wird angelegt) |
| `Data/Scripts/GermanLanguagePatch.rb` | Sprachpersistenz-Modul (wird kopiert) |
| `Data/Scripts/001_Settings.rb` | LANGUAGES-Array wird ergänzt |
| `Data/Scripts/999_Main/999_Main.rb` | Sprache beim Start laden |
| `Data/Scripts/052_InfiniteFusion/System/MultiSaves.rb` | Sprachwahl speichern |
| `Data/Scripts/016_UI/013_UI_Load.rb` | Sprachwahl speichern |

Von jeder geänderten Datei wird **automatisch eine `.bak`-Sicherungskopie** angelegt.

## Sprache wechseln

Im Spiel → Titelbildschirm → **Language** → gewünschte Sprache wählen.  
Die Wahl wird gespeichert und beim nächsten Start automatisch geladen.

## Manuelle Installation (Fortgeschrittene)

```
python apply_patch.py --game "C:\Pfad\zum\InfiniteFusion"
```

Optionen:
- `--dry-run`  –  Nur anzeigen was gemacht würde, ohne Dateien zu ändern

## Übersetzung selbst erstellen / aktualisieren

Die Übersetzung wird mit dem Script `Translation/starte_uebersetzung.bat` erstellt.

**Benötigt zusätzlich:**
- `Translation/messange.dat` (aus dem Spielordner kopieren)
- Einen DeepL-Account (kostenlos, 500.000 Zeichen/Monat) oder Nutzung ohne Key

**Hinweis zur Übersetzungsqualität:**
Die Übersetzung wird automatisch per KI (DeepL) erstellt und anschließend mit
offiziellen Pokémon-Begriffen von PokéAPI korrigiert. Trotzdem können Fehler
auftreten, z.B.:

- Falsche Grammatik oder unnatürliche Formulierungen
- Spielspezifische Begriffe die falsch oder gar nicht übersetzt wurden
- Eigennamen von Charakteren oder Orten die nicht erkannt wurden
- Kontext-Fehler bei mehrdeutigen Sätzen

Die `translations.csv` kann in Excel geöffnet und manuell nachbearbeitet werden.
Danach mit Option **[4] german.dat aus CSV bauen** die Datei aktualisieren.

## Mithilfe bei der Übersetzung

Du möchtest bei der Übersetzung helfen? Melde dich gerne auf **Discord** unter **shirokazetv**!

## Probleme?

- **"Python ist nicht installiert"**: Python 3.10+ von https://www.python.org/downloads/ herunterladen, bei Installation "Add Python to PATH" aktivieren.
- **Spiel startet noch auf Englisch**: Titelbildschirm → Language → Deutsch wählen.
- **Zurücksetzen**: Alle `.bak`-Dateien umbenennen (`.bak` entfernen) um den Originalzustand wiederherzustellen.
- **Übersetzungsfehler gefunden**: `Translation/translations.csv` in Excel öffnen, Fehler in der DE-Spalte korrigieren, speichern, dann `starte_uebersetzung.bat` → Option [4] ausführen.
