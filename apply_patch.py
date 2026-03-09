#!/usr/bin/env python3
"""
apply_patch.py  ÔÇô  Deutsch-Patch f├╝r Pok├®mon Infinite Fusion
=============================================================

Dieses Script installiert die deutsche ├£bersetzung automatisch in ein
beliebiges InfiniteFusion-Spielverzeichnis.

Was wird gemacht:
  1. german.dat   ÔåÆ Data/german.dat kopieren
  2. english.dat  ÔåÆ Data/english.dat kopieren (Stub, 4 Bytes)
  3. GermanLanguagePatch.rb in den richtigen Script-Ordner kopieren
  4. LANGUAGES-Array in Data/Scripts/001_Settings.rb patchen
  5. set_up_system in MultiSaves.rb patchen (safeExists? + clamp)
  6. cmd_language Handler in MultiSaves.rb patchen (Persistenz)
  7. set_up_system in 001_StartGame.rb patchen (Fallback)
  8. 999_Main.rb patchen (pbApplyLanguagePreference beim Start)
  9. cmd_language in 013_UI_Load.rb patchen (Persistenz)
 10. Spielstand-unabh├ñngige Sprachpr├ñferenz: language_preference.dat = Deutsch

AUSF├£HRUNG:
  python apply_patch.py --game C:\\Pfad\\zum\\InfiniteFusion-Ordner

  Oder ohne --game: fragt interaktiv nach dem Pfad.

  --dry-run   Zeigt was gemacht w├╝rde, ohne Dateien zu ├ñndern.
"""

import os, sys, re, shutil, argparse, traceback

PATCH_DIR = os.path.dirname(os.path.abspath(__file__))

# ÔöÇÔöÇÔöÇ Farben (Windows-kompatibel) ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
def green(s):  return f"\033[92m{s}\033[0m"
def yellow(s): return f"\033[93m{s}\033[0m"
def red(s):    return f"\033[91m{s}\033[0m"
def bold(s):   return f"\033[1m{s}\033[0m"

results = []   # (status, message) f├╝r Abschlussbericht


def report(status, msg):
    results.append((status, msg))
    sym = {"OK": green("Ô£ô"), "SKIP": yellow("~"), "WARN": yellow("!"), "ERR": red("Ô£ù")}
    print(f"  {sym.get(status, '?')} [{status:4}] {msg}")


# ===========================================================================
#  Datei-Hilfsfunktionen
# ===========================================================================

def backup(path):
    """Legt eine .bak-Kopie an, falls noch keine existiert."""
    bak = path + ".bak"
    if not os.path.exists(bak) and os.path.exists(path):
        shutil.copy2(path, bak)


def find_file(game_dir, *rel_parts):
    """Sucht eine Datei relativ zu game_dir, toleriert unterschiedliche Ordnernamen."""
    path = os.path.join(game_dir, *rel_parts)
    if os.path.exists(path):
        return path
    return None


def find_script(game_dir, filename):
    """
    Sucht eine .rb-Datei irgendwo unter Data/Scripts/.
    Gibt den vollst├ñndigen Pfad zur├╝ck oder None.
    """
    scripts_root = os.path.join(game_dir, "Data", "Scripts")
    if not os.path.isdir(scripts_root):
        return None
    for root, dirs, files in os.walk(scripts_root):
        if filename in files:
            return os.path.join(root, filename)
    return None


def read_text(path):
    for enc in ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1'):
        try:
            with open(path, encoding=enc) as f:
                return f.read(), enc
        except UnicodeDecodeError:
            continue
    return None, None


def write_text(path, content, encoding='utf-8'):
    with open(path, 'w', encoding=encoding, newline='\n') as f:
        f.write(content)


# ===========================================================================
#  Patch-Operationen
# ===========================================================================

