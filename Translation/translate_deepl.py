#!/usr/bin/env python3
"""
translate_deepl.py  –  Übersetzt + korrigiert messange.dat → german.dat
=========================================================================

MODI:
  Mit API-Key (empfohlen – 500k Zeichen/Monat kostenlos):
    python translate_deepl.py --key DEIN_KEY
    Kostenlosen Key: https://www.deepl.com/de/pro#developer

  Ohne API-Key (inoffizieller DeepL-Endpunkt, kein Key nötig):
    python translate_deepl.py --no-key

  german.dat aus bestehender CSV bauen (kein DeepL):
    python translate_deepl.py --build

  Nur PokéAPI-Korrekturen auf vorhandene CSV anwenden:
    python translate_deepl.py --fix-only

AUTOMATISCHE FUNKTIONEN:
  ✓ Erkennt neue Dialoge in messange.dat – übersetzt nur fehlende Einträge
  ✓ Lädt Pokémon-Namen/Attacken/Items/Fähigkeiten/Orte von PokéAPI (GitHub)
  ✓ Korrigiert DeepL-Fehler bei offiziellen Spielbegriffen automatisch
  ✓ Repariert falsch kodierte Umlaute automatisch (ä/ö/ü/ß)
  ✓ Live-Fortschrittsanzeige mit Balken

DATEIEN (alle im gleichen Ordner wie dieses Script):
  messange.dat          Quelldatei (DE-Patch Basis)
  translations.csv      Zwischendatei (in Excel bearbeitbar)
  german.dat            Ausgabe (fertiger DE-Patch)
  pokeapi_cache.json    Cache: Attacken/Items/Fähigkeiten/Typen/Pokémon
  location_cache.json   Cache: Ortsnamen
  translation_cache.json  Cache: DeepL-Übersetzungen
"""

import os, sys, json, struct, argparse, time, traceback, io, csv, re, shutil
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from random import randint, uniform

# ─── Windows: UTF-8 Konsolen-Output erzwingen ─────────────────────────────────
if sys.platform == "win32":
    import ctypes
    try:
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ─── Umlaut-Reparatur-Tabelle (Mojibake latin-1 → korrekt UTF-8) ──────────────
UMLAUT_FIXES = {
    # Mojibake: latin-1 Zeichen falsch als UTF-8 gelesen (häufigster Fall)
    "Ã¤": "ä", "Ã„": "Ä",
    "Ã¶": "ö", "Ã–": "Ö",
    "Ã¼": "ü", "Ãœ": "Ü",
    "ÃŸ": "ß",
    # Anführungszeichen-Mojibake
    "\u00e2\u0080\u009e": "\u201e",   # „  (dt. öffnendes Anführungszeichen)
    "\u00e2\u0080\u009c": "\u201c",   # "  (engl. öffnendes Anführungszeichen)
    "\u00e2\u0080\u009d": "\u201d",   # "  (schließendes Anführungszeichen)
    "\u00e2\u0080\u0098": "\u2018",   # '
    "\u00e2\u0080\u0099": "\u2019",   # '
    "\u00e2\u0080\u0093": "\u2013",   # –  (Gedankenstrich)
    "\u00e2\u0080\u0094": "\u2014",   # —  (langer Gedankenstrich)
    "\u00e2\u0080\u00a6": "\u2026",   # …  (Auslassungspunkte)
    # Windows-1252 Steuerzeichen-Reste (als literal char im String)
    "\x84": "\u201e", "\x93": "\u201c", "\x94": "\u201d",
    "\x96": "\u2013", "\x97": "\u2014",
    "\x85": "\u2026",
    # latin-1 Direktzeichen (byte direkt im String)
    "\xe4": "ä", "\xc4": "Ä",
    "\xf6": "ö", "\xd6": "Ö",
    "\xfc": "ü", "\xdc": "Ü",
    "\xdf": "ß",
}

_UMLAUT_PAT = re.compile("|".join(re.escape(k) for k in sorted(UMLAUT_FIXES, key=len, reverse=True)))

def fix_umlauts(text: str) -> str:
    """Repariert Mojibake-Umlaute und Windows-Sonderzeichen in einem String."""
    return _UMLAUT_PAT.sub(lambda m: UMLAUT_FIXES[m.group(0)], text)


# ─── Fortschrittsanzeige ───────────────────────────────────────────────────────

_SPINNER_CHARS = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_spinner_idx   = 0
_last_len      = 0

def progress(msg: str = "", current: int = 0, total: int = 0, done: bool = False):
    """
    Schreibt eine animierte Fortschrittszeile in die Konsole (überschreibt sich selbst).
    done=True: schreibt einen abschließenden Zeilenumbruch.
    """
    global _spinner_idx, _last_len
    if done:
        sys.stdout.write("\r" + " " * _last_len + "\r")
        sys.stdout.flush()
        _last_len = 0
        return

    spin = _SPINNER_CHARS[_spinner_idx % len(_SPINNER_CHARS)]
    _spinner_idx += 1

    if total > 0:
        pct  = current / total
        filled = int(pct * 25)
        bar  = "█" * filled + "░" * (25 - filled)
        line = f"\r  {spin} [{bar}] {current:,}/{total:,}  {msg}"
    else:
        line = f"\r  {spin}  {msg}"

    sys.stdout.write(line)
    sys.stdout.flush()
    _last_len = len(line)

# ─── Konfiguration ─────────────────────────────────────────────────────────────
HARDCODED_API_KEY = ""   # Optional: API-Key direkt hier eintragen
BASE = os.path.dirname(os.path.abspath(__file__))

POKEAPI_BASE = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/"
EN_LANG_ID   = "9"
DE_LANG_ID   = "6"

