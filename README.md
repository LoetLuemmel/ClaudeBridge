# Claude Bridge Server v1.2

Ein HTTP-Server, der Claude AI fuer Classic Mac OS Systeme (MacOS 7.5 in Basilisk II) mit Netscape 3 zugaenglich macht.

## Ueberblick

Dieser Server ermoeglicht es, von einem Vintage Mac mit Netscape Navigator 3 auf die Claude API zuzugreifen. Der Server ist speziell fuer die Einschraenkungen alter Browser optimiert (HTML 3.2, ISO-8859-1 Encoding, META REFRESH fuer asynchrone Updates).

**Neu in v1.2**: Configuration-File-Support, strukturiertes Logging, Unit Tests, Security-Hardening, Graceful Shutdown

## Quick Start

```bash
# 1. Dependencies installieren
pip install pyyaml

# 2. API Key einrichten
mkdir -p ~/.config/anthropic
echo 'sk-ant-...' > ~/.config/anthropic/api_key
chmod 600 ~/.config/anthropic/api_key

# 3. Server starten
python3 claude_bridge.py --shared-folder ~/Desktop/Share

# 4. Browser oeffnen
# http://localhost:8080/
```

Das war's! Der Server laeuft und ist bereit fuer Netscape 3.

## Features

### Drei Hauptfunktionen:

1. **Code-Assistent** - Think C Code schreiben, analysieren und debuggen
   - Spezialisiert auf Think C 7 unter MacOS 7.5
   - Toolbox-API Kenntnisse
   - Handle-basierte Speicherverwaltung
   - Pascal-String Unterstuetzung

2. **Resource-Generator** - Rez-Quelltext generieren
   - MENU, DLOG, DITL, WIND, ICON, etc.
   - Fertiger Rez-Code zum Kompilieren

3. **Frage & Antwort** - Allgemeine Classic Mac Programmierung
   - Toolbox-Fragen
   - Debugging-Hilfe
   - Architektur-Beratung

### Technische Features:

- **Background Threading**: API-Calls laufen im Hintergrund
- **META REFRESH**: Automatische Seitenaktualisierung waehrend Claude arbeitet
- **ISO-8859-1 Encoding**: Kompatibel mit Netscape "Western" Zeichensatz
- **HTML 3.2**: Funktioniert mit alten Browsern
- **Shared Folder**: Dateien zwischen Mac und Server austauschen
- **Conversation History**: Letzte 20 Fragen/Antworten werden gespeichert
- **Text-Export**: Einfaches Kopieren von Claude's Antworten

### Neue Features in v1.2:

- **Configuration File**: YAML-basierte Konfiguration (config.yaml)
- **Strukturiertes Logging**: Log zu Datei und/oder Console mit konfigurierbarem Level
- **Security Hardening**: Path-Traversal-Prevention, Job-Timeouts, Race-Condition-Fixes
- **Graceful Shutdown**: Sauberes Herunterfahren mit Warten auf laufende Jobs
- **Unit Tests**: 22 Tests fuer kritische Funktionen (100% Pass-Rate)
- **Job Error Handling**: Robuste Fehlerbehandlung mit aussagekraeftigen Meldungen

## Installation

### Voraussetzungen

- Python 3.8 oder neuer (getestet mit 3.12)
- PyYAML (fuer config.yaml Support)
- Anthropic API Key
- Basilisk II Emulator mit MacOS 7.5 und Netscape 3 (optional)

### Dependencies installieren

```bash
pip install -r requirements.txt
```

oder mit uv (empfohlen):

```bash
uv pip install -r requirements.txt
```

Manuell:
```bash
pip install pyyaml
```

### API Key einrichten

Option 1 (empfohlen):
```bash
mkdir -p ~/.config/anthropic
echo 'sk-ant-...' > ~/.config/anthropic/api_key
chmod 600 ~/.config/anthropic/api_key
```

Option 2: .env Datei im Projektverzeichnis erstellen

Option 3: Environment Variable setzen:
```bash
export ANTHROPIC_API_KEY='sk-ant-...'
```

## Verwendung

### Manueller Start

```bash
python3 claude_bridge.py --port 8080 --host 0.0.0.0 --shared-folder ~/Desktop/Share
```

### Mit Start-Script (macOS)

```bash
sudo ./start_bridge.sh
```

Das Script:
- Deaktiviert temporaer die Firewall
- Startet den Server
- Reaktiviert die Firewall beim Beenden

### Parameter

- `--port`: Port (Standard: 8080, ueberschreibbar via config.yaml)
- `--host`: Host-Adresse (Standard: 0.0.0.0, ueberschreibbar via config.yaml)
- `--shared-folder`: Pfad zum Shared Folder fuer Dateienaustausch
- `--config`: Pfad zur Config-Datei (Standard: config.yaml)

### Zugriff

