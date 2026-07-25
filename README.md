# Claude Bridge Server v2.1

An HTTP server that makes Claude AI accessible for Classic Mac OS systems (MacOS 7.5 in Basilisk II) via native app or Netscape 3 browser.

## Overview

This server enables access to the Claude API from a vintage Mac with either:
- **Native Think C Application** (NEW in v2.1) - Fast, efficient, native Mac Toolbox UI
- **Netscape Navigator 3** - Browser-based interface with HTML 3.2

The server automatically detects the client type and responds appropriately (JSON for native app, HTML for browser).

**New in v2.1**: Native Think C 7.0 application with MacTCP networking, JSON API support, mode selection, preferences, and file saving

**New in v1.3**: English UI, Web Proxy with HTTPS-to-HTTP bridging, image optimization for vintage browsers, rate limiting for Wikipedia

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up API key
mkdir -p ~/.config/anthropic
echo 'sk-ant-...' > ~/.config/anthropic/api_key
chmod 600 ~/.config/anthropic/api_key

# 3. Start server
python3 claude_bridge.py --shared-folder ~/Desktop/Share

# 4. Open browser
# http://localhost:8080/
```

That's it! The server is running and ready for Netscape 3 or the native app.

## Client Options

### Option 1: Native Think C Application (Recommended)

A native Mac application built with Think C 7.0 that communicates directly with the server via MacTCP.

**Advantages over browser:**
- ✅ **Faster UI**: Instant response, no page reloads
- ✅ **Better Polling**: Event loop instead of META REFRESH flicker
- ✅ **One-Click Copy**: Direct clipboard access (no 3-step workaround)
- ✅ **Native Encoding**: MacRoman instead of ISO-8859-1 limitations
- ✅ **Save to File**: StandardFile dialog integration
- ✅ **Preferences**: Configurable server IP and port

**Setup:**
1. Compile the app with Think C 7.0 (see `ClassicClient/BUILD.txt`)
2. Configure MacTCP with network settings
3. Launch "Claude Assistant" application
4. Set server IP in Preferences
5. Start asking questions!

**Documentation:**
- `ClassicClient/README.txt` - User guide
- `ClassicClient/BUILD.txt` - Build instructions
- `CHANGES_NATIVE_CLIENT.txt` - Technical details

### Option 2: Netscape Navigator 3 (Classic)

Browser-based interface using HTML 3.2 and META REFRESH for polling.

**Setup:**
1. Open Netscape Navigator 3
2. Navigate to `http://[SERVER-IP]:8080/`
3. Use web forms to interact with Claude

**Good for:** Quick access without compiling, testing on modern browsers

## Features

### Main Functions:

1. **Code Assistant** - Write, analyze and debug Think C code
   - Specialized for Think C 7 on MacOS 7.5
   - Toolbox API knowledge
   - Handle-based memory management
   - Pascal string support

2. **Resource Generator** - Generate Rez source code
   - MENU, DLOG, DITL, WIND, ICON, etc.
   - Ready-to-compile Rez code

3. **Ask & Answer** - General Classic Mac programming questions
   - Toolbox questions
   - Debugging help
   - Architecture advice

4. **Claude Chat** - General AI assistant
   - Chat about anything, not just programming
   - Context-aware conversation history
   - Plain text export for easy copying

5. **Web Proxy** - Browse modern HTTPS websites in Netscape 3
   - Converts modern HTML to HTML 3.2
   - Removes JavaScript and CSS
   - Optimizes images for Classic Mac (GIF, 500px, 50KB, 32-64 colors)
   - Rate limiting to prevent Wikipedia blocks
   - Image caching (100 entries, 1 hour TTL)

### Technical Features:

- **Background Threading**: API calls run in background
- **META REFRESH**: Automatic page refresh while Claude works
- **ISO-8859-1 Encoding**: Compatible with Netscape "Western" character set
- **HTML 3.2**: Works with old browsers
- **Shared Folder**: Exchange files between Mac and server
- **Conversation History**: Last 20 questions/answers saved
- **Text Export**: Easy copying of Claude's answers

### New Features in v1.3:

- **English UI**: All interface elements translated to English
- **Web Proxy**: HTTPS-to-HTTP proxy for vintage browsers
- **Image Optimization**: Automatic conversion to GIF with size limits
- **Rate Limiting**: 2-second delay between image requests (prevents Wikipedia 429 errors)
- **Smart Retry**: Automatic retry on rate limit errors
- **Input Image Support**: Handles `<input type="image">` tags
- **Image Caching**: Reduces redundant fetches

## Installation

### Requirements

- Python 3.8 or newer (tested with 3.12)
- PyYAML (for config.yaml support)
- BeautifulSoup4 (for HTML parsing)
- Pillow (for image optimization)
- Anthropic API Key
- Basilisk II emulator with MacOS 7.5 and Netscape 3 (optional)