# ─── Offizielle Pokémon-Ortsnamen EN → DE ──────────────────────────────────────
# Hat Vorrang vor PokéAPI-Daten (manuelle Korrekturen).
CITY_MAPPING = {
    # Kanto
    "Pallet Town":      "Alabastia",
    "Viridian City":    "Vertania City",
    "Pewter City":      "Marmoria City",
    "Cerulean City":    "Azuria City",
    "Vermilion City":   "Zinnoberina City",
    "Lavender Town":    "Lavendeldorf",
    "Celadon City":     "Prismania City",
    "Fuchsia City":     "Fucsia City",
    "Saffron City":     "Saffronia City",
    "Cinnabar Island":  "Vulcania",
    "Viridian Forest":  "Vertania-Wald",
    "Mt. Moon":         "Mondberg",
    "Victory Road":     "Triumphpfad",
    "Indigo Plateau":   "Indigo-Plateau",
    "Rock Tunnel":      "Felsentunnel",
    "Diglett's Cave":   "Digdas Höhle",
    "Pokemon Tower":    "Pokémon-Turm",
    "Safari Zone":      "Safarizone",
    "Seafoam Islands":  "Meeresschaum-Inseln",
    "Power Plant":      "Kraftwerk",
    "Cerulean Cave":    "Azuria-Höhle",
    "Silph Co.":        "Silph AG",
    "S.S. Anne":        "S.S. Anne",
    # Johto
    "New Bark Town":    "Neue-Rinde-Stadt",
    "Cherrygrove City": "Kirschblütenstadt",
    "Violet City":      "Veilchengarten",
    "Azalea Town":      "Mimosaikon",
    "Goldenrod City":   "Goldenrod City",
    "Ecruteak City":    "Weinberg City",
    "Olivine City":     "Malvenfrisch City",
    "Cianwood City":    "Cianopolis",
    "Mahogany Town":    "Mahagoni-Stadt",
    "Blackthorn City":  "Pflaumenbach City",
    "National Park":    "Nationalpark",
    "Ice Path":         "Eispfad",
    "Mt. Mortar":       "Mörserberg",
    "Whirl Islands":    "Strudelinseln",
    "Dragon's Den":     "Drachenhöhle",
    # Hoenn
    "Littleroot Town":  "Wurzelheim",
    "Oldale Town":      "Schleiheim",
    "Petalburg City":   "Blütenburg City",
    "Rustboro City":    "Granipolis",
    "Dewford Town":     "Muschelküste",
    "Slateport City":   "Blaugraum City",
    "Mauville City":    "Mauvielo City",
    "Verdanturf Town":  "Frischwiese",
    "Fallarbor Town":   "Aschfeld",
    "Lavaridge Town":   "Lavasand City",
    "Fortree City":     "Baumhain City",
    "Lilycove City":    "Seerosenküste City",
    "Mossdeep City":    "Moosstadt",
    "Sootopolis City":  "Schlammbad City",
    "Ever Grande City": "Ever Grande City",
    "Meteor Falls":     "Meteorfälle",
    "Mt. Chimney":      "Vulkaninsel",
    "Sky Pillar":       "Himmelssäule",
    "Shoal Cave":       "Flachseehöhle",
    "Seafloor Cavern":  "Meeresgrundkaverne",
    "Cave of Origin":   "Urhöhle",
    "Abandoned Ship":   "Geisterschiff",
    # Sinnoh
    "Twinleaf Town":    "Zweiblattdorf",
    "Sandgem Town":     "Sandgemstadt",
    "Jubilife City":    "Frohfeldia City",
    "Oreburgh City":    "Kohlberg City",
    "Floaroma Town":    "Blütenbach",
    "Eterna City":      "Evigna City",
    "Hearthome City":   "Herzhofen City",
    "Solaceon Town":    "Ruhefeld",
    "Veilstone City":   "Kieselstein City",
    "Pastoria City":    "Sumpfartica City",
    "Celestic Town":    "Alte-Zeit-Stadt",
    "Canalave City":    "Kanalava City",
    "Snowpoint City":   "Schneebaum City",
    "Sunyshore City":   "Strahlstein City",
    "Mt. Coronet":      "Koroneta",
    "Great Marsh":      "Großer Sumpf",
    "Iron Island":      "Eiseninsel",
    "Lake Verity":      "See der Wahrhaftigkeit",
    "Lake Valor":       "See der Entschlossenheit",
    "Lake Acuity":      "See der Klugheit",
    "Spear Pillar":     "Säulenspitze",
    "Distortion World": "Verzerrte Welt",
    "Battle Zone":      "Kampfzone",
    "Fight Area":       "Kampfstätte",
    "Survival Area":    "Überlebensstätte",
    "Resort Area":      "Urlaubsstätte",
    # Unova
    "Nuvema Town":      "Flachsheim",
    "Accumula Town":    "Akkumula-Stadt",
    "Striaton City":    "Dreizack City",
    "Nacrene City":     "Perlweißa City",
    "Castelia City":    "Castellia City",
    "Nimbasa City":     "Nimbasa City",
    "Driftveil City":   "Wogenburg City",
    "Mistralton City":  "Windfels City",
    "Icirrus City":     "Eisunos City",
    "Opelucid City":    "Quakerflint City",
    "Lacunosa Town":    "Lakunosa-Stadt",
    "Undella Town":     "Undella-Stadt",
    "Black City":       "Schwarze Stadt",
    "White Forest":     "Weißer Wald",
    "Pokemon League":   "Pokémon-Liga",
}

# ─── DeepL-Literalübersetzungen → Offizielle DE-Namen ─────────────────────────
# DeepL übersetzt Stadtnamen manchmal wörtlich statt mit dem offiziellen Namen.
# Diese Map enthält die bekannten Literalvarianten als zusätzliche Quellterme.
# Sie wird in build_fix_mapping() in CITY_MAPPING zusammengeführt.
CITY_LITERAL_MAP = {
    # Kanto – DeepL-Literalvarianten -> offizieller Name
    "Zinnstadt":         "Marmoria City",   # Pewter City
    "Alabastia":         "Alabastia",        # Pallet Town (schon korrekt, zur Sicherheit)
    "Viridianischer Wald": "Vertania-Wald",  # Viridian Forest
    "Viridianisch":      "Vertania",         # Prefix für Komposita (Viridianische Stadt etc.)
    # Cerulean – DeepL lässt es manchmal auf Englisch
    "Cerulean":          "Azuria",           # Prefix-Fix für "Cerulean Division" etc.
    # Weitere bekannte Literalvarianten
    "Zinnoberinsel":     "Vulcania",         # Cinnabar Island
}


# ===========================================================================
#  Ruby Marshal – Integer lesen / schreiben
# ===========================================================================

def rb_int_r(buf, pos):
    b = buf[pos]; p = pos + 1
    c = b if b < 128 else b - 256
    if c == 0:  return 0, p
    if c > 4:   return c - 5, p
    if 1 <= c <= 4:
        n = 0
        for i in range(c): n |= buf[p + i] << (8 * i)
        return n, p + c
    if -4 <= c <= -1:
        nc = -c; n = -1
        for i in range(nc):
            n &= ~(0xFF << (8 * i))
            n |= buf[p + i] << (8 * i)
        return n, p + nc
    return c + 5, p


def rb_int_w(n):
    if n == 0:             return b'\x00'
    if 0 < n < 123:        return bytes([n + 5])
    if 0 < n < 256:        return bytes([1, n])
    if 0 < n < 65536:      return bytes([2]) + struct.pack('<H', n)
    if 0 < n < (1 << 24):  return bytes([3]) + struct.pack('<I', n)[:3]
    if 0 < n < (1 << 31):  return bytes([4]) + struct.pack('<I', n)
    if -123 <= n < 0:      return bytes([(n - 5) & 0xFF])
    if -256 <= n < 0:      return bytes([255, n + 256])
    if -(1 << 15) < n < 0: return bytes([254]) + struct.pack('<H', n + (1 << 16))
    if -(1 << 23) < n < 0: return bytes([253]) + struct.pack('<I', n + (1 << 24))[:3]
    if -(1 << 31) < n < 0: return bytes([252]) + struct.pack('<i', n)
    raise ValueError(f"Integer zu groß für Marshal: {n}")