Im Browser (Netscape 3 auf Classic Mac oder modern):
```
http://[SERVER-IP]:8080/
```

## Architektur

### Server-Komponenten

- **HTTP Server**: BaseHTTPRequestHandler mit Threading
- **Job Queue**: Background-Verarbeitung von API-Calls
- **File Management**: Lesen/Schreiben im Shared Folder
- **Character Sanitization**: Unicode → ISO-8859-1 Konvertierung
- **HTML Templates**: HTML 3.2 konforme Seiten

### System Prompts

Der Server verwendet spezialisierte System-Prompts:
- **SYSTEM_PROMPT_CODE**: Think C Programmierung
- **SYSTEM_PROMPT_REZ**: Resource-Datei Generierung
- **SYSTEM_PROMPT_GENERAL**: Allgemeine Mac-Entwicklung

### Workflow

1. Benutzer sendet Anfrage via HTML-Formular
2. Server erstellt Background-Job
3. "Bitte warten" Seite mit META REFRESH
4. Claude API Call im Background
5. Automatische Weiterleitung zum Ergebnis
6. Ergebnis mit Speicher- und Nachfrage-Optionen

## Technische Details

### Character Encoding

- **Input**: ISO-8859-1 vom Browser
- **Processing**: Unicode intern
- **Output**: ISO-8859-1 fuer Netscape
- **Umlauts**: ä, ö, ü, ß werden korrekt behandelt
- **Sonderzeichen**: Automatische Ersetzung (– → -, " → ")

### Browser-Kompatibilitaet

- HTML 3.2 konform (keine CSS, kein JavaScript)
- TABLE-basiertes Layout
- META REFRESH fuer Updates
- TEXTAREA statt contenteditable
- Einfache Forms ohne AJAX

### API-Nutzung

- Model: claude-sonnet-4-20250514
- Max Tokens: 4096
- Timeout: 120 Sekunden
- Fehlerbehandlung mit aussagekraeftigen Meldungen

## Konfiguration

### Configuration File (config.yaml)

**Neu in v1.2**: Alle Einstellungen koennen via config.yaml konfiguriert werden.

Beispiel `config.yaml`:

```yaml
# Server Settings
server:
  host: "0.0.0.0"
  port: 8080

# Claude API Settings
claude:
  model: "claude-sonnet-4-20250514"
  max_tokens: 4096
  timeout: 120  # seconds for API call

# Job Management
jobs:
  timeout: 180  # seconds (3 minutes)
  max_history: 10  # max jobs to keep in memory
  refresh_interval: 3  # seconds for META REFRESH

# File Management
files:
  shared_folder: null  # path to shared folder

# History
history:
  max_entries: 20  # max conversation history entries

# Logging
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  file: "claude_bridge.log"  # log file path (null = no file logging)
  console: true  # log to console
```

**Hinweis**: config.yaml ist optional. Ohne Config-File werden Default-Werte verwendet.

### Command-Line-Parameter ueberschreiben Config

Command-Line-Parameter haben Vorrang vor config.yaml:

```bash
python3 claude_bridge.py --port 9090 --config my_config.yaml
# Port 9090 wird verwendet, auch wenn config.yaml etwas anderes sagt
```

### Logging

**Neu in v1.2**: Strukturiertes Logging mit konfigurierbarem Level.

Log-Levels:
- `DEBUG`: Alle Details inkl. Path-Validierung
- `INFO`: Standard-Betrieb, Job-Lifecycle (empfohlen)
- `WARNING`: Warnungen (z.B. API Key fehlt, Path-Traversal-Versuche)
- `ERROR`: Fehler bei Job-Ausfuehrung

Beispiel Log-Ausgabe:
```
2025-01-15 14:32:10 [INFO] API Key: loaded from /Users/.../.config/anthropic/api_key
2025-01-15 14:32:10 [INFO] Job 1 created: Code - Schreibe ein Hello World...
2025-01-15 14:32:15 [INFO] Job 1 completed in 4.8s
2025-01-15 14:32:20 [WARNING] Path traversal attempt blocked: ../../../etc/passwd
```

### Start-Script (start_bridge.sh)

```bash
PYTHON="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
SHARED="/Users/pitforster/Desktop/Share"
HOST="192.168.3.154"
PORT=8080
```

## Security

### Security-Verbesserungen in v1.2

Der Server wurde mit mehreren Security-Features gehaertet:

1. **Path Traversal Prevention**
   - `validate_safe_path()` Funktion validiert alle Dateipfade
   - Verhindert `../` Attacken
   - Alle File-Operationen geschuetzt

2. **Filename Sanitization**
   - Whitelist fuer Dateinamen: nur `a-zA-Z0-9._-`
   - Verhindert versteckte Dateien (`.`)
   - Ersetzt unsichere Zeichen

