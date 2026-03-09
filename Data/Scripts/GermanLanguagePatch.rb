#===============================================================================
# Sprachpersistenz-Helfer
#
# SPRACH-ARCHITEKTUR:
#   LANGUAGES[0] = "English"  -> english.dat  (leere Datei, eingebaute EN-Texte)
#   LANGUAGES[1] = "Deutsch"  -> german.dat   (deutsche Karten- und Pokedextexte)
#   LANGUAGES[2] = "Francais" -> french.dat   (franzoesische Uebersetzung)
#
#   Sprachwahl: Titelbildschirm -> "Language" waehlen
#   Gespeichert in: Data/language_preference.dat (unabhaengig vom Spielstand)
#===============================================================================

LANG_PREF_FILE = "Data/language_preference.dat"
LANG_LOG_FILE  = "lang_debug.txt"

# Schreibt in die Diagnosedatei lang_debug.txt im Spielverzeichnis.
def langLog(msg)
  begin
    File.open(LANG_LOG_FILE, "ab") { |f| f.puts("[#{Time.now.strftime('%H:%M:%S')}] #{msg}") }
  rescue
  end
  echoln "[LANG] #{msg}"
end

# Speichert den Sprachindex.
def pbSaveLanguagePreference(lang_idx)
  begin
    File.open(LANG_PREF_FILE, "wb") { |f| Marshal.dump(lang_idx.to_i, f) }
    langLog("Praeferenz gespeichert: idx=#{lang_idx} (#{Settings::LANGUAGES[lang_idx]&.first || '?'})")
  rescue => e
    langLog("FEHLER beim Speichern der Praeferenz: #{e.message}")
  end
end

# Laedt den gespeicherten Sprachindex (Standard: 0 = Englisch).
def pbLoadLanguagePreference
  return 0 unless safeExists?(LANG_PREF_FILE)
  begin
    File.open(LANG_PREF_FILE, "rb") { |f| Marshal.load(f) }.to_i
  rescue
    0
  end
end