### Install Dependencies

```bash
pip install -r requirements.txt
```

or with uv (recommended):

```bash
uv pip install -r requirements.txt
```

Manual installation:
```bash
pip install PyYAML beautifulsoup4 Pillow
```

### Set Up API Key

Option 1 (recommended):
```bash
mkdir -p ~/.config/anthropic
echo 'sk-ant-...' > ~/.config/anthropic/api_key
chmod 600 ~/.config/anthropic/api_key
```

Option 2: Create .env file in project directory

Option 3: Set environment variable:
```bash
export ANTHROPIC_API_KEY='sk-ant-...'
```

## Usage

### Manual Start

```bash
python3 claude_bridge.py --port 8080 --host 0.0.0.0 --shared-folder ~/Desktop/Share
```

### With Start Script (macOS)

```bash
sudo ./start_bridge.sh
```

The script:
- Temporarily disables firewall
- Starts the server
- Re-enables firewall on exit

### Parameters

- `--port`: Port (default: 8080, overridable via config.yaml)
- `--host`: Host address (default: 0.0.0.0, overridable via config.yaml)
- `--shared-folder`: Path to shared folder for file exchange
- `--config`: Path to config file (default: config.yaml)

### Access

In browser (Netscape 3 on Classic Mac or modern):
```
http://[SERVER-IP]:8080/
```

## Web Proxy

The Web Proxy allows you to browse modern HTTPS websites in Netscape Navigator 3.

### How It Works

1. **HTML Conversion**: Modern HTML → HTML 3.2
   - Removes `<script>`, `<style>`, CSS
   - Converts `<div>` → `<p>`, removes `<span>`
   - Truncates large pages to 200KB

2. **Image Optimization**:
   - Downloads HTTPS images
   - Converts to GIF format (best Netscape 3 compatibility)
   - Resizes to max 500px width
   - Compresses to max 50KB
   - Uses 32-64 color adaptive palette
   - SVG → 1x1 transparent GIF placeholder

3. **Rate Limiting**:
   - 2-second delay between image requests to same domain
   - Prevents Wikipedia HTTP 429 errors
   - Automatic retry with 3-second wait on 429

4. **Link Rewriting**:
   - All links proxied through `/proxy?url=`
   - All images proxied through `/proxyimg?url=`
   - Handles both `<img>` and `<input type="image">` tags

### Recommended Sites

- Wikipedia (works well with rate limiting)
- Hacker News (text-heavy, fast)
- Reddit Old (simple layout)

### Known Limitations

- Some images may show placeholders due to rate limiting
- JavaScript-heavy sites won't work (no JS support)
- Maximum 200KB HTML per page
- 2-second delay makes image-heavy pages slow (~40 seconds for 20 images)

## Architecture

### Server Components

- **HTTP Server**: BaseHTTPRequestHandler with Threading
- **Unified Handler**: Routes requests to Claude Interface or Web Proxy
- **Claude Interface**:
  - Automatic client detection (User-Agent: "ClaudeAssistant" → JSON, else → HTML)
  - JSON API for native app (job_id, status, answer)
  - HTML templates for browser (HTML 3.2)
- **Job Queue**: Background processing of API calls
- **File Management**: Read/write in Shared Folder
- **Character Sanitization**: Unicode → ISO-8859-1/UTF-8 conversion
- **Web Proxy**: HTTPS fetching + HTML/image conversion
- **Image Cache**: LRU cache with 100 entries, 1 hour TTL
- **Rate Limiter**: Per-domain request tracking

### System Prompts

The server uses specialized system prompts:
- **SYSTEM_PROMPT_CODE**: Think C programming
- **SYSTEM_PROMPT_REZ**: Resource file generation
- **SYSTEM_PROMPT_GENERAL**: General Mac development
- **SYSTEM_PROMPT_CHAT**: General AI assistant

### Workflow

**Browser Client:**
1. User sends request via HTML form
2. Server creates background job
3. "Please wait" page with META REFRESH
4. Claude API call in background
5. Automatic redirect to result
6. Result with save and follow-up options

**Native Client:**
1. App sends HTTP POST with User-Agent: "ClaudeAssistant/1.0"
2. Server creates background job, returns JSON: `{"job_id": "abc123"}`
3. App polls GET /result/{job_id} every 2 seconds
4. Server returns `{"status": "working", "elapsed": N}` while processing
5. When done, server returns `{"status": "done", "answer": "...", "mode": "Code"}`
6. App displays answer in TextEdit control

### JSON API Reference

For native clients, set User-Agent header to include "ClaudeAssistant".