3. **Job Timeout**
   - Automatischer Timeout nach 180 Sekunden (konfigurierbar)
   - Verhindert haengende Jobs
   - Benutzerfreundliche Timeout-Meldung

4. **Race Condition Fixes**
   - Thread-Locks bei allen Job-Operationen
   - Double-Check vor Delete
   - Keine Crashes bei concurrent Access

5. **Error Handling**
   - try/except um alle kritischen Operationen
   - Jobs werden als "error" markiert statt ewig "working"
   - Aussagekraeftige Fehlermeldungen

### Security-Limitierungen

**Wichtig**: Dieser Server ist NICHT fuer Production gedacht:
- ❌ Keine Authentifizierung
- ❌ Kein HTTPS (nur HTTP)
- ❌ Kein Rate-Limiting
- ❌ Direkter Dateisystem-Zugriff via Shared Folder
- ❌ API Key im Environment/Config

**Nutzung**: Nur in vertrauenswuerdigen Netzwerken (lokales Netz / Emulator).

## Testing

### Unit Tests ausfuehren

```bash
python3 test_claude_bridge.py
```

**Test Coverage** (22 Tests):
- ✅ Path Validation (6 Tests)
- ✅ Character Sanitization (6 Tests)
- ✅ Filename Validation (4 Tests)
- ✅ Config Loading (2 Tests)
- ✅ File Management (4 Tests)

Alle Tests haben eine 100% Pass-Rate.

### Test-Kategorien

1. **TestPathValidation**: Path-Traversal-Prevention
   - Valid paths accepted
   - `../` attacks blocked
   - Absolute paths blocked
   - Sneaky attempts blocked

2. **TestSanitization**: ISO-8859-1 Character-Handling
   - ASCII passthrough
   - German umlauts preserved
   - Unicode quotes/dashes replaced
   - Emojis removed

3. **TestFilenameValidation**: Filename-Sanitization
   - Safe filenames pass
   - Dangerous chars removed
   - Spaces replaced

4. **TestConfigLoading**: Config-Struktur validiert

5. **TestFileManagement**: File-Operationen getestet

## Entwicklung

### Dateistruktur

```
AppleBridge/
├── claude_bridge.py       # Haupt-Server (730 Zeilen)
├── test_claude_bridge.py  # Unit Tests (232 Zeilen)
├── config.yaml            # Configuration File
├── requirements.txt       # Python Dependencies
├── start_bridge.sh        # Start-Script (macOS)
├── CLAUDE.md              # Entwicklungs-Guidelines
├── README.md              # Diese Datei (425 Zeilen)
└── .gitignore             # Git-Ignore-Regeln
```

### Entwicklungs-Guidelines

Siehe `CLAUDE.md` fuer wichtige Hinweise:
- ⚠️ **KRITISCH**: ISO-8859-1 Encoding NICHT aendern!
- Think C Compiler-Einschraenkungen
- Netscape 3 HTML 3.2 Kompatibilitaet
- System Prompt Guidelines

### Erweiterungen

Moegliche Erweiterungen:
- Weitere Programmiersprachen (Pascal, Assembly)
- Authentifizierung (Basic Auth, Token)
- HTTPS Support
- Session-Management
- Multi-User Support
- Export in verschiedene Formate

## Lizenz

Keine Lizenz angegeben.

## Autor

Peter Forster

## Version

**Aktuelle Version**: 1.2 (Januar 2025)

### Changelog

#### v1.2 (2025-01-15)
- ✨ **Feature**: Configuration File Support (config.yaml)
- ✨ **Feature**: Strukturiertes Logging mit konfigurierbarem Level
- ✨ **Feature**: Graceful Shutdown (wartet auf laufende Jobs)
- ✨ **Feature**: Unit Tests (22 Tests, 100% Pass-Rate)
- 🔒 **Security**: Path Traversal Prevention
- 🔒 **Security**: Filename Sanitization mit Whitelist
- 🔒 **Security**: Job Timeout (180 Sekunden)
- 🔒 **Security**: Race Condition Fixes mit Thread-Locks
- 🐛 **Fix**: Job Error Handling (Jobs haengen nicht mehr)
- 📝 **Docs**: CLAUDE.md mit Entwicklungs-Guidelines
- 📝 **Docs**: README komplett ueberarbeitet

#### v1.1 (2025-01)
- Initial release mit Background-Threading
- META REFRESH fuer asynchrone Updates
- Code-Assistent, Resource-Generator, Q&A
- Shared Folder Integration
- ISO-8859-1 Encoding Support

## Hinweise

- Der Server ist nicht fuer den produktiven Einsatz gedacht
- Keine Authentifizierung implementiert (nur lokales Netz!)
- API Key sollte sicher aufbewahrt werden
- Firewall-Deaktivierung nur temporaer beim Start
- Logs koennen sensitive Informationen enthalten (in .gitignore)
- Tests vor jedem Deployment ausfuehren empfohlen