# ===========================================================================
#  Hilfsklassen für Ruby-Typen
# ===========================================================================

class RbSym(str):
    """Ruby Symbol – eigene Tabelle, kein obj-Slot."""
    pass

class RbOrderedHash:
    def __init__(self, keys, values):
        self.keys = list(keys); self.values = list(values)

class RbUserDef:
    def __init__(self, cls, data):
        self.cls = cls; self.data = data

class RbObject:
    def __init__(self, cls, ivars):
        self.cls = cls; self.ivars = ivars


# ===========================================================================
#  Ruby Marshal Reader
#  Objekttabelle-Regeln:
#    String/Array/Hash/UserDef/Object/Float/Bignum → registrieren
#    IVAR (0x49)  → KEIN eigener Slot (innerer Typ registriert sich selbst)
#    Array        → Slot VOR den Elementen (Rückref.-sicher)
#    Fixnum/nil/true/false/Symbol → kein Slot
# ===========================================================================

class RbReader:
    def __init__(self, buf):
        self.buf = bytes(buf); self.pos = 0
        self.syms = []; self.objs = []

    def _b(self):
        v = self.buf[self.pos]; self.pos += 1; return v

    def _i(self):
        v, self.pos = rb_int_r(self.buf, self.pos); return v

    def _raw(self, n):
        r = self.buf[self.pos:self.pos + n]; self.pos += n; return r

    def _new_sym(self):
        s = RbSym(self._raw(self._i()).decode('utf-8', 'replace'))
        self.syms.append(s); return s

    def load(self):
        v, m = self._b(), self._b()
        if (v, m) != (4, 8):
            raise ValueError(f"Kein Ruby-Marshal-Header ({v},{m})")
        return self._v()

    def _v(self):
        t = self._b()

        if t == 0x30: return None
        if t == 0x54: return True
        if t == 0x46: return False
        if t == 0x69: return self._i()           # Fixnum – kein Slot

        if t == 0x3A: return self._new_sym()
        if t == 0x3B: return self.syms[self._i()]
        if t == 0x40: return self.objs[self._i()]

        if t == 0x22:                             # String – Slot!
            s = self._raw(self._i()).decode('utf-8', 'replace')
            self.objs.append(s); return s

        if t == 0x49:                             # IVAR – KEIN eigener Slot
            inner = self._v()
            n = self._i()
            for _ in range(n): self._v(); self._v()
            return inner

        if t == 0x5B:                             # Array – Slot VOR Elementen
            n = self._i(); arr = []; self.objs.append(arr)
            for _ in range(n): arr.append(self._v())
            return arr

        if t == 0x7B:                             # Hash
            n = self._i(); h = {}; self.objs.append(h)
            for _ in range(n): k = self._v(); v = self._v(); h[k] = v
            return h

        if t == 0x7D:                             # Hash + default
            n = self._i(); h = {}; self.objs.append(h)
            for _ in range(n): k = self._v(); v = self._v(); h[k] = v
            self._v(); return h

        if t == 0x75:                             # UserDefined (OrderedHash…)
            cls = self._v()
            n = self._i(); data = self._raw(n)
            if str(cls) == 'OrderedHash':
                inner = RbReader(data).load()
                oh = RbOrderedHash(inner[0], inner[1])
                self.objs.append(oh); return oh
            ud = RbUserDef(cls, data); self.objs.append(ud); return ud

        if t == 0x6F:                             # Object
            cls = self._v(); obj = RbObject(cls, {}); self.objs.append(obj)
            n = self._i()
            for _ in range(n): k = self._v(); v = self._v(); obj.ivars[k] = v
            return obj

        if t == 0x66:                             # Float
            f = float(self._raw(self._i()).decode('ascii', 'replace'))
            self.objs.append(f); return f

        if t == 0x6C:                             # Bignum
            sign = self._b(); n = self._i(); d = self._raw(n * 2)
            v = int.from_bytes(d, 'little')
            big = v if sign == ord('+') else -v
            self.objs.append(big); return big

        if t == 0x2F:                             # Regexp
            src = self._raw(self._i()); opts = self._b()
            r = (src, opts); self.objs.append(r); return r

        if t == 0x55:                             # UserMarshal
            cls = self._v(); inner = self._v()
            um = (cls, inner); self.objs.append(um); return um

        if t in (0x43, 0x65, 0x4D): return self._v()

        raise ValueError(f"Unbekannter Marshal-Typ 0x{t:02X} @ {self.pos - 1}")


# ===========================================================================
#  Ruby Marshal Writer  (BytesIO – schnell auch bei 30 MB)
# ===========================================================================

class RbWriter:
    def __init__(self):
        self.syms = {}; self._buf = io.BytesIO()

    def dump(self, obj):
        self._buf = io.BytesIO()
        self._buf.write(b'\x04\x08')
        self._w(obj)
        return self._buf.getvalue()

    def _put(self, data): self._buf.write(data)

    def _sym(self, name):
        if name in self.syms:
            self._put(b'\x3B'); self._put(rb_int_w(self.syms[name])); return
        self.syms[name] = len(self.syms)
        enc = name.encode('utf-8')
        self._put(b'\x3A'); self._put(rb_int_w(len(enc))); self._put(enc)

    def _w(self, obj):
        if obj is None:  self._put(b'\x30'); return
        if obj is True:  self._put(b'\x54'); return
        if obj is False: self._put(b'\x46'); return
        if isinstance(obj, RbSym): self._sym(str(obj)); return
        if isinstance(obj, bool): self._put(b'\x54' if obj else b'\x46'); return
        if isinstance(obj, int):
            self._put(b'\x69'); self._put(rb_int_w(obj)); return
        if isinstance(obj, float):
            s = repr(obj).encode('ascii')
            self._put(b'\x66'); self._put(rb_int_w(len(s))); self._put(s); return
        if isinstance(obj, str):
            enc = obj.encode('utf-8')
            self._put(b'\x49\x22'); self._put(rb_int_w(len(enc))); self._put(enc)
            self._put(rb_int_w(1)); self._sym('E'); self._put(b'\x54'); return
        if isinstance(obj, bytes):
            self._put(b'\x22'); self._put(rb_int_w(len(obj))); self._put(obj); return
        if isinstance(obj, list):
            self._put(b'\x5B'); self._put(rb_int_w(len(obj)))
            for x in obj: self._w(x)
            return
        if isinstance(obj, dict):
            pairs = list(obj.items())
            self._put(b'\x7B'); self._put(rb_int_w(len(pairs)))
            for k, v in pairs: self._w(k); self._w(v)
            return
        if isinstance(obj, RbOrderedHash):
            inner = RbWriter().dump([obj.keys, obj.values])
            self._put(b'\x75'); self._sym('OrderedHash')
            self._put(rb_int_w(len(inner))); self._put(inner); return
        if isinstance(obj, RbUserDef):
            self._put(b'\x75'); self._sym(str(obj.cls))
            self._put(rb_int_w(len(obj.data))); self._put(obj.data); return
        if isinstance(obj, RbObject):
            self._put(b'\x6F'); self._sym(str(obj.cls))
            self._put(rb_int_w(len(obj.ivars)))
            for k, v in obj.ivars.items(): self._sym(str(k)); self._w(v)
            return
        if isinstance(obj, tuple) and len(obj) == 2 and isinstance(obj[0], bytes):
            src, opts = obj
            self._put(b'\x2F'); self._put(rb_int_w(len(src)))
            self._put(src); self._put(bytes([opts])); return
        raise TypeError(f"Nicht serialisierbar: {type(obj).__name__!r} = {repr(obj)[:80]}")


