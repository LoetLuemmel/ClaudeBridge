Claude Assistant for Classic Mac OS 7.5
========================================

Native Think C 7.0 Application

OVERVIEW
--------
This is a native Mac application that connects to the AppleBridge server
to provide Claude AI assistance directly on Classic Mac OS 7.5.

Features:
- Native Mac Toolbox UI with TextEdit controls
- Direct HTTP communication with AppleBridge server
- No browser required - faster and more efficient
- One-click copy to clipboard
- Event-driven asynchronous polling (no META REFRESH flicker)

REQUIREMENTS
------------
- Mac OS 7.5 or later
- MacTCP or Open Transport installed and configured
- Think C 7.0 (for compilation)
- AppleBridge server running on network

BUILDING
--------
1. Open Think C 7.0
2. Create new project: "ClaudeAssistant.π"
3. Add source files to project:
   - main.c
   - ui.c
   - network.c
4. Add library: MacTCP
5. Set project settings:
   - 68k or PowerPC code generation
   - Preferred memory: 512 KB
   - Minimum memory: 256 KB
6. Compile Rez file:
   Rez ClaudeAssistant.r -o ClaudeAssistant
7. Build project:
   Project > Build Application

CONFIGURATION
-------------
Default server settings:
- IP: 127.0.0.1 (localhost)
- Port: 8080

To change server settings:
1. Edit globals.h
2. Change kDefaultServerIP and kDefaultServerPort
3. Rebuild application

Or use Preferences dialog (Phase 3 feature, coming soon).

USAGE
-----
1. Start AppleBridge server on network
2. Launch Claude Assistant application
3. Enter question or code in "Your Question/Code" field
4. Click "Send" button
5. Wait for Claude's response (status bar shows progress)
6. Response appears in "Claude's Answer" field
7. Click "Copy" to copy answer to clipboard
8. Click "Clear" to start new question

NETWORK SETUP
-------------
MacTCP Configuration:
1. Open MacTCP Control Panel
2. Configure IP address (static or DHCP)
3. Test with Ping or other network tool
4. Ensure AppleBridge server is reachable

Firewall:
- Allow incoming connections on port 8080 (or configured port)

TROUBLESHOOTING
---------------
"Network initialization failed"
  → Check MacTCP is installed and configured
  → Check network cable is connected

"Failed to send request"
  → Check server IP address is correct
  → Check server is running (port 8080)
  → Check firewall allows connection

"Request timed out"
  → Server may be slow or unresponsive
  → Check network latency
  → Wait times are normal for complex questions

"Error checking status"
  → Server connection lost during polling
  → Check network stability

ARCHITECTURE
------------
Files:
- main.c         Event loop, initialization, button handlers
- ui.c           Window, menu, TextEdit, drawing
- network.c      HTTP client, MacTCP interface, job polling
- globals.h      Global definitions and constants
- http.h         HTTP client API definitions
- ClaudeAssistant.r  Rez resources (menus, windows, dialogs)

Flow:
1. User enters text → gInputTE
2. Send button → DoSendToServer()
3. HTTP POST /code with prompt → SendJobRequest()
4. Server returns job_id
5. Poll /result/{job_id} → CheckJobStatus()
6. When done, display answer → gOutputTE

DEVELOPMENT STATUS
------------------
✅ Phase 1: Basic UI Framework (COMPLETE)
   - Window with 2 TextEdit controls
   - Menu bar (Apple, File, Edit, Code)
   - Button handling
   - Event loop

✅ Phase 2: HTTP Client (COMPLETE)
   - MacTCP integration
   - HTTP GET/POST requests
   - Response parsing
   - Job polling with timeout

⏳ Phase 3: Advanced Features (PLANNED)
   - Save to file (StandardFile)
   - Preferences dialog
   - Multiple modes (Code, Rez, Ask, Chat)

SERVER INTEGRATION
------------------
This client works with AppleBridge server 2.0 or later.

Required endpoints:
- POST /code    → Send job request, returns {"job_id": "..."}
- GET /result/{job_id} → Poll result, returns {"status": "done", "answer": "..."}

Optional endpoints (Phase 3):
- POST /rez     → Resource generation
- POST /ask     → General questions
- POST /chat    → Chat mode

KNOWN LIMITATIONS
-----------------
- No DNS resolution (IP addresses only)
- No HTTPS support (HTTP only)
- No syntax highlighting (plain text)
- Maximum response size: 32 KB
- No threading (event-loop polling)
- No progress bar (text status only)

FUTURE ENHANCEMENTS
-------------------
- DNS resolution via MacTCP DNR
- Mode selection (Code/Rez/Ask/Chat)
- Save to file with StandardFile
- Preferences dialog
- About box with version info
- Better error messages
- Progress indicator

VERSION HISTORY
---------------
1.0 (2025-04-02)
- Initial release
- Basic UI framework
- HTTP client with MacTCP
- Job polling
- Clipboard copy

LICENSE
-------
Part of AppleBridge project.

CONTACT
-------
For issues or questions, see AppleBridge documentation.