**Create Job:**
```http
POST /code (or /rez, /ask, /chat)
User-Agent: ClaudeAssistant/1.0 (Mac OS 7.5)
Content-Type: application/x-www-form-urlencoded

prompt=<url-encoded-text>
```

Response:
```json
{"job_id": "abc123"}
```

**Poll Status:**
```http
GET /result/{job_id}
User-Agent: ClaudeAssistant/1.0 (Mac OS 7.5)
```

Response (working):
```json
{"status": "working", "elapsed": 15}
```

Response (done):
```json
{
  "status": "done",
  "mode": "Code",
  "answer": "Here's the answer..."
}
```

Response (error):
```json
{"error": "Job not found"}
```

See `CHANGES_NATIVE_CLIENT.txt` for complete API specification.

## Technical Details

### Character Encoding

- **Input**: ISO-8859-1 from browser
- **Processing**: Unicode internally
- **Output**: ISO-8859-1 for Netscape
- **Umlauts**: ä, ö, ü, ß handled correctly
- **Special chars**: Automatic replacement (– → -, " → ")

### Browser Compatibility

- HTML 3.2 compliant (no CSS, no JavaScript)
- TABLE-based layout
- META REFRESH for updates
- TEXTAREA instead of contenteditable
- Simple forms without AJAX

### API Usage

- Model: claude-sonnet-4-20250514
- Max Tokens: 4096
- Timeout: 120 seconds
- Error handling with meaningful messages

## Configuration

### Configuration File (config.yaml)

All settings can be configured via config.yaml.

Example `config.yaml`:

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

**Note**: config.yaml is optional. Without config file, default values are used.

### Command-Line Parameters Override Config

Command-line parameters take precedence over config.yaml:

```bash
python3 claude_bridge.py --port 9090 --config my_config.yaml
# Port 9090 will be used, even if config.yaml says otherwise
```

### Logging

Structured logging with configurable level.

Log levels:
- `DEBUG`: All details including path validation, rate limiting
- `INFO`: Standard operation, job lifecycle (recommended)
- `WARNING`: Warnings (e.g. API key missing, rate limits hit)
- `ERROR`: Errors during job execution

Example log output:
```
2026-04-01 18:08:43 [WARNING] Rate limited (429) for https://upload.wikimedia.org/..., waiting 3s and retrying...
2026-04-01 18:08:47 [INFO] Retry successful after 429: https://upload.wikimedia.org/...
2026-04-01 18:08:47 [INFO] GET /proxyimg?url=https://upload.wikimedia.org/... HTTP/1.0
```

## Security

### Security Improvements in v1.2

The server was hardened with several security features:

1. **Path Traversal Prevention**
   - `validate_safe_path()` function validates all file paths
   - Prevents `../` attacks
   - All file operations protected

2. **Filename Sanitization**
   - Whitelist for filenames: only `a-zA-Z0-9._-`
   - Prevents hidden files (`.`)
   - Replaces unsafe characters

3. **Job Timeout**
   - Automatic timeout after 180 seconds (configurable)
   - Prevents hanging jobs
   - User-friendly timeout message

4. **Race Condition Fixes**
   - Thread locks on all job operations
   - Double-check before delete
   - No crashes on concurrent access

5. **Error Handling**
   - try/except around all critical operations
   - Jobs marked as "error" instead of forever "working"
   - Meaningful error messages

### Security Limitations

**Important**: This server is NOT intended for production:
- ❌ No authentication
- ❌ No HTTPS (HTTP only)
- ❌ No rate limiting (except Web Proxy)
- ❌ Direct filesystem access via Shared Folder
- ❌ API key in environment/config

**Usage**: Only in trusted networks (local network / emulator).

## Testing

### Run Unit Tests

```bash
python3 test_claude_bridge.py
```

**Test Coverage** (22 Tests):
- ✅ Path Validation (6 Tests)
- ✅ Character Sanitization (6 Tests)
- ✅ Filename Validation (4 Tests)
- ✅ Config Loading (2 Tests)
- ✅ File Management (4 Tests)

All tests have 100% pass rate.

## Development

### File Structure