# Wendet die gespeicherte Sprachpraeferenz an (und Spielstand-Sprache als Fallback).
def pbApplyLanguagePreference
  return unless Settings::LANGUAGES.length >= 2
  # Praeferenz-Datei hat Vorrang; sonst $PokemonSystem.language als Fallback
  lang_idx = if safeExists?(LANG_PREF_FILE)
               pbLoadLanguagePreference
             elsif defined?($PokemonSystem) && $PokemonSystem
               $PokemonSystem.language.to_i
             else
               0
             end
  lang_idx = lang_idx.clamp(0, Settings::LANGUAGES.length - 1)
  lang_file = "Data/" + Settings::LANGUAGES[lang_idx][1]
  langLog("pbApplyLanguagePreference: idx=#{lang_idx}, file=#{lang_file}, exists=#{safeExists?(lang_file)}")
  if safeExists?(lang_file)
    result = MessageTypes.loadMessageFile(lang_file)
    langLog("  -> loadMessageFile: #{result ? "OK (#{result.compact.length} Typen, ScriptTexts=#{result[24]&.length || 0})" : "FEHLGESCHLAGEN"}")
  end
  $PokemonSystem.language = lang_idx if defined?($PokemonSystem) && $PokemonSystem
end

#===============================================================================
# Patche Messages#loadMessageFile um Fehler zu protokollieren.
#===============================================================================
class Messages
  alias :_lmf_unpatched :loadMessageFile

  def loadMessageFile(filename)
    begin
      pbRgssOpen(filename, "rb") { |f| @messages = Marshal.load(f) }
      if !@messages.is_a?(Array)
        langLog("loadMessageFile(#{filename}): FEHLER - kein Array (#{@messages.class})")
        @messages = nil
        return nil
      end
      sc = @messages[24]
      langLog("loadMessageFile(#{filename}): OK - #{@messages.compact.length} Typen, ScriptTexts=#{sc.respond_to?(:length) ? sc.length : sc.class}")
      return @messages
    rescue => e
      langLog("loadMessageFile(#{filename}): EXCEPTION #{e.class}: #{e.message}")
      # Fallback: File.open direkt (umgeht eventuelle RGSS-Probleme)
      begin
        File.open(filename, "rb") { |f| @messages = Marshal.load(f) }
        if @messages.is_a?(Array)
          langLog("  -> File.open Fallback: OK - #{@messages.compact.length} Typen")
          return @messages
        end
      rescue => e2
        langLog("  -> File.open Fallback: FEHLER #{e2.class}: #{e2.message}")
      end
      @messages = nil
      return nil
    end
  end
end

#===============================================================================
# Debug-Menu: Sprachwerkzeuge
#===============================================================================
DebugMenuCommands.register("languagemenu", {
  "parent"      => "main",
  "name"        => _INTL("Language tools..."),
  "description" => _INTL("Language patch helpers and text extraction."),
  "always_show" => true
})

DebugMenuCommands.register("showlangpref", {
  "parent"      => "languagemenu",
  "name"        => _INTL("Show Current Language"),
  "description" => _INTL("Shows which language is currently saved."),
  "always_show" => true,
  "effect"      => proc {
    lang_idx = pbLoadLanguagePreference
    name = (lang_idx < Settings::LANGUAGES.length) ? Settings::LANGUAGES[lang_idx][0] : "?"
    pbMessage("Gespeicherte Sprache: #{name} (Index #{lang_idx})")
  }
})

DebugMenuCommands.register("updategermandat", {
  "parent"      => "languagemenu",
  "name"        => _INTL("Update german.dat (save current messages)"),
  "description" => _INTL("Saves currently loaded messages to german.dat."),
  "always_show" => true,
  "effect"      => proc {
    msgwindow = pbCreateMessageWindow
    if pbConfirmMessage("Nachrichten als german.dat speichern?")
      pbMessageDisplay(msgwindow, "Bitte warten...\\wtnp[0]")
      begin
        MessageTypes.saveMessages("Data/german.dat")
        pbMessageDisplay(msgwindow, "Erfolgreich!\\1")
      rescue => e
        pbMessageDisplay(msgwindow, "Fehler: #{e.message}")
      end
    end
    pbDisposeMessageWindow(msgwindow)
  }
})

#===============================================================================
# Baut german.dat neu auf, indem strings aus der byte-gepatchten german.dat
# extrahiert und über die Messages-API in eine neue valide Datei geschrieben
# werden. Benoetigt: messages.dat (EN, valide) und german.dat (DE, byte-gepatcht).
#
# Ablauf:
#  1. Lade messages.dat (valide EN) via Marshal
#  2. Lese german.dat roh als Byte-Array
#  3. Fuer jeden String in messages-Array: suche denselben UTF-8-String in
#     german.dat an der erwarteten Position (mit Toleranz). Falls anders:
#     der DE-String ist an dieser Stelle.
#  4. Ersetze EN-String durch DE-String im gerade geladenen Array
#  5. Speichere als neue german.dat via Marshal.dump (valides Format!)
#===============================================================================
def pbRebuildGermanDat(msgwindow)
  # messange.dat = originale EN-Basisdatei (valides Marshal)
  # german.dat   = byte-gepatchte DE-Datei (kaputtes Marshal, aber DE-Strings drin)
  en_file  = "Data/messange.dat"
  de_file  = "Data/german.dat"
  out_file = "Data/german.dat"

  unless safeExists?(en_file)
    pbMessageDisplay(msgwindow, "FEHLER: messages.dat nicht gefunden!\\1")
    return
  end
  unless safeExists?(de_file)
    pbMessageDisplay(msgwindow, "FEHLER: german.dat nicht gefunden!\\1")
    return
  end

  # Lade englische Nachrichten (valide Marshal-Datei)
  pbMessageDisplay(msgwindow, "Lade messages.dat (EN)...\\wtnp[0]")
  en_messages = nil
  begin
    File.open(en_file, "rb") { |f| en_messages = Marshal.load(f) }
  rescue => e
    pbMessageDisplay(msgwindow, "FEHLER beim Laden von messages.dat:\\n#{e.message}\\1")
    return
  end
  unless en_messages.is_a?(Array)
    pbMessageDisplay(msgwindow, "FEHLER: messages.dat kein gueltiges Array!\\1")
    return
  end

  # Lese german.dat roh (byte-gepatcht, kein Marshal.load moeglich)
  pbMessageDisplay(msgwindow, "Lese german.dat (roh)...\\wtnp[0]")
  de_raw = nil
  begin
    File.open(de_file, "rb") { |f| de_raw = f.read }
  rescue => e
    pbMessageDisplay(msgwindow, "FEHLER beim Lesen von german.dat:\\n#{e.message}\\1")
    return
  end

  # Extrahiere alle UTF-8-Strings aus der byte-gepatchten Datei
  # Ruby Marshal String: 0x22 <ruby-int-len> <bytes>  ODER
  #                      0x49 0x22 <ruby-int-len> <bytes> (IVAR = mit Encoding)
  pbMessageDisplay(msgwindow, "Extrahiere DE-Strings...\\wtnp[0]")
  de_strings_by_pos = {}
  pos = 2  # Skip \x04\x08 header
  while pos < de_raw.length - 3
    Graphics.update if pos % 100000 == 0
    ch = de_raw.getbyte(pos)
    has_ivar = false
    if ch == 0x49 && pos+1 < de_raw.length && de_raw.getbyte(pos+1) == 0x22
      has_ivar = true
      str_pos = pos + 2
    elsif ch == 0x22
      str_pos = pos + 1
    else
      pos += 1
      next
    end

    # Lese Ruby-Integer fuer String-Laenge
    b = de_raw.getbyte(str_pos)
    if b == 0
      length = 0; text_start = str_pos + 1
    elsif b > 4 && b < 128
      length = b - 5; text_start = str_pos + 1
    elsif b == 1
      length = de_raw.getbyte(str_pos + 1); text_start = str_pos + 2
    elsif b == 2
      length = de_raw.getbyte(str_pos+1) | (de_raw.getbyte(str_pos+2) << 8); text_start = str_pos + 3
    else
      pos += 1; next
    end

    if length > 0 && length < 50000 && text_start + length <= de_raw.length
      raw_str = de_raw[text_start, length]
      begin
        text = raw_str.force_encoding("UTF-8")
        if text.valid_encoding? && text.length > 0
          de_strings_by_pos[pos] = text
        end
      rescue
      end
      pos = text_start + length
      next
    end
    pos += 1
  end

  langLog("Extrahiert: #{de_strings_by_pos.length} Strings aus german.dat")
  pbMessageDisplay(msgwindow, "#{de_strings_by_pos.length} DE-Strings extrahiert.\\wtnp[0]")

  # Gleicher Durchlauf durch EN-Datei um Positionen zu matchen
  pbMessageDisplay(msgwindow, "Matche EN mit DE...\\wtnp[0]")
  en_raw = nil
  File.open(en_file, "rb") { |f| en_raw = f.read }

  # Baue eine geordnete Liste von EN-String-Positionen
  en_string_seq = []
  pos = 2
  while pos < en_raw.length - 3
    ch = en_raw.getbyte(pos)
    if ch == 0x49 && pos+1 < en_raw.length && en_raw.getbyte(pos+1) == 0x22
      str_pos = pos + 2
    elsif ch == 0x22
      str_pos = pos + 1
    else
      pos += 1; next
    end

    b = en_raw.getbyte(str_pos)
    if b == 0
      length = 0; text_start = str_pos + 1
    elsif b > 4 && b < 128
      length = b - 5; text_start = str_pos + 1
    elsif b == 1
      length = en_raw.getbyte(str_pos + 1); text_start = str_pos + 2
    elsif b == 2
      length = en_raw.getbyte(str_pos+1) | (en_raw.getbyte(str_pos+2) << 8); text_start = str_pos + 3
    else
      pos += 1; next
    end

    if length > 0 && length < 50000 && text_start + length <= en_raw.length
      raw_str = en_raw[text_start, length]
      begin
        text = raw_str.force_encoding("UTF-8")
        if text.valid_encoding?
          en_string_seq << [pos, text]
          pos = text_start + length
          next
        end
      rescue
      end
    end
    pos += 1
  end

  langLog("EN-Strings: #{en_string_seq.length}")

  # Baue DE-String-Sequenz in gleicher Reihenfolge
  de_string_seq = de_strings_by_pos.sort_by { |p, _| p }.map { |_, t| t }

  # Erstelle EN→DE-Mapping über Sequenz-Index
  # Beide Dateien haben dieselbe Anzahl Strings in derselben Reihenfolge,
  # nur mit unterschiedlichen Inhalten (EN vs DE). Matche per Index.
  en_to_de = {}
  [en_string_seq.length, de_string_seq.length].min.times do |i|
    en_text = en_string_seq[i][1]
    de_text = de_string_seq[i]
    en_to_de[en_text] = de_text if de_text && de_text != en_text && de_text.length > 0
  end

  langLog("EN→DE-Mappings: #{en_to_de.length}")
  pbMessageDisplay(msgwindow, "#{en_to_de.length} Uebersetzungen gefunden.\\wtnp[0]")

  # Wende Mappings auf EN-Messages-Array an
  replaced = 0
  de_messages = en_messages.map.with_index do |section, type_idx|
    next section if section.nil?
    if section.is_a?(Array)
      section.map do |entry|
        next entry unless entry.is_a?(String)
        de = en_to_de[entry]
        if de
          replaced += 1
          de
        else
          entry
        end
      end
    elsif section.is_a?(OrderedHash)
      new_hash = OrderedHash.new
      section.keys.each do |k|
        v = section[k]
        de_k = en_to_de[k] || k
        de_v = en_to_de[v] || v
        replaced += 1 if de_v != v
        new_hash[de_k] = de_v
      end
      new_hash
    else
      section
    end
  end

  langLog("Ersetzt: #{replaced} Strings")
  pbMessageDisplay(msgwindow, "#{replaced} Strings ersetzt. Speichere...\\wtnp[0]")

  # Speichere als valide Marshal-Datei
  begin
    File.open(out_file, "wb") { |f| Marshal.dump(de_messages, f) }
    size_kb = File.size(out_file) / 1024
    langLog("german.dat gespeichert: #{size_kb} KB")
    pbMessageDisplay(msgwindow, "german.dat gespeichert (#{size_kb} KB)!\\n#{replaced} DE-Strings eingebaut.\\1")
  rescue => e
    langLog("FEHLER beim Speichern: #{e.message}")
    pbMessageDisplay(msgwindow, "FEHLER beim Speichern:\\n#{e.message}\\1")
  end
end

DebugMenuCommands.register("rebuildgermandat", {
  "parent"      => "languagemenu",
  "name"        => _INTL("Rebuild german.dat from byte-patched file"),
  "description" => _INTL("Extracts DE strings from byte-patched german.dat and saves as valid Marshal."),
  "always_show" => true,
  "effect"      => proc {
    msgwindow = pbCreateMessageWindow
    if pbConfirmMessageSerious("Rebuild german.dat?\\nBraucht messages.dat (EN) + german.dat (byte-gepatcht).\\nDauert etwas laenger.")
      pbRebuildGermanDat(msgwindow)
    end
    pbDisposeMessageWindow(msgwindow)
  }
})

DebugMenuCommands.register("extracttext", {
  "parent"      => "languagemenu",
  "name"        => _INTL("Extract All Text (-> intl.txt)"),
  "description" => _INTL("Extract all game texts to intl.txt for translation."),
  "always_show" => true,
  "effect"      => proc {
    msgwindow = pbCreateMessageWindow
    if safeExists?("intl.txt") && !pbConfirmMessageSerious("intl.txt exists. Overwrite?")
      pbDisposeMessageWindow(msgwindow)
      next
    end
    pbMessageDisplay(msgwindow, "Please wait...\\wtnp[0]")
    MessageTypes.extract("intl.txt")
    pbMessageDisplay(msgwindow, "Extracted to intl.txt.\\1")
    pbDisposeMessageWindow(msgwindow)
  }
})

DebugMenuCommands.register("compiletext", {
  "parent"      => "languagemenu",
  "name"        => _INTL("Compile Text (intl.txt -> intl.dat)"),
  "description" => _INTL("Compile translated intl.txt to intl.dat."),
  "always_show" => true,
  "effect"      => proc {
    msgwindow = pbCreateMessageWindow
    pbMessageDisplay(msgwindow, "Please wait...\\wtnp[0]")
    begin
      pbCompileText
      pbMessageDisplay(msgwindow, "Compiled to intl.dat.\\1")
    rescue RuntimeError
      pbMessageDisplay(msgwindow, "Failed: #{$!.message}")
    end
    pbDisposeMessageWindow(msgwindow)
  }
})

DebugMenuCommands.register("langstats", {
  "parent"      => "languagemenu",
  "name"        => _INTL("Show Message Stats"),
  "description" => _INTL("Show loaded message counts per type."),
  "always_show" => true,
  "effect"      => proc {
    lang_idx = pbLoadLanguagePreference
    lang_name = (lang_idx < Settings::LANGUAGES.length) ? Settings::LANGUAGES[lang_idx][0] : "?"
    types = { 0 => "MapTexts", 1 => "Species", 5 => "Moves", 7 => "Items",
              10 => "Abilities", 12 => "Types", 24 => "ScriptTexts", 25 => "RibbonNames" }
    lines = ["Sprache: #{lang_name} (#{lang_idx})"]
    types.each { |idx, name| lines.push("#{name}: #{MessageTypes.getCount(idx)}") }
    pbMessage(lines.join("\n"))
  }
})