def copy_data_file(src_name, game_dir, dry_run):
    """Kopiert eine Datei aus dem Patch-Ordner nach Data/."""
    src = os.path.join(PATCH_DIR, "Data", src_name)
    dst = os.path.join(game_dir, "Data", src_name)
    if not os.path.exists(src):
        report("WARN", f"Patch-Datei fehlt: Data/{src_name} (├╝bersprungen)")
        return
    if dry_run:
        report("SKIP", f"[DRY-RUN] w├╝rde kopieren: Data/{src_name}")
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    report("OK", f"Data/{src_name} kopiert ({os.path.getsize(dst):,} Bytes)")


def copy_script_file(src_name, game_dir, dry_run):
    """
    Kopiert GermanLanguagePatch.rb in den richtigen Scripts-Unterordner.
    Sucht zuerst ob die Datei schon existiert (Update), sonst legt sie
    in 052_InfiniteFusion/System/ ab falls vorhanden, sonst direkt unter Scripts/.
    """
    src = os.path.join(PATCH_DIR, "Data", "Scripts", src_name)
    if not os.path.exists(src):
        report("WARN", f"Patch-Script fehlt: {src_name} (├╝bersprungen)")
        return

    # Schon vorhanden? ÔåÆ an selber Stelle updaten
    existing = find_script(game_dir, src_name)
    if existing:
        dst = existing
    else:
        # Bevorzugter Ort
        preferred = os.path.join(game_dir, "Data", "Scripts",
                                 "052_InfiniteFusion", "System", src_name)
        fallback  = os.path.join(game_dir, "Data", "Scripts", src_name)
        parent = os.path.join(game_dir, "Data", "Scripts", "052_InfiniteFusion", "System")
        dst = preferred if os.path.isdir(parent) else fallback

    if dry_run:
        report("SKIP", f"[DRY-RUN] w├╝rde kopieren: Scripts/{src_name} ÔåÆ {os.path.relpath(dst, game_dir)}")
        return

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    backup(dst)
    shutil.copy2(src, dst)
    report("OK", f"Scripts/{src_name} installiert ({os.path.relpath(dst, game_dir)})")


def patch_settings(game_dir, dry_run):
    """
    001_Settings.rb: LANGUAGES-Array auf EN/DE/FR setzen.
    Erkennt sowohl einfache als auch vorhandene Definitionen.
    """
    path = find_script(game_dir, "001_Settings.rb")
    if not path:
        report("ERR", "001_Settings.rb nicht gefunden ÔÇô LANGUAGES nicht gepacht")
        return

    content, enc = read_text(path)
    if content is None:
        report("ERR", "001_Settings.rb konnte nicht gelesen werden")
        return

    # Pr├╝fen ob schon gepacht
    if '"german.dat"' in content and '"english.dat"' in content:
        report("SKIP", "001_Settings.rb: LANGUAGES bereits gepacht")
        return

    new_languages = (
        '  LANGUAGES = [\n'
        '      ["English",  "english.dat"],\n'
        '      ["Deutsch",  "german.dat"],\n'
        '      ["Fran\\u00e7ais", "french.dat"]\n'
        '  ]\n'
    )

    # Suche bestehende LANGUAGES-Definition und ersetze sie
    pattern = re.compile(
        r'[ \t]*LANGUAGES\s*=\s*\[.*?\]\s*\n',
        re.DOTALL
    )
    if pattern.search(content):
        new_content = pattern.sub(new_languages, content, count=1)
    else:
        # F├╝ge vor dem letzten 'end' des Settings-Moduls ein
        new_content = content.rstrip() + "\n\n" + new_languages + "\n"

    if dry_run:
        report("SKIP", "[DRY-RUN] 001_Settings.rb: LANGUAGES w├╝rde gepacht")
        return

    backup(path)
    write_text(path, new_content, enc or 'utf-8')
    report("OK", "001_Settings.rb: LANGUAGES auf EN/DE/FR gesetzt")


# ÔöÇÔöÇÔöÇ MultiSaves.rb ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

MULTISAVES_SET_UP_PATCH = '''
    if Settings::LANGUAGES.length >= 2
      $PokemonSystem.language = pbChooseLanguage if save_data.empty?
      # Clamp language index in case LANGUAGES array changed since last save
      lang_idx = ($PokemonSystem.language.to_i).clamp(0, Settings::LANGUAGES.length - 1)
      $PokemonSystem.language = lang_idx
      langFile = 'Data/' + Settings::LANGUAGES[lang_idx][1]
      pbLoadMessages(langFile) if safeExists?(langFile)
    end
'''