```
AppleBridge/
├── claude_bridge.py            # Main server entry point
├── applebridge/                # Server package (modular architecture)
│   ├── config.py               # Configuration management
│   ├── encoding.py             # Character encoding utilities
│   ├── claude/                 # Claude Interface module
│   │   ├── server.py           # HTTP handlers (HTML + JSON API)
│   │   ├── jobs.py             # Job queue and processing
│   │   ├── prompts.py          # System prompts
│   │   ├── templates.py        # HTML templates
│   │   ├── history.py          # Conversation history
│   │   └── files.py            # Shared folder management
│   └── proxy/                  # Web Proxy module
│       ├── server.py           # Proxy HTTP handlers
│       ├── fetcher.py          # HTTPS fetching
│       ├── simplifier.py       # HTML simplification
│       └── images.py           # Image optimization
├── ClassicClient/              # Native Think C 7.0 application
│   ├── main.c                  # Event loop, handlers
│   ├── ui.c                    # Window, menu, drawing
│   ├── network.c               # MacTCP HTTP client
│   ├── prefs.c                 # Preferences management
│   ├── globals.h               # Global definitions
│   ├── http.h                  # HTTP API definitions
│   ├── ClaudeAssistant.r       # Rez resources
│   ├── README.txt              # User documentation
│   └── BUILD.txt               # Build instructions
├── config.yaml                 # Server configuration
├── requirements.txt            # Python dependencies
├── start_bridge.sh             # Start script (macOS)
├── CLAUDE.md                   # Development guidelines
├── CHANGES_NATIVE_CLIENT.txt   # v2.1 changes
└── README.md                   # This file
```

### Development Guidelines

See `CLAUDE.md` for important notes:
- ⚠️ **CRITICAL**: DO NOT change ISO-8859-1 encoding!
- Think C compiler limitations
- Netscape 3 HTML 3.2 compatibility
- System prompt guidelines

### Extensions

Possible extensions:
- More programming languages (Pascal, Assembly)
- Authentication (Basic Auth, Token)
- HTTPS support
- Session management
- Multi-user support
- Export in various formats
- Better proxy caching strategies

## License

No license specified.

## Author

Peter Forster

## Version

**Current Version**: 2.1 (April 2026)

### Changelog

#### v2.1 (2026-04-02)
- ✨ **Feature**: Native Think C 7.0 application for Classic Mac OS 7.5
  - Full Mac Toolbox UI with TextEdit controls
  - MacTCP HTTP client implementation
  - Asynchronous job polling via event loop (no META REFRESH flicker!)
  - One-click clipboard copy
  - StandardFile dialog for saving
  - Preferences dialog with persistence
  - Mode selection (Code/Rez/Ask/Chat)
- ✨ **Feature**: JSON API support in server
  - Automatic client detection via User-Agent header
  - JSON responses for native app: `{"job_id": "..."}`, `{"status": "done", "answer": "..."}`
  - HTML responses for browser (unchanged, 100% backwards compatible)
- 📁 **New**: Complete ClassicClient/ directory with source code
  - main.c, ui.c, network.c, prefs.c (ca. 2000 lines)
  - globals.h, http.h
  - ClaudeAssistant.r (Rez resources)
  - README.txt, BUILD.txt
- 📝 **Docs**: CHANGES_NATIVE_CLIENT.txt with technical details
- 🏗️ **Refactor**: Server now modular (applebridge/ package)

#### v1.3 (2026-04-01)
- ✨ **Feature**: English UI (all German text translated)
- ✨ **Feature**: Web Proxy with HTTPS-to-HTTP bridging
- ✨ **Feature**: Image optimization for vintage browsers (GIF conversion)
- ✨ **Feature**: Rate limiting (2s delay between image requests)
- ✨ **Feature**: Smart retry on HTTP 429 errors
- ✨ **Feature**: Image caching (100 entries, 1 hour TTL)
- ✨ **Feature**: Claude Chat with conversation context
- 🐛 **Fix**: `<input type="image">` URL rewriting
- 🐛 **Fix**: Text wrapping in Netscape 3 (72 char line breaks)
- 📝 **Docs**: README translated to English

#### v1.2 (2025-01-15)
- ✨ **Feature**: Configuration file support (config.yaml)
- ✨ **Feature**: Structured logging with configurable level
- ✨ **Feature**: Graceful shutdown (waits for running jobs)
- ✨ **Feature**: Unit tests (22 tests, 100% pass rate)
- 🔒 **Security**: Path traversal prevention
- 🔒 **Security**: Filename sanitization with whitelist
- 🔒 **Security**: Job timeout (180 seconds)
- 🔒 **Security**: Race condition fixes with thread locks
- 🐛 **Fix**: Job error handling (jobs don't hang anymore)
- 📝 **Docs**: CLAUDE.md with development guidelines
- 📝 **Docs**: README completely revised

#### v1.1 (2025-01)
- Initial release with background threading
- META REFRESH for asynchronous updates
- Code Assistant, Resource Generator, Q&A
- Shared Folder integration
- ISO-8859-1 encoding support

## Notes

- Server is not intended for production use
- No authentication implemented (local network only!)
- API key should be stored securely
- Firewall deactivation only temporary during start
- Logs may contain sensitive information (in .gitignore)
- Running tests before each deployment recommended
- Web Proxy works best with text-heavy sites
- Wikipedia requires 2s image delay to avoid rate limits
