# Projekt-Anweisungen für Claude Code

## Wichtige Hinweise für die Entwicklung

### Character Encoding - NICHT ÄNDERN ohne Tests!

**KRITISCH**: Die aktuelle Implementierung verwendet ISO-8859-1 Encoding und funktioniert perfekt mit Netscape Navigator 3 auf Classic Mac OS 7.5.

#### Aktuelle Konfiguration (BEWÄHRT):

- **Server → Browser**: ISO-8859-1 (`iso-8859-1`)
- **Browser → Server**: ISO-8859-1 (`iso-8859-1`)
- **Umlaute**: ä, ö, ü, ß funktionieren einwandfrei
- **Netscape Einstellung**: "Western" Character Set

#### Was funktioniert:

```python
def sanitize(text):
    text = unicodedata.normalize('NFC', text)
    # Unicode → ISO-8859-1 Konvertierung
    # Umlaute (ä=0xE4, ö=0xF6, ü=0xFC, ß=0xDF) sind in ISO-8859-1 vorhanden
```

```python
def send_html(self, content):
    data = content.encode("iso-8859-1", errors="replace")
    self.send_header("Content-Type", "text/html")
```

```python
def do_POST(self):
    body = self.rfile.read(content_length).decode("iso-8859-1", errors="replace")
```

#### WARNUNG:

**ÄNDERE NIEMALS** ohne vorherige Tests auf Classic Mac:
- Das Encoding (`iso-8859-1` → UTF-8)
- Die `sanitize()` Funktion
- Character-Mappings für Sonderzeichen
- Content-Type Headers

**GRUND**: Netscape 3 auf Classic Mac ist extrem wählerisch beim Encoding. Die aktuelle Lösung ist das Ergebnis ausgiebiger Tests. Änderungen können dazu führen, dass:
- Umlaute als Fragezeichen erscheinen
- Text komplett unleserlich wird
- Der Browser abstürzt
- Mac Script Manager falsche Zeichen anzeigt

### Think C Compiler Einschränkungen

Der Code-Assistent ist spezialisiert auf **Think C 7** unter MacOS 7.5:

#### Think C unterstützt NICHT:
- Volles ANSI C89 (nur Subset)
- Moderne C99/C11 Features
- Lange Funktionsnamen (max. 31 Zeichen)
- `//` Kommentare (nur `/* */`)
- Inline-Funktionen
- Variable-Length Arrays

#### Think C BENÖTIGT:
- Pascal-Strings (`"\pHello"`)
- Toolbox-Aufrufe (Mac APIs)
- Handle-basierte Speicherverwaltung (`Handle h = NewHandle(size)`)
- `#include <Types.h>`, `<QuickDraw.h>`, etc.
- Explizite `EventRecord`, `WindowPtr`, `GrafPtr` Typen

### Browser-Kompatibilität

**Ziel-Browser**: Netscape Navigator 3.04 auf MacOS 7.5

#### Unterstützte HTML-Features:
- HTML 3.2 (NICHT HTML 4 oder 5!)
- `<TABLE>`, `<FORM>`, `<TEXTAREA>`
- `<META HTTP-EQUIV="Refresh">`
- Basis-Formatierung (`<B>`, `<I>`, `<PRE>`, `<BLOCKQUOTE>`)

#### NICHT unterstützt:
- CSS (kein `<STYLE>`, kein `class=`)
- JavaScript (wird ignoriert)
- AJAX/XMLHttpRequest
- `<DIV>`, `<SPAN>` (eingeschränkt)
- Moderne Form-Elemente

### API-Konfiguration

```python
CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096
REFRESH_SECONDS = 3  # Wichtig für Netscape - nicht zu kurz!
```

**REFRESH_SECONDS**: Nicht unter 2 Sekunden setzen, sonst wird Netscape 3 überfordert.

### System Prompts

Die drei System-Prompts sind fein abgestimmt auf Classic Mac Entwicklung:

1. **SYSTEM_PROMPT_CODE**: Think C Expertise
2. **SYSTEM_PROMPT_REZ**: Rez-Format für Resources
3. **SYSTEM_PROMPT_GENERAL**: Allgemeine Mac Toolbox Hilfe

**Beim Ändern beachten**:
- Kurze, präzise Antworten (Netscape 3 ist langsam)
- Deutsche Sprache beibehalten
- Think C Limitierungen erwähnen
- MacOS 7.5 Kompatibilität betonen

### Threading-Modell

```python
def create_job(mode, prompt, system_prompt):
    # Background Thread für API-Call
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return job_id
```

**Warum**: Netscape 3 hat sehr kurze Timeouts. Ohne Background-Threading würde der Browser die Verbindung abbrechen bevor Claude antwortet.

**META REFRESH**: Die einzige Methode für "asynchrone" Updates in Netscape 3.

### Shared Folder

```python
def read_shared_file(filename):
    try:
        return filepath.read_text(encoding="mac_roman", errors="replace")
    except:
        try:
            return filepath.read_text(encoding="utf-8", errors="replace")
```

**Reihenfolge wichtig**:
1. Erst `mac_roman` versuchen (Classic Mac Files)
2. Fallback zu `utf-8` (moderne Dateien)

### Entwicklungs-Workflow

Wenn neue Features hinzugefügt werden:

1. **IMMER** auf echtem Classic Mac / Basilisk II testen
2. **NIEMALS** Encoding ändern ohne Test
3. HTML 3.2 Validator verwenden
4. Keine modernen Web-Features verwenden
5. Performance beachten (Netscape 3 ist LANGSAM)

### Bekannte Einschränkungen

- Keine Syntax-Highlighting (würde JavaScript benötigen)
- Kein Live-Preview (META REFRESH ist das Maximum)
- Keine Keyboard-Shortcuts (außer Browser-Standard)
- Maximale Textlänge in TEXTAREA limitiert
- Kein Copy-to-Clipboard via Button (daher `/text/` Endpoint)

### Python-Version

Aktuell: Python 3.12

**Kompatibilität**: Code sollte mit Python 3.8+ funktionieren, nutzt aber:
- `Path` (pathlib)
- f-Strings
- Type Hints (optional, nur in Kommentaren)

### Sicherheit

**WICHTIG**: Dieser Server ist NICHT für Production gedacht:
- Keine Authentifizierung
- Keine Rate-Limiting
- Kein HTTPS (HTTP only)
- Direkter Dateisystem-Zugriff via Shared Folder
- API Key im Environment

**Nutzung**: Nur in vertrauenswürdigen Netzwerken (lokales Netz / Emulator).

## Zusammenfassung

**ABSOLUTE DON'Ts**:
- ❌ Encoding von ISO-8859-1 ändern
- ❌ HTML über 3.2 verwenden
- ❌ CSS oder JavaScript hinzufügen
- ❌ Think C Limitierungen ignorieren
- ❌ REFRESH_SECONDS < 2 setzen

**IMMER**:
- ✅ Auf Classic Mac testen
- ✅ Umlaute testen (ä, ö, ü, ß)
- ✅ HTML 3.2 konform bleiben
- ✅ Deutsche Sprache in UI beibehalten
- ✅ Think C Kompatibilität prüfen
- ✅ Netscape 3 Limitierungen beachten