MULTISAVES_CMD_LANGUAGE_PATCH = r'''        when cmd_language
          @scene.pbEndScene
          chosen = pbChooseLanguage
          $PokemonSystem.language = chosen
          langLog("cmd_language (MultiSaves): lang=#{chosen}") if defined?(langLog)
          lang_file = 'Data/' + Settings::LANGUAGES[$PokemonSystem.language][1]
          pbLoadMessages(lang_file) if safeExists?(lang_file)
          pbSaveLanguagePreference($PokemonSystem.language) if defined?(pbSaveLanguagePreference)
          if show_continue
            @save_data[:pokemon_system] = $PokemonSystem
            File.open(SaveData.get_full_path(@selected_file), 'wb') { |file| Marshal.dump(@save_data, file) }
          end
'''


def patch_multisaves(game_dir, dry_run):
    path = find_script(game_dir, "MultiSaves.rb")
    if not path:
        report("WARN", "MultiSaves.rb nicht gefunden ÔÇô ├╝bersprungen")
        return

    content, enc = read_text(path)
    if content is None:
        report("ERR", "MultiSaves.rb konnte nicht gelesen werden")
        return

    changed = False

    # 1. set_up_system: safeExists? + clamp
    if 'safeExists?(langFile)' not in content:
        old = re.search(
            r'([ \t]*if Settings::LANGUAGES\.length >= 2\s*\n'
            r'[ \t]*\$PokemonSystem\.language = pbChooseLanguage if save_data\.empty\?\s*\n'
            r'[^\n]*\n'
            r'[ \t]*langFile\s*=\s*[^\n]+\n'
            r'[ \t]*pbLoadMessages[^\n]+\n'
            r'[ \t]*end\s*\n)',
            content, re.MULTILINE
        )
        if old:
            content = content[:old.start()] + MULTISAVES_SET_UP_PATCH + content[old.end():]
            changed = True
        else:
            report("WARN", "MultiSaves.rb: set_up_system-Block nicht eindeutig erkennbar ÔÇô manuell pr├╝fen")

    # 2. cmd_language: Persistenz
    if 'pbSaveLanguagePreference' not in content:
        old = re.search(
            r'[ \t]*when cmd_language\s*\n'
            r'[ \t]*@scene\.pbEndScene\s*\n'
            r'[ \t]*chosen = pbChooseLanguage\s*\n'
            r'[ \t]*\$PokemonSystem\.language = chosen\s*\n'
            r'(.*?\n)*?'   # beliebige Zeilen bis zum n├ñchsten when/end
            r'[ \t]*if show_continue\s*\n'
            r'.*?\n'
            r'.*?\n'
            r'[ \t]*end\s*\n',
            content, re.MULTILINE
        )
        if old:
            content = content[:old.start()] + MULTISAVES_CMD_LANGUAGE_PATCH + content[old.end():]
            changed = True

    if not changed:
        report("SKIP", "MultiSaves.rb: bereits gepacht oder nicht anwendbar")
        return

    if dry_run:
        report("SKIP", "[DRY-RUN] MultiSaves.rb w├╝rde gepacht")
        return

    backup(path)
    write_text(path, content, enc or 'utf-8')
    report("OK", "MultiSaves.rb gepacht (safeExists? + Sprachpersistenz)")


