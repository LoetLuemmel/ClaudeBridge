# Claude Bridge Server

Ein HTTP-Server, der Claude AI fuer Classic Mac OS Systeme (MacOS 7.5 in Basilisk II) mit Netscape 3 zugaenglich macht.

## Ueberblick

Dieser Server ermoeglicht es, von einem Vintage Mac mit Netscape Navigator 3 auf die Claude API zuzugreifen. Der Server ist speziell fuer die Einschraenkungen alter Browser optimiert (HTML 3.2, ISO-8859-1 Encoding, META REFRESH fuer asynchrone Updates).

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

## Installation

### Voraussetzungen

- Python 3.12 oder neuer
- Anthropic API Key
- Basilisk II Emulator mit MacOS 7.5 und Netscape 3 (optional)

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

- `--port`: Port (Standard: 8080)
- `--host`: Host-Adresse (Standard: 0.0.0.0)
- `--shared-folder`: Pfad zum Shared Folder fuer Dateienaustausch

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

### Anpassbare Konstanten (claude_bridge.py)

```python
CLAUDE_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096
REFRESH_SECONDS = 3  # META REFRESH Intervall
MAX_HISTORY = 20     # Anzahl gespeicherter Konversationen
```

### Start-Script (start_bridge.sh)

```bash
PYTHON="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
SHARED="/Users/pitforster/Desktop/Share"
HOST="192.168.3.154"
PORT=8080
```

## Entwicklung

### Dateistruktur

```
AppleBridge/
├── claude_bridge.py    # Haupt-Server
├── start_bridge.sh     # Start-Script (macOS)
└── README.md           # Diese Datei
```

### Erweiterungen

Moegliche Erweiterungen:
- Weitere Programmiersprachen (Pascal, Assembly)
- Code-Syntax-Highlighting
- Session-Management
- Multi-User Support
- Export in verschiedene Formate

## Lizenz

Keine Lizenz angegeben.

## Autor

Peter Forster

## Version

1.1 (2025)

## Hinweise

- Der Server ist nicht fuer den produktiven Einsatz gedacht
- Keine Authentifizierung implementiert
- API Key sollte sicher aufbewahrt werden
- Firewall-Deaktivierung nur temporaer beim Start