# ===========================================================================
#  String-Sammlung + Übersetzung anwenden
# ===========================================================================

def collect_strings(obj):
    """Alle übersetzbaren Strings iterativ sammeln (kein Rekursions-Problem)."""
    result = []; stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, str) and not isinstance(cur, RbSym):
            result.append(cur)
        elif isinstance(cur, list):
            stack.extend(reversed(cur))
        elif isinstance(cur, RbOrderedHash):
            stack.extend(reversed(cur.values))
        elif isinstance(cur, RbObject):
            stack.extend(cur.ivars.values())
    return result


def apply_translations(obj, mapping, counter):
    """Strings rekursiv ersetzen (mit erhöhtem Rekursionslimit)."""
    sys.setrecursionlimit(50000)
    def _t(o):
        if isinstance(o, str) and not isinstance(o, RbSym):
            tr = mapping.get(o)
            if tr and tr != o: counter[0] += 1; return tr
            return o
        if isinstance(o, list): return [_t(x) for x in o]
        if isinstance(o, RbOrderedHash):
            return RbOrderedHash(o.keys, [_t(v) for v in o.values])
        if isinstance(o, RbObject):
            return RbObject(o.cls, {k: _t(v) for k, v in o.ivars.items()})
        return o
    return _t(obj)


# ===========================================================================
#  CSV-Zwischendatei
# ===========================================================================

def save_csv(rows, csv_path, log_fn):
    """Speichert Liste von [EN, DE]-Zeilen als CSV (UTF-8)."""
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        for row in rows:
            w.writerow(row)
    log_fn(f"  CSV gespeichert: {csv_path}  ({len(rows):,} Zeilen)")


def load_csv(csv_path, log_fn):
    """Liest translations.csv → gibt (dict {EN: DE}, Zeilenliste) zurück."""
    if not os.path.exists(csv_path):
        return None, []
    rows = []; mapping = {}
    with open(csv_path, 'r', encoding='utf-8', newline='') as f:
        for row in csv.reader(f):
            if len(row) >= 2:
                fixed_row = list(row)
                fixed_row[1] = fix_umlauts(fixed_row[1])  # Umlaut-Reparatur
                rows.append(fixed_row)
                if row[0]:
                    mapping[row[0]] = fixed_row[1]
    log_fn(f"  Bestehende CSV geladen: {len(mapping):,} Einträge")
    return mapping, rows


# ===========================================================================
#  DeepL – offiziell (mit API-Key, Free oder Pro)
# ===========================================================================

class DeepLOfficial:
    """Offizielle DeepL API über das 'deepl' Python-Paket.
    Free-Keys enden auf ':fx'  → api-free.deepl.com (500k Zeichen/Monat)
    Pro-Keys:  regulärer Key   → api.deepl.com"""

    def __init__(self, api_key):
        try:
            import deepl as _deepl
        except ImportError:
            print("\nFEHLER: deepl-Paket nicht installiert. Bitte ausführen:\n  pip install deepl")
            sys.exit(1)
        self._tr = _deepl.Translator(api_key)

    def usage(self):
        u = self._tr.get_usage()
        if u.character.limit:
            pct = u.character.count / u.character.limit * 100
            return f"{u.character.count:,}/{u.character.limit:,} Zeichen ({pct:.1f}%)"
        return f"{u.character.count:,} Zeichen genutzt"

    def translate_batch(self, texts, target_lang="DE", source_lang="EN"):
        indices = [i for i, t in enumerate(texts) if t.strip()]
        results = list(texts)
        if not indices:
            return results
        translated = self._tr.translate_text(
            [texts[i] for i in indices],
            source_lang=source_lang, target_lang=target_lang)
        for idx, res in zip(indices, translated):
            results[idx] = res.text
        return results


# ===========================================================================
#  DeepL – inoffiziell (ohne API-Key)
# ===========================================================================