def patch_999_main(game_dir, dry_run):
    """999_Main.rb: pbApplyLanguagePreference nach Game.set_up_system einf├╝gen."""
    path = find_script(game_dir, "999_Main.rb")
    if not path:
        report("WARN", "999_Main.rb nicht gefunden")
        return

    content, enc = read_text(path)
    if content is None:
        report("ERR", "999_Main.rb konnte nicht gelesen werden")
        return

    if 'pbApplyLanguagePreference' in content:
        report("SKIP", "999_Main.rb: bereits gepacht")
        return

    inject = '  pbApplyLanguagePreference if defined?(pbApplyLanguagePreference)\n'
    # Nach "Game.set_up_system" einf├╝gen
    pattern = re.compile(r'([ \t]*Game\.set_up_system[^\n]*\n)')
    m = pattern.search(content)
    if m:
        new_content = content[:m.end()] + inject + content[m.end():]
    else:
        report("WARN", "999_Main.rb: Game.set_up_system nicht gefunden ÔÇô manuell einf├╝gen")
        return

    if dry_run:
        report("SKIP", "[DRY-RUN] 999_Main.rb w├╝rde gepacht")
        return

    backup(path)
    write_text(path, new_content, enc or 'utf-8')
    report("OK", "999_Main.rb: pbApplyLanguagePreference eingef├╝gt")


def patch_ui_load(game_dir, dry_run):
    """013_UI_Load.rb: Sprachpersistenz im cmd_language-Handler."""
    path = find_script(game_dir, "013_UI_Load.rb")
    if not path:
        report("WARN", "013_UI_Load.rb nicht gefunden")
        return

    content, enc = read_text(path)
    if content is None:
        report("ERR", "013_UI_Load.rb konnte nicht gelesen werden")
        return

    if 'pbSaveLanguagePreference' in content:
        report("SKIP", "013_UI_Load.rb: bereits gepacht")
        return

    # Nach der Zeile "pbChooseLanguage" (oder "pbLoadMessages") im cmd_language-Block einf├╝gen
    pattern = re.compile(
        r'(when cmd_language.*?pbLoadMessages[^\n]*\n)',
        re.DOTALL
    )
    m = pattern.search(content)
    if m:
        inject = ('          pbSaveLanguagePreference($PokemonSystem.language)'
                  ' if defined?(pbSaveLanguagePreference)\n')
        new_content = content[:m.end()] + inject + content[m.end():]
    else:
        report("WARN", "013_UI_Load.rb: cmd_language-Block nicht erkannt ÔÇô ├╝bersprungen")
        return

    if dry_run:
        report("SKIP", "[DRY-RUN] 013_UI_Load.rb w├╝rde gepacht")
        return

    backup(path)
    write_text(path, new_content, enc or 'utf-8')
    report("OK", "013_UI_Load.rb: Sprachpersistenz eingef├╝gt")


def set_language_preference_to_german(game_dir, dry_run):
    """
    Schreibt language_preference.dat mit Wert 1 (= Deutsch, Index in LANGUAGES).
    Das sorgt daf├╝r, dass das Spiel beim n├ñchsten Start sofort Deutsch l├ñdt.
    """
    import struct
    dst = os.path.join(game_dir, "Data", "language_preference.dat")

    # Ruby Marshal.dump(1):  \x04\x08 i \x06
    # Fixnum 1 in Ruby Marshal = 0x69 0x06
    marshal_1 = b'\x04\x08\x69\x06'

    if os.path.exists(dst):
        report("SKIP", "Data/language_preference.dat: existiert bereits")
        return

    if dry_run:
        report("SKIP", "[DRY-RUN] Data/language_preference.dat w├╝rde geschrieben (=Deutsch)")
        return

    with open(dst, 'wb') as f:
        f.write(marshal_1)
    report("OK", "Data/language_preference.dat gesetzt (Deutsch als Standard)")


# ===========================================================================
#  Spielverzeichnis ermitteln
# ===========================================================================

def detect_game_dir(candidate=None):
    """
    Pr├╝ft ob candidate ein g├╝ltiges InfiniteFusion-Verzeichnis ist.
    Gibt den Pfad zur├╝ck oder None.
    """
    if not candidate:
        return None
    candidate = candidate.strip().strip('"').strip("'")
    if not os.path.isdir(candidate):
        return None
    # Mindest-Pr├╝fung: Data/Scripts muss existieren
    if os.path.isdir(os.path.join(candidate, "Data", "Scripts")):
        return candidate
    return None


# ===========================================================================
#  Hauptprogramm
# ===========================================================================

def main():
    # ANSI-Farben auf Windows aktivieren
    if sys.platform == 'win32':
        os.system('')

    parser = argparse.ArgumentParser(
        description="Deutsch-Patch f├╝r Pok├®mon Infinite Fusion")
    parser.add_argument("--game",    default="",
                        help="Pfad zum InfiniteFusion-Spielordner")
    parser.add_argument("--dry-run", action="store_true",
                        help="Zeige was gemacht w├╝rde, ohne Dateien zu ├ñndern")
    args = parser.parse_args()

    print()
    print(bold("=" * 60))
    print(bold("  Pok├®mon Infinite Fusion ÔÇô Deutsch-Patch"))
    print(bold("=" * 60))
    print()

    # ÔöÇÔöÇ Spielverzeichnis ermitteln ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    game_dir = detect_game_dir(args.game)
    if not game_dir:
        # Interaktiv fragen
        print("Wo ist dein InfiniteFusion-Spielordner?")
        print('(z.B. C:\\Games\\InfiniteFusion  oder  D:\\Downloads\\PokemonInfiniteFusion)')
        print()
        while True:
            raw = input("Pfad eingeben: ").strip().strip('"').strip("'")
            game_dir = detect_game_dir(raw)
            if game_dir:
                break
            print(red(f"  Nicht gefunden oder kein g├╝ltiger Spielordner: {raw!r}"))
            print("  (Der Ordner muss 'Data/Scripts' enthalten)")
            print()

    print(f"  Spielordner: {bold(game_dir)}")
    if args.dry_run:
        print(f"  {yellow('[DRY-RUN aktiv ÔÇô keine Dateien werden ge├ñndert]')}")
    print()

    # ÔöÇÔöÇ Patch-Schritte ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    print("Installiere Patch...")
    print()

    # 1. german.dat
    copy_data_file("german.dat",  game_dir, args.dry_run)

    # 2. english.dat (Stub)
    copy_data_file("english.dat", game_dir, args.dry_run)

    # 3. GermanLanguagePatch.rb
    copy_script_file("GermanLanguagePatch.rb", game_dir, args.dry_run)

    # 4. 001_Settings.rb ÔÇô LANGUAGES
    patch_settings(game_dir, args.dry_run)

    # 5. MultiSaves.rb
    patch_multisaves(game_dir, args.dry_run)

    # 6. 999_Main.rb
    patch_999_main(game_dir, args.dry_run)

    # 7. 013_UI_Load.rb
    patch_ui_load(game_dir, args.dry_run)

    # 8. Sprachpr├ñferenz auf Deutsch setzen
    set_language_preference_to_german(game_dir, args.dry_run)

    # ÔöÇÔöÇ Bericht ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    ok   = sum(1 for s, _ in results if s == "OK")
    skip = sum(1 for s, _ in results if s == "SKIP")
    warn = sum(1 for s, _ in results if s == "WARN")
    err  = sum(1 for s, _ in results if s == "ERR")

    print()
    print(bold("=" * 60))
    if err == 0 and warn == 0:
        print(green(bold(f"  FERTIG! {ok} Schritte erfolgreich.")))
    elif err == 0:
        print(yellow(bold(f"  Fertig mit Warnungen: {ok} OK, {warn} Warnungen, {skip} ├╝bersprungen.")))
        print(yellow("  Bitte Warnungen oben pr├╝fen."))
    else:
        print(red(bold(f"  {err} Fehler! Bitte Ausgabe oben pr├╝fen.")))

    if not args.dry_run and err == 0:
        print()
        print("  Das Spiel ist jetzt auf Deutsch eingestellt.")
        print("  Beim n├ñchsten Start einfach spielen ÔÇô keine weiteren Schritte n├Âtig.")
    print(bold("=" * 60))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nAbgebrochen.")
    except Exception:
        print("\nUnerwarteter Fehler:")
        traceback.print_exc()
    finally:
        input("\nDr├╝cke Enter zum Schlie├ƒen ...")