class DeepLFree:
    """Inoffizieller DeepL-Endpunkt – kein API-Key nötig.
    Nutzt denselben Endpunkt wie die DeepL Mobile-App.
    Ratenlimit: kleine Batches (≤8) + automatische Pausen empfohlen."""

    ENDPOINT = "https://www2.deepl.com/jsonrpc"
    HEADERS  = {
        "Content-Type":     "application/json",
        "Accept":           "*/*",
        "Accept-Language":  "de-DE,de;q=0.9,en;q=0.8",
        "User-Agent":       "DeepL-iOS/2.9.1 iOS/16.3.0 (iPhone13,2)",
        "x-app-os-name":    "iOS",
        "x-app-os-version": "16.3.0",
        "x-app-product":    "TRANSLATOR",
        "x-app-version":    "24.1",
        "x-app-build":      "510265",
    }

    def _make_payload(self, texts, target_lang, source_lang):
        jobs = [
            {"kind": "default",
             "sentences": [{"text": t, "id": i + 1, "prefix": ""}],
             "raw_en_context_before": [], "raw_en_context_after": [],
             "preferred_num_beams": 4}
            for i, t in enumerate(texts)
        ]
        return json.dumps({
            "jsonrpc": "2.0", "method": "LMT_handle_jobs",
            "id": randint(1_000_000, 9_999_999),
            "params": {
                "jobs": jobs,
                "lang": {"source_lang_computed": source_lang.upper(),
                         "target_lang": target_lang.upper()},
                "priority": 1,
                "commonJobParams": {"wasSpoken": False, "transcribe_as": ""},
                "timestamp": int(time.time() * 1000),
            },
        }).encode("utf-8")

    def translate_batch(self, texts, target_lang="DE", source_lang="EN"):
        indices = [i for i, t in enumerate(texts) if t.strip()]
        results = list(texts)
        if not indices:
            return results
        payload = self._make_payload([texts[i] for i in indices], target_lang, source_lang)
        req = urllib.request.Request(self.ENDPOINT, data=payload,
                                     headers=self.HEADERS, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            for idx, trans in zip(indices, data.get("result", {}).get("translations", [])):
                beams = trans.get("beams", [])
                if beams:
                    results[idx] = beams[0]["sentences"][0]["text"]
        except Exception as e:
            print(f"    [WARNUNG] Anfrage fehlgeschlagen: {e}")
        return results


# ===========================================================================
#  PokéAPI – Daten laden und Cache aufbauen
# ===========================================================================

def _fetch_text(url, log_fn):
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.read().decode("utf-8-sig")
    except Exception as e:
        log_fn(f"  WARNUNG: {url.split('/')[-1]} nicht ladbar: {e}")
        return None


def _parse_name_csv(text, en_id, de_id, key_col, name_col, lang_col):
    en_map = {}; de_map = {}
    reader = csv.reader(text.splitlines())
    next(reader, None)
    for row in reader:
        if len(row) <= max(key_col, name_col, lang_col):
            continue
        lang = row[lang_col]; key = row[key_col]; name = row[name_col]
        if not name.strip():
            continue
        if lang == en_id:   en_map[key] = name
        elif lang == de_id: de_map[key] = name
    return {en: de_map[k] for k, en in en_map.items()
            if k in de_map and en != de_map[k]}


def load_pokeapi_cache(log_fn, force_refresh=False):
    """Attacken/Items/Fähigkeiten/Typen/Pokémon aus Cache oder GitHub (parallel)."""
    cache_path = os.path.join(BASE, "pokeapi_cache.json")
    if not force_refresh and os.path.exists(cache_path):
        try:
            data = json.load(open(cache_path, encoding="utf-8"))
            log_fn(f"  PokéAPI-Cache: {len(data):,} Paare geladen")
            return data
        except Exception as e:
            log_fn(f"  WARNUNG Cache: {e}")

    log_fn("  Lade PokéAPI-Daten von GitHub (parallel) ...")
    # Spalten aller PokeAPI-Name-CSVs: entity_id | local_language_id | name | ...
    # _parse_name_csv(text, en_id, de_id, key_col, name_col, lang_col)
    sources = [
        ("move_names.csv",            0, 2, 1, "Attacken"),
        ("item_names.csv",            0, 2, 1, "Items"),
        ("ability_names.csv",         0, 2, 1, "Fähigkeiten"),
        ("type_names.csv",            0, 2, 1, "Typen"),
        ("pokemon_species_names.csv", 0, 2, 1, "Pokémon"),
    ]

    results = {}
    def _load_one(src):
        fname, kc, nc, lc, label = src
        text = _fetch_text(POKEAPI_BASE + fname, log_fn)
        if text:
            m = _parse_name_csv(text, EN_LANG_ID, DE_LANG_ID, kc, nc, lc)
            return label, m
        return label, {}

    progress("Lade PokéAPI …", 0, len(sources))
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_load_one, s): s for s in sources}
        done_count = 0
        for future in as_completed(futures):
            done_count += 1
            label, m = future.result()
            results[label] = m
            progress(f"Lade PokéAPI … ({label})", done_count, len(sources))
    progress(done=True)

    combined = {}
    for label, m in results.items():
        combined.update(m)
        log_fn(f"    {label}: {len(m):,} Paare")
    try:
        json.dump(combined, open(cache_path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    except Exception as e:
        log_fn(f"  WARNUNG Cache schreiben: {e}")
    log_fn(f"  PokéAPI-Cache gespeichert: {len(combined):,} Paare")
    return combined


def load_location_cache(log_fn, force_refresh=False):
    """Ortsnamen aus Cache oder GitHub."""
    cache_path = os.path.join(BASE, "location_cache.json")
    if not force_refresh and os.path.exists(cache_path):
        try:
            data = json.load(open(cache_path, encoding="utf-8"))
            log_fn(f"  Ortsnamen-Cache: {len(data):,} Paare geladen")
            return data
        except Exception as e:
            log_fn(f"  WARNUNG Cache: {e}")

    log_fn("  Lade Ortsnamen von GitHub ...")
    progress("Lade Ortsnamen …")
    text = _fetch_text(POKEAPI_BASE + "location_names.csv", log_fn)
    progress(done=True)
    if not text:
        return {}
    locs_en = {}; locs_de = {}
    reader = csv.reader(text.splitlines()); next(reader, None)
    for row in reader:
        if len(row) < 3: continue
        loc_id, lang_id, name = row[0], row[1], row[2]
        if not name.strip(): continue
        if lang_id == EN_LANG_ID:   locs_en[loc_id] = name
        elif lang_id == DE_LANG_ID: locs_de[loc_id] = name
    mapping = {en: locs_de[k] for k, en in locs_en.items()
               if k in locs_de and en != locs_de[k]}
    try:
        json.dump(mapping, open(cache_path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    except Exception as e:
        log_fn(f"  WARNUNG Cache schreiben: {e}")
    log_fn(f"  Ortsnamen-Cache gespeichert: {len(mapping):,} Paare")
    return mapping


def build_fix_mapping(log_fn, force_refresh=False):
    """PokéAPI + Ortsnamen + CITY_MAPPING + CITY_LITERAL_MAP kombinieren.
    Priorität: CITY_MAPPING > CITY_LITERAL_MAP > Ortsnamen > PokéAPI allgemein."""
    log_fn("\n[PokéAPI] Lade Korrekturdaten ...")
    api_map = load_pokeapi_cache(log_fn, force_refresh)
    loc_map = load_location_cache(log_fn, force_refresh)
    combined = {}
    combined.update(api_map)
    combined.update(loc_map)
    combined.update(CITY_LITERAL_MAP)  # DeepL-Literalvarianten (DE→DE Korrekturen)
    combined.update(CITY_MAPPING)      # Höchste Priorität (EN→DE offizielle Namen)
    log_fn(f"  Gesamt: {len(combined):,} EN→DE-Paare")
    return combined


# ===========================================================================
#  PokéAPI-Korrekturen auf CSV-Zeilen anwenden
# ===========================================================================

def apply_pokeapi_fixes(rows, fix_map, log_fn):
    """Korrigiert offizielle Pokémon-Begriffe in der DE-Spalte.

    Drei Strategien, in dieser Reihenfolge:
      a) Exakter Zeileninhalt-Match (EN == fix_map-Key)
      b) EN-gestützte Suche: EN-Text hat bekannten Begriff -> suche seinen
         DeepL-Output im DE-Text (auch als Kompositum-Präfix) und ersetze ihn
      c) Klassischer Regex im DE-Text (für Begriffe die DeepL unübersetzt lässt,
         z.B. englische Pokémon-Namen)
    """
    sorted_pairs  = sorted(fix_map.items(), key=lambda x: len(x[0]), reverse=True)
    lower_map     = {en.lower(): de for en, de in sorted_pairs}

    # Regex A – mit beidseitiger Wortgrenze (sicher, kein Compound-Schaden)
    pat_parts_full = [re.escape(en) for en, _ in sorted_pairs if len(en) >= 4]
    re_full = re.compile(
        r'(?<![A-Za-zÀ-ÿ])(' + '|'.join(pat_parts_full) + r')(?![A-Za-zÀ-ÿ])',
        re.IGNORECASE)

    # Regex B – nur linke Wortgrenze (für Komposita-Präfixe: SlowpokeTail, Zinnstadtmuseum)
    re_prefix = re.compile(
        r'(?<![A-Za-zÀ-ÿ])(' + '|'.join(pat_parts_full) + r')',
        re.IGNORECASE)

    def replacer_full(m):
        return lower_map.get(m.group(1).lower(), m.group(1))

    def replacer_prefix(m):
        return lower_map.get(m.group(1).lower(), m.group(1))

    # EN-seitige Regex: findet alle bekannten EN-Terme im EN-Text
    re_en = re.compile(
        r'(?<![A-Za-zÀ-ÿ])(' + '|'.join(pat_parts_full) + r')(?:[A-Za-zÀ-ÿ]*)',
        re.IGNORECASE)

    corrections = []
    total_rows = len(rows)
    for i, row in enumerate(rows):
        if i % 500 == 0:
            progress("PokéAPI-Korrekturen …", i, total_rows)
        if len(row) < 2:
            continue
        en_text  = row[0]
        de_text  = row[1]
        en_stripped = en_text.strip()

        # ── a) Exakter Zeileninhalt-Match ──────────────────────────────────
        if en_stripped in fix_map:
            correct_de = fix_map[en_stripped]
            if de_text.strip().lower() != correct_de.lower():
                corrections.append(("exakt", en_stripped, de_text, correct_de))
                rows[i][1] = correct_de
                continue

        # ── b) EN-gestützte Compound-Korrektur ─────────────────────────────
        # Sammle alle EN-Terme, die im EN-Text vorkommen (inkl. Compound-Präfix)
        en_hits = re_en.findall(en_text)  # gibt nur die capture group zurück
        if en_hits:
            working = de_text
            for en_hit in dict.fromkeys(h.lower() for h in en_hits):  # dedup
                correct_de = lower_map.get(en_hit)
                if not correct_de:
                    continue
                # Suche den EN-Begriff ODER seinen DE-Gegenpart im DE-Text
                # als vollständiges Wort ODER als Kompositum-Präfix
                search_terms = [en_hit, correct_de.lower()]
                for term in search_terms:
                    pat = re.compile(
                        r'(?<![A-Za-zÀ-ÿ])' + re.escape(term),
                        re.IGNORECASE)
                    def _repl(m, _corr=correct_de, _term=term, _en=en_hit):
                        matched = m.group(0)
                        # Bewahre die Großschreibung des Originals wenn möglich
                        if matched[0].isupper() and len(_corr) > 0:
                            return _corr[0].upper() + _corr[1:]
                        return _corr
                    new_working = pat.sub(_repl, working)
                    if new_working != working:
                        working = new_working
                        break  # ein Term gefunden reicht pro EN-Hit
            if working != de_text:
                corrections.append(("en-gestützt", en_text[:60], de_text[:60], working[:60]))
                rows[i][1] = working
                de_text = working  # für Pass c)

        # ── c) Klassischer Regex im DE-Text ────────────────────────────────
        # Fängt Terme, die DeepL unübersetzt im DE lässt (z.B. engl. Pokémon-Namen)
        new_de = re_full.sub(replacer_full, de_text)
        if new_de != de_text:
            corrections.append(("regex-de", en_text[:60], de_text[:60], new_de[:60]))
            rows[i][1] = new_de
            # Zusatz: Compound-Präfixe (SlowpokeTail etc.)
            new_de2 = re_prefix.sub(replacer_prefix, new_de)
            if new_de2 != new_de:
                rows[i][1] = new_de2
        else:
            # Nur Compound-Prefix-Pass wenn kein vollständiger Match
            new_de_prefix = re_prefix.sub(replacer_prefix, de_text)
            if new_de_prefix != de_text:
                corrections.append(("kompositum", en_text[:60], de_text[:60], new_de_prefix[:60]))
                rows[i][1] = new_de_prefix

    progress(done=True)

    by_type = {}
    for c in corrections:
        by_type[c[0]] = by_type.get(c[0], 0) + 1
    summary = ", ".join(f"{k}: {v}" for k, v in sorted(by_type.items()))
    log_fn(f"  PokéAPI-Korrekturen: {len(corrections)} gesamt ({summary})")
    return corrections


# ===========================================================================
#  german.dat aus Mapping bauen
# ===========================================================================

def build_dat(en_data, mapping, out_path, src_path, log_fn):
    # Sicherheit: niemals die Quelldatei überschreiben
    if os.path.abspath(out_path) == os.path.abspath(src_path):
        log_fn(f"FEHLER: Ausgabepfad ist identisch mit Quelldatei: {out_path}")
        log_fn("  german.dat und messange.dat dürfen nicht denselben Pfad haben.")
        return 0
    counter = [0]
    de_data = apply_translations(en_data, mapping, counter)
    log_fn(f"  {counter[0]:,} Strings ersetzt")
    out_bytes = RbWriter().dump(de_data)
    if os.path.exists(out_path):
        bak = out_path + '.bak'
        shutil.copy2(out_path, bak)
        log_fn(f"  Backup: {bak}")
    with open(out_path, 'wb') as f:
        f.write(out_bytes)
    log_fn(f"  {len(out_bytes)/1024/1024:.1f} MB → {out_path}")
    # Prüfen ob Quelldatei noch vorhanden (könnte durch AV-Software entfernt werden)
    if not os.path.exists(src_path):
        log_fn(f"\n  WARNUNG: {src_path} ist nach dem Schreiben nicht mehr vorhanden!")
        log_fn("  Mögliche Ursache: Antivirus-Software hat die Datei in Quarantäne verschoben.")
        log_fn("  Bitte Antivirus-Quarantäne prüfen und messange.dat wiederherstellen.")
    return counter[0]


# ===========================================================================
#  Übersetzungs-Hilfsfunktion
# ===========================================================================

def translate_strings(strings, translator, target_lang, source_lang,
                      cache, batch_size, limit, log_fn):
    mapping = {}; new_idx = []
    for i, s in enumerate(strings):
        if s in cache:   mapping[s] = cache[s]
        elif s.strip():  new_idx.append(i)

    log_fn(f"  {len(mapping):,} aus Cache, {len(new_idx):,} neu zu übersetzen")
    if limit and 0 < limit < len(new_idx):
        log_fn(f"  (Limit: max. {limit})")
        new_idx = new_idx[:limit]
    if not new_idx:
        return mapping

    log_fn(f"  ~{sum(len(strings[i]) for i in new_idx):,} Zeichen")
    batches = [new_idx[j:j + batch_size] for j in range(0, len(new_idx), batch_size)]
    log_fn(f"  {len(batches)} Batch(es) à max. {batch_size}")
    log_fn("")  # Platz für Fortschrittsbalken

    done = 0
    start_time = time.time()
    for bi, batch in enumerate(batches):
        progress(f"Batch {bi+1}/{len(batches)}", done, len(new_idx))
        try:
            translated = translator.translate_batch(
                [strings[i] for i in batch],
                target_lang=target_lang, source_lang=source_lang)
        except Exception as e:
            progress(done=True)
            log_fn(f"  WARNUNG Batch {bi + 1}: {e}")
            translated = [strings[i] for i in batch]

        for orig_i, trans in zip(batch, translated):
            en  = strings[orig_i]
            tr  = fix_umlauts(trans)
            mapping[en] = tr; cache[en] = tr
        done += len(batch)

        elapsed = time.time() - start_time
        rate    = done / elapsed if elapsed > 0 else 1
        eta_s   = int((len(new_idx) - done) / rate) if rate > 0 else 0
        eta_str = f"  ETA {eta_s//60}m{eta_s%60:02d}s" if eta_s > 5 else ""
        progress(f"Batch {bi+1}/{len(batches)}{eta_str}", done, len(new_idx))

        if bi < len(batches) - 1:
            time.sleep(0.3)

    progress(done=True)
    elapsed = time.time() - start_time
    log_fn(f"  {done:,} Strings übersetzt in {elapsed:.1f}s")
    return mapping


# ===========================================================================
#  Argumente
# ===========================================================================

def parse_args():
    p = argparse.ArgumentParser(
        description="Übersetzt messange.dat → german.dat (DE-Patch für Pokémon Infinite Fusion)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Modi:
  Mit API-Key (empfohlen):  python translate_deepl.py --key DEIN_KEY
  Ohne API-Key (inoffiziell): python translate_deepl.py --no-key
  Nur bauen:                python translate_deepl.py --build
  Nur PokéAPI-Korrekturen:  python translate_deepl.py --fix-only
""")
    dg = p.add_mutually_exclusive_group()
    dg.add_argument("--key",      metavar="KEY",
                    help="DeepL API-Key (Free (':fx'), Pro oder env DEEPL_API_KEY)")
    dg.add_argument("--no-key",   action="store_true",
                    help="Inoffizieller DeepL-Endpunkt – kein API-Key nötig")
    dg.add_argument("--build",    action="store_true",
                    help="CSV lesen + german.dat bauen (kein DeepL)")
    dg.add_argument("--fix-only", action="store_true",
                    help="Nur PokéAPI-Korrekturen auf bestehende CSV anwenden")

    p.add_argument("--src",    default=os.path.join(BASE, "messange.dat"))
    p.add_argument("--out",    default=os.path.join(BASE, "german.dat"))
    p.add_argument("--csv",    default=os.path.join(BASE, "translations.csv"))
    p.add_argument("--cache",  default=os.path.join(BASE, "translation_cache.json"))
    p.add_argument("--lang",     default="DE",  help="Zielsprache (Standard: DE)")
    p.add_argument("--src-lang", default="EN",  help="Quellsprache (Standard: EN)")
    p.add_argument("--limit",    type=int, default=0,
                   help="Max. N neue Strings übersetzen (0 = kein Limit)")
    p.add_argument("--batch",    type=int, default=50,
                   help="Strings pro Anfrage (Standard: 50; für --no-key: 8)")
    p.add_argument("--no-pokeapi",    action="store_true",
                   help="PokéAPI-Korrekturen überspringen")
    p.add_argument("--refresh-cache", action="store_true",
                   help="PokéAPI-Cache neu laden (ignoriert vorhandene .json)")
    p.add_argument("--dry-run",       action="store_true",
                   help="Nur zählen – keine Anfragen, keine Datei schreiben")
    return p.parse_args()


# ===========================================================================
#  Hauptprogramm
# ===========================================================================

def main():
    args = parse_args()
    log_lines = []
    log_file  = os.path.join(BASE, "deepl_translate_log.txt")

    def log(msg=""):
        print(msg); log_lines.append(str(msg))

    def save_log():
        try:
            open(log_file, 'w', encoding='utf-8').write("\n".join(log_lines))
        except Exception:
            pass

    log("=" * 65)
    log("  translate_deepl.py – Pokémon Infinite Fusion DE-Patch")
    log("=" * 65)
    log(f"  Verzeichnis: {BASE}")

    # ══════════════════════════════════════════════════════════════════════
    #  MODUS: --fix-only  →  PokéAPI-Korrekturen auf vorhandene CSV
    # ══════════════════════════════════════════════════════════════════════
    if args.fix_only:
        log("\n[MODUS] --fix-only: PokéAPI-Korrekturen auf bestehende CSV")
        _, rows = load_csv(args.csv, log)
        if not rows:
            log(f"FEHLER: CSV nicht gefunden: {args.csv}"); save_log(); sys.exit(1)
        fix_map = build_fix_mapping(log, args.refresh_cache)
        log("\n[Korrektur] Wende Fixes an ...")
        apply_pokeapi_fixes(rows, fix_map, log)
        if os.path.exists(args.csv):
            shutil.copy2(args.csv, args.csv + ".pre_fix.bak")
        save_csv(rows, args.csv, log)
        log("\nFERTIG."); save_log(); return

    # ══════════════════════════════════════════════════════════════════════
    #  MODUS: --build  →  CSV → german.dat
    # ══════════════════════════════════════════════════════════════════════
    if args.build:
        log("\n[MODUS] --build: Lese CSV → schreibe german.dat")
        if not os.path.exists(args.src):
            log(f"FEHLER: Quelldatei nicht gefunden: {args.src}"); save_log(); sys.exit(1)
        log(f"\n[1/3] Lade CSV: {args.csv}")
        mapping, _ = load_csv(args.csv, log)
        if mapping is None:
            log("FEHLER: CSV nicht gefunden. Zuerst ohne --build ausführen.")
            save_log(); sys.exit(1)
        log(f"\n[2/3] Parse {args.src} ...")
        try:
            en_data = RbReader(open(args.src, 'rb').read()).load()
        except Exception as e:
            log(f"FEHLER beim Parsen: {e}"); save_log(); sys.exit(1)
        log(f"  OK – {len(en_data)} Einträge")
        log(f"\n[3/3] Baue {args.out} ...")
        n = build_dat(en_data, mapping, args.out, args.src, log)
        log(f"\n{'=' * 65}")
        log(f"  FERTIG! {n:,} Strings eingebaut.")
        log(f"{'=' * 65}")
        save_log(); return

    # ══════════════════════════════════════════════════════════════════════
    #  MODUS: Übersetzen (--key / --no-key / interaktiv)
    # ══════════════════════════════════════════════════════════════════════

    if not os.path.exists(args.src):
        log(f"\nFEHLER: Quelldatei nicht gefunden: {args.src}"); save_log(); sys.exit(1)

    # ── Translator bestimmen ─────────────────────────────────────────────
    translator = None

    if args.dry_run:
        log("\n[DRY-RUN] Kein Translator – nur Zählen")

    elif args.no_key:
        log("\n[MODUS] Ohne API-Key (inoffizieller DeepL-Endpunkt)")
        log("  Ratenlimit: kleine Batches + automatische Pausen")
        translator = DeepLFree()
        args.batch = min(args.batch, 8)
        log(f"  Batch-Größe: {args.batch}")

    else:
        api_key = (args.key or os.environ.get("DEEPL_API_KEY", "") or HARDCODED_API_KEY)
        if not api_key:
            log("\nKein DeepL API-Key.\nOptionen:")
            log("  1) Kostenloser Key (500k Zeichen/Monat): https://www.deepl.com/de/pro#developer")
            log("  2) Ohne Key:  python translate_deepl.py --no-key")
            log()
            api_key = input("  API-Key eingeben (oder Enter für --no-key Modus): ").strip()
            if not api_key:
                log("  → Starte im --no-key Modus")
                translator = DeepLFree()
                args.batch = min(args.batch, 8)

        if translator is None and api_key:
            tier = "Free (api-free.deepl.com)" if api_key.endswith(":fx") else "Pro (api.deepl.com)"
            log(f"\n[MODUS] Mit API-Key • Tier: {tier}")
            translator = DeepLOfficial(api_key)
            try:
                log(f"  Nutzung: {translator.usage()}")
            except Exception as e:
                log(f"  WARNUNG Nutzungsabfrage: {e}")

    # ── Translation-Cache laden ───────────────────────────────────────────
    trans_cache = {}
    if os.path.exists(args.cache):
        try:
            trans_cache = json.load(open(args.cache, encoding='utf-8'))
            log(f"\nTranslation-Cache: {len(trans_cache):,} Einträge")
        except Exception as e:
            log(f"WARNUNG Cache: {e}")

    # ── messange.dat parsen ───────────────────────────────────────────────
    log(f"\n[1] Parse {args.src} ({os.path.getsize(args.src)/1024/1024:.1f} MB) ...")
    try:
        en_data = RbReader(open(args.src, 'rb').read()).load()
    except Exception as e:
        log(f"FEHLER beim Parsen:\n{traceback.format_exc()}"); save_log(); sys.exit(1)
    log(f"  OK – {len(en_data)} Einträge")

    # ── Strings extrahieren ───────────────────────────────────────────────
    log(f"\n[2] Strings extrahieren ...")
    all_strings    = collect_strings(en_data)
    unique_strings = list(dict.fromkeys(s for s in all_strings if s and s.strip()))
    log(f"  {len(all_strings):,} Vorkommen, {len(unique_strings):,} eindeutig")

    # ── Vorhandene CSV laden + Inkremental-Vergleich ──────────────────────
    log(f"\n[3] Prüfe vorhandene CSV: {args.csv}")
    existing_map, existing_rows = load_csv(args.csv, log)

    if existing_map:
        new_strings = [s for s in unique_strings if s not in existing_map]
        log(f"  Neu in messange.dat (nicht in CSV): {len(new_strings):,} Strings")
        if not new_strings and not args.dry_run:
            log("  Alle Strings bereits in CSV. Wende nur PokéAPI-Korrekturen an ...")
            if not args.no_pokeapi:
                fix_map = build_fix_mapping(log, args.refresh_cache)
                apply_pokeapi_fixes(existing_rows, fix_map, log)
                if os.path.exists(args.csv):
                    shutil.copy2(args.csv, args.csv + ".bak")
                save_csv(existing_rows, args.csv, log)
            log("\nFERTIG."); save_log(); return
        strings_to_translate = new_strings
    else:
        log("  Keine CSV – Erstübersetzung")
        strings_to_translate = unique_strings

    # ── Übersetzen ────────────────────────────────────────────────────────
    log(f"\n[4] Übersetze {len(strings_to_translate):,} Strings ...")
    if args.dry_run:
        log("  [DRY-RUN] Keine Anfragen.")
        new_mapping = {s: s for s in strings_to_translate}
    else:
        new_mapping = translate_strings(
            strings_to_translate, translator,
            args.lang, args.src_lang,
            trans_cache, args.batch, args.limit, log)

    # ── Translation-Cache speichern ───────────────────────────────────────
    if not args.dry_run:
        try:
            json.dump(trans_cache, open(args.cache, 'w', encoding='utf-8'),
                      ensure_ascii=False, separators=(',', ':'))
            log(f"  Translation-Cache: {len(trans_cache):,} Einträge gespeichert")
        except Exception as e:
            log(f"WARNUNG Cache: {e}")

    # ── Zeilen zusammenführen ─────────────────────────────────────────────
    if existing_map:
        used_keys = {row[0] for row in existing_rows if row}
        for en, de in new_mapping.items():
            if en not in used_keys:
                existing_rows.append([en, de])
        all_rows = existing_rows
        log(f"  {len(new_mapping):,} neue Einträge zu CSV hinzugefügt")
    else:
        all_rows = [[s, new_mapping.get(s, s)] for s in unique_strings]

    # ── PokéAPI-Korrekturen anwenden ──────────────────────────────────────
    if not args.no_pokeapi and not args.dry_run:
        fix_map = build_fix_mapping(log, args.refresh_cache)
        log(f"\n[5] Wende PokéAPI-Korrekturen an ...")
        apply_pokeapi_fixes(all_rows, fix_map, log)
    elif args.no_pokeapi:
        log("\n[5] PokéAPI-Korrekturen übersprungen (--no-pokeapi)")

    # ── CSV speichern ─────────────────────────────────────────────────────
    if not args.dry_run:
        if os.path.exists(args.csv):
            shutil.copy2(args.csv, args.csv + ".bak")
        log(f"\n[6] Speichere CSV ...")
        save_csv(all_rows, args.csv, log)

    # ── german.dat bauen ─────────────────────────────────────────────────
    if not args.dry_run:
        log(f"\n[7] Baue {args.out} ...")
        full_map = {row[0]: row[1] for row in all_rows if len(row) >= 2 and row[0]}
        n = build_dat(en_data, full_map, args.out, args.src, log)
        log(f"\n{'=' * 65}")
        log(f"  FERTIG! {n:,} Strings übersetzt und eingebaut.")
        log(f"  ➜ translations.csv prüfen, dann --build für german.dat")
        log(f"{'=' * 65}")
    else:
        log(f"\n{'=' * 65}")
        log(f"  DRY-RUN: {len(strings_to_translate):,} Strings würden übersetzt.")
        log(f"  ➜ python translate_deepl.py --key KEY   (mit Key)")
        log(f"  ➜ python translate_deepl.py --no-key    (ohne Key)")
        log(f"{'=' * 65}")

    save_log()
    log(f"  Log: {log_file}")


# ===========================================================================
#  Einstiegspunkt
# ===========================================================================

if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        if e.code and e.code != 0:
            print(f"\nProgramm mit Fehler beendet (Code {e.code}).")
    except KeyboardInterrupt:
        print("\n\nAbgebrochen.")
    except Exception:
        print("\nUnerwarteter Fehler:")
        traceback.print_exc()
    finally:
        input("\nDrücke Enter zum Schließen ...")


