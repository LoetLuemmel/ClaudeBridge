#!/usr/bin/env python3
"""
Claude Bridge Server 1.2 for Classic Mac OS
=============================================
Uses background threading + META REFRESH to avoid Netscape timeouts.

Features (v1.2):
- Configuration file support (config.yaml)
- Structured logging to file and console
- Security fixes (path traversal prevention, job timeouts)
- Graceful error handling

Usage:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python3 claude_bridge.py [--port 8080] [--host 0.0.0.0] [--config config.yaml]
"""

import argparse
import html
import json
import os
import time
import threading
import unicodedata
import logging
import yaml
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from pathlib import Path

# --- Configuration ---
# Default configuration (can be overridden by config.yaml)
CONFIG = {
    "server": {"host": "0.0.0.0", "port": 8080},
    "claude": {"model": "claude-sonnet-4-20250514", "max_tokens": 4096, "timeout": 120},
    "jobs": {"timeout": 180, "max_history": 10, "refresh_interval": 3},
    "files": {"shared_folder": None},
    "history": {"max_entries": 20},
    "logging": {"level": "INFO", "file": "claude_bridge.log", "console": True}
}

def load_config(config_file="config.yaml"):
    """Load configuration from YAML file if it exists."""
    global CONFIG
    config_path = Path(__file__).parent / config_file
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    # Deep merge user config into default config
                    for section, values in user_config.items():
                        if section in CONFIG and isinstance(values, dict):
                            CONFIG[section].update(values)
                        else:
                            CONFIG[section] = values
                    logging.info(f"Configuration loaded from {config_path}")
        except Exception as e:
            logging.warning(f"Could not load config file: {e}")
    else:
        logging.info("No config.yaml found, using defaults")

# Legacy global variables for backward compatibility
CLAUDE_MODEL = CONFIG["claude"]["model"]
MAX_TOKENS = CONFIG["claude"]["max_tokens"]
SHARED_FOLDER = CONFIG["files"]["shared_folder"]
REFRESH_SECONDS = CONFIG["jobs"]["refresh_interval"]
JOB_TIMEOUT_SECONDS = CONFIG["jobs"]["timeout"]

def setup_logging():
    """Setup logging based on configuration."""
    log_level = getattr(logging, CONFIG["logging"]["level"], logging.INFO)
    log_format = '%(asctime)s [%(levelname)s] %(message)s'
    log_date_format = '%Y-%m-%d %H:%M:%S'

    handlers = []

    # Console handler
    if CONFIG["logging"]["console"]:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_format, log_date_format))
        handlers.append(console_handler)

    # File handler
    if CONFIG["logging"]["file"]:
        try:
            file_handler = logging.FileHandler(CONFIG["logging"]["file"], encoding='utf-8')
            file_handler.setFormatter(logging.Formatter(log_format, log_date_format))
            handlers.append(file_handler)
        except Exception as e:
            print(f"Warning: Could not setup file logging: {e}")

    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        force=True
    )

# --- Job Queue ---
jobs = {}
job_counter = 0
job_lock = threading.Lock()
shutdown_event = threading.Event()  # Signal for graceful shutdown

def create_job(mode, prompt, system_prompt):
    global job_counter
    with job_lock:
        job_counter += 1
        job_id = str(job_counter)
    jobs[job_id] = {
        "status": "working",
        "mode": mode,
        "prompt": prompt[:200],
        "answer": None,
        "started": time.time(),
        "error": None
    }
    logging.info(f"Job {job_id} created: {mode} - {prompt[:50]}...")

    def run():
        try:
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            logging.debug(f"Job {job_id}: Calling Claude API...")
            answer = call_claude(api_key, prompt, system_prompt)
            with job_lock:
                if job_id in jobs:  # Job might have been cleaned up
                    jobs[job_id]["answer"] = answer
                    jobs[job_id]["status"] = "done"
                    add_to_history(mode, jobs[job_id]["prompt"], answer)
                    elapsed = time.time() - jobs[job_id]["started"]
                    logging.info(f"Job {job_id} completed in {elapsed:.1f}s")
        except Exception as e:
            # Ensure job is marked as failed even if something goes wrong
            logging.error(f"Job {job_id} failed: {str(e)}")
            with job_lock:
                if job_id in jobs:
                    jobs[job_id]["answer"] = f"[Interner Fehler]: {str(e)}"
                    jobs[job_id]["status"] = "error"
                    jobs[job_id]["error"] = str(e)
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return job_id

# --- Claude API ---
def call_claude(api_key, prompt, system_prompt=""):
    import urllib.request
    import urllib.error
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01"
    }
    body = {
        "model": CLAUDE_MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}]
    }
    if system_prompt:
        body["system"] = system_prompt
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=data, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["content"][0]["text"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        return f"[API Error {e.code}]: {error_body}"
    except Exception as e:
        return f"[Error]: {str(e)}"

# --- System Prompts ---
SYSTEM_PROMPT_CODE = (
    "Du bist ein Experte fuer Classic Macintosh Programmierung mit Think C 7 "
    "unter MacOS 7.5. Du schreibst Code der mit Think C kompatibel ist. "
    "Beachte: Think C unterstuetzt kein volles ANSI C89. "
    "Verwende Toolbox-Aufrufe, Pascal-Strings, Handle-basierte Speicherverwaltung. "
    "Antworte mit gut kommentiertem, kompilierbarem Code. "
    "Halte Erklaerungen kurz und praezise.")

SYSTEM_PROMPT_REZ = (
    "Du bist ein Experte fuer Classic Macintosh Resource-Dateien im Rez-Format. "
    "Du generierst gueltigen Rez-Quelltext fuer MacOS 7.5 Ressourcen wie "
    "MENU, DLOG, DITL, WIND, ALRT, STR#, ICON, CNTL etc. "
    "Gib nur den Rez-Code aus, mit Kommentaren. Kein zusaetzlicher Text.")

SYSTEM_PROMPT_GENERAL = (
    "Du bist ein Assistent fuer Classic Macintosh Entwicklung mit Think C 7 "
    "unter MacOS 7.5 in Basilisk II. Du hilfst bei Toolbox-Fragen, "
    "Debugging, Architektur und allgemeinen Programmierfragen. "
    "Halte Antworten kompakt - der Benutzer liest sie in Netscape 3.")

# --- History ---
conversation_history = []
MAX_HISTORY = 20

def add_to_history(mode, question, answer):
    conversation_history.append({
        "time": time.strftime("%H:%M:%S"),
        "mode": mode,
        "question": question[:200],
        "answer": answer[:500]
    })
    if len(conversation_history) > MAX_HISTORY:
        conversation_history.pop(0)

# --- File Management ---
def validate_safe_path(base_path, user_path):
    """Validate that user_path stays within base_path (prevent path traversal).
    Returns resolved path if safe, None otherwise."""
    try:
        base = Path(base_path).resolve()
        target = (base / user_path).resolve()
        # Check if target is within base (prevents ../ attacks)
        target.relative_to(base)
        logging.debug(f"Path validation OK: {user_path}")
        return target
    except (ValueError, RuntimeError) as e:
        logging.warning(f"Path traversal attempt blocked: {user_path} (from base: {base_path})")
        return None

def list_shared_files(subfolder=""):
    if not SHARED_FOLDER:
        return []
    target = validate_safe_path(SHARED_FOLDER, subfolder)
    if not target or not target.exists():
        return []
    files = []
    try:
        for f in sorted(target.iterdir()):
            if f.name.startswith("."):
                continue
            files.append({
                "name": f.name,
                "is_dir": f.is_dir(),
                "size": f.stat().st_size if f.is_file() else 0
            })
    except (PermissionError, OSError):
        pass
    return files

def read_shared_file(filename):
    if not SHARED_FOLDER:
        return None
    filepath = validate_safe_path(SHARED_FOLDER, filename)
    if not filepath or not filepath.exists() or not filepath.is_file():
        return None
    try:
        return filepath.read_text(encoding="mac_roman", errors="replace")
    except:
        try:
            return filepath.read_text(encoding="utf-8", errors="replace")
        except:
            return None

def save_shared_file(filename, content):
    if not SHARED_FOLDER:
        return False
    filepath = validate_safe_path(SHARED_FOLDER, filename)
    if not filepath:
        return False
    try:
        filepath.write_text(content, encoding="utf-8")
        return True
    except:
        return False

# --- Sanitize for ISO-8859-1 (Netscape "Western" on Classic Mac) ---
def sanitize(text):
    """Convert Unicode to ISO-8859-1 safe text.
    Netscape 'Western' = ISO-8859-1, the Mac Script Manager then
    converts to MacRoman glyphs for display.
    Umlauts (ä=0xE4, ö=0xF6, ü=0xFC, ß=0xDF) exist in ISO-8859-1."""
    # Step 1: NFC normalize (compose u + combining diaeresis -> ü)
    text = unicodedata.normalize('NFC', text)
    # Step 2: Replace Unicode chars that don't exist in ISO-8859-1
    replacements = {
        '\u2014': '-',    # em dash
        '\u2013': '-',    # en dash
        '\u2018': "'",    # left single quote
        '\u2019': "'",    # right single quote
        '\u201c': '"',    # left double quote
        '\u201d': '"',    # right double quote
        '\u2026': '...',  # ellipsis
        '\u2022': '*',    # bullet
        '\u2003': ' ',    # em space
        '\u2002': ' ',    # en space
        '\u200b': '',     # zero width space
        '\u2192': '->',   # right arrow
        '\u2190': '<-',   # left arrow
    }
    for char, repl in replacements.items():
        text = text.replace(char, repl)
    # Step 3: Drop anything that still can't be encoded in ISO-8859-1
    result = []
    for c in text:
        try:
            c.encode('iso-8859-1')
            result.append(c)
        except UnicodeEncodeError:
            result.append('?')
    return ''.join(result)

# --- HTML 3.2 Templates ---

def html_page(title, body, back=True, refresh_url=None, refresh_sec=None):
    nav = ""
    if back:
        nav = """
<TABLE WIDTH="100%" BGCOLOR="#999999" CELLPADDING="4" CELLSPACING="0">
<TR>
<TD><FONT SIZE="-1">
<A HREF="/"><B>Start</B></A> |
<A HREF="/code">Code</A> |
<A HREF="/rez">Resources</A> |
<A HREF="/ask">Frage</A> |
<A HREF="/files">Dateien</A> |
<A HREF="/history">Verlauf</A>
</FONT></TD>
</TR>
</TABLE>"""
    refresh_tag = ""
    if refresh_url and refresh_sec:
        refresh_tag = f'<META HTTP-EQUIV="Refresh" CONTENT="{refresh_sec};URL={refresh_url}">'
    return f"""\
<HTML>
<HEAD><TITLE>{title} - Claude Bridge</TITLE>
{refresh_tag}
</HEAD>
<BODY BGCOLOR="#EEEEEE" TEXT="#000000" LINK="#0000CC" VLINK="#660099">
<TABLE WIDTH="100%" BGCOLOR="#333366" CELLPADDING="8" CELLSPACING="0">
<TR><TD><FONT SIZE="+2" COLOR="#FFFFFF"><B>{title}</B></FONT></TD>
<TD ALIGN="RIGHT"><FONT SIZE="-1" COLOR="#CCCCCC">Claude Bridge 1.2</FONT></TD></TR>
</TABLE>
{nav}
{body}
</BODY>
</HTML>"""

def page_index():
    return html_page("Claude Bridge fuer Classic Mac", """
<BR>
<CENTER>
<TABLE WIDTH="80%" CELLPADDING="12" CELLSPACING="4">
<TR><TD BGCOLOR="#FFFFFF" VALIGN="TOP">
<FONT SIZE="+1"><B><A HREF="/code">[C] Code-Assistent</A></B></FONT><BR>
Think C Quellcode schreiben, erklaeren und debuggen lassen.
</TD></TR>
<TR><TD BGCOLOR="#FFFFFF" VALIGN="TOP">
<FONT SIZE="+1"><B><A HREF="/rez">[R] Resource-Generator</A></B></FONT><BR>
Rez-Quelltext fuer MENU, DLOG, DITL, WIND, ICON generieren.
</TD></TR>
<TR><TD BGCOLOR="#FFFFFF" VALIGN="TOP">
<FONT SIZE="+1"><B><A HREF="/ask">[?] Frage &amp; Antwort</A></B></FONT><BR>
Allgemeine Fragen zu Classic Mac Programmierung.
</TD></TR>
<TR><TD BGCOLOR="#FFFFFF" VALIGN="TOP">
<FONT SIZE="+1"><B><A HREF="/files">[F] Shared Folder</A></B></FONT><BR>
Dateien im Shared Folder anzeigen und an Claude senden.
</TD></TR>
<TR><TD BGCOLOR="#FFFFFF" VALIGN="TOP">
<FONT SIZE="+1"><B><A HREF="/history">[V] Verlauf</A></B></FONT><BR>
Letzte Fragen und Antworten anzeigen.
</TD></TR>
</TABLE>
</CENTER>
""", back=False)

def page_waiting(job_id, mode):
    elapsed = int(time.time() - jobs[job_id]["started"])
    return html_page(f"{mode} - Claude denkt nach...", f"""
<BR>
<CENTER>
<TABLE WIDTH="60%" BGCOLOR="#FFFFFF" CELLPADDING="20" CELLSPACING="0" BORDER="1">
<TR><TD ALIGN="CENTER">
<FONT SIZE="+1"><B>Claude arbeitet...</B></FONT>
<P>Deine Anfrage wird verarbeitet.<BR>
Diese Seite aktualisiert sich automatisch.</P>
<P><FONT SIZE="-1">Bisherige Wartezeit: {elapsed} Sekunden</FONT></P>
</TD></TR>
</TABLE>
</CENTER>
""", refresh_url=f"/result/{job_id}", refresh_sec=REFRESH_SECONDS)

def page_code():
    return html_page("Code-Assistent", """
<P>Beschreibe was du brauchst, oder fuege Code ein den Claude analysieren soll.</P>
<FORM METHOD="POST" ACTION="/code">
<P><B>Deine Frage / Aufgabe:</B><BR>
<TEXTAREA NAME="prompt" ROWS="8" COLS="72" WRAP="virtual"></TEXTAREA></P>
<P><B>Vorhandener Code (optional):</B><BR>
<TEXTAREA NAME="code" ROWS="12" COLS="72" WRAP="off"></TEXTAREA></P>
<P><INPUT TYPE="SUBMIT" VALUE=" An Claude senden ">
<INPUT TYPE="RESET" VALUE=" Loeschen "></P>
</FORM>
""")

def page_code_result(question, answer, job_id=None):
    escaped = html.escape(sanitize(answer))
    q_escaped = html.escape(sanitize(question))
    save_val = html.escape(sanitize(answer), quote=True)
    text_link = f'<A HREF="/text/{job_id}"><B>[ Nur Text - zum Kopieren ]</B></A>' if job_id else ""
    return html_page("Code-Assistent -- Ergebnis", f"""
<P><B>Deine Frage:</B></P>
<BLOCKQUOTE>{q_escaped}</BLOCKQUOTE>
<HR>
<P><B>Claude's Antwort:</B> {text_link}</P>
<PRE>{escaped}</PRE>
<HR>
<FORM METHOD="POST" ACTION="/save">
<INPUT TYPE="HIDDEN" NAME="content" VALUE="{save_val}">
<B>Speichern als:</B>
<INPUT TYPE="TEXT" NAME="filename" SIZE="25" VALUE="claude_output.c">
<INPUT TYPE="SUBMIT" VALUE=" Speichern ">
</FORM>
<HR>
<FORM METHOD="POST" ACTION="/code">
<P><B>Nachfrage:</B><BR>
<TEXTAREA NAME="prompt" ROWS="4" COLS="72" WRAP="virtual"></TEXTAREA></P>
<INPUT TYPE="HIDDEN" NAME="code" VALUE="">
<P><INPUT TYPE="SUBMIT" VALUE=" Nachfragen "></P>
</FORM>
""")

def page_rez():
    return html_page("Resource-Generator", """
<P>Beschreibe die Resources die du brauchst.</P>
<FORM METHOD="POST" ACTION="/rez">
<P><B>Was fuer Resources brauchst du?</B><BR>
<TEXTAREA NAME="prompt" ROWS="6" COLS="72" WRAP="virtual"></TEXTAREA></P>
<P><B>Resource-Typen (optional):</B><BR>
<INPUT TYPE="TEXT" NAME="types" SIZE="60" VALUE="MENU, DLOG, DITL"></P>
<P><INPUT TYPE="SUBMIT" VALUE=" Rez generieren ">
<INPUT TYPE="RESET" VALUE=" Loeschen "></P>
</FORM>
""")

def page_rez_result(question, answer, job_id=None):
    escaped = html.escape(sanitize(answer))
    save_val = html.escape(sanitize(answer), quote=True)
    text_link = f'<A HREF="/text/{job_id}"><B>[ Nur Text - zum Kopieren ]</B></A>' if job_id else ""
    save_section = ""
    if SHARED_FOLDER:
        save_section = f"""
<HR>
<FORM METHOD="POST" ACTION="/save">
<INPUT TYPE="HIDDEN" NAME="content" VALUE="{save_val}">
<B>Speichern als:</B>
<INPUT TYPE="TEXT" NAME="filename" SIZE="25" VALUE="resources.r">
<INPUT TYPE="SUBMIT" VALUE=" Speichern ">
</FORM>"""
    return html_page("Resource-Generator -- Ergebnis", f"""
<P><B>Deine Beschreibung:</B></P>
<BLOCKQUOTE>{html.escape(sanitize(question))}</BLOCKQUOTE>
<HR>
<P><B>Rez-Quelltext:</B> {text_link}</P>
<PRE>{escaped}</PRE>
{save_section}
<HR>
<P><A HREF="/rez">Neue Resources generieren</A></P>
""")

def page_ask():
    return html_page("Frage &amp; Antwort", """
<P>Stelle eine Frage zur Classic Mac Programmierung.</P>
<FORM METHOD="POST" ACTION="/ask">
<P><B>Deine Frage:</B><BR>
<TEXTAREA NAME="prompt" ROWS="6" COLS="72" WRAP="virtual"></TEXTAREA></P>
<P><INPUT TYPE="SUBMIT" VALUE=" Fragen ">
<INPUT TYPE="RESET" VALUE=" Loeschen "></P>
</FORM>
""")

def page_ask_result(question, answer, job_id=None):
    escaped = html.escape(sanitize(answer))
    text_link = f'<A HREF="/text/{job_id}"><B>[ Nur Text - zum Kopieren ]</B></A>' if job_id else ""
    return html_page("Frage &amp; Antwort -- Ergebnis", f"""
<P><B>Deine Frage:</B></P>
<BLOCKQUOTE>{html.escape(sanitize(question))}</BLOCKQUOTE>
<HR>
<P><B>Antwort:</B> {text_link}</P>
<PRE>{escaped}</PRE>
<HR>
<FORM METHOD="POST" ACTION="/ask">
<P><B>Nachfrage:</B><BR>
<TEXTAREA NAME="prompt" ROWS="4" COLS="72" WRAP="virtual"></TEXTAREA></P>
<P><INPUT TYPE="SUBMIT" VALUE=" Nachfragen "></P>
</FORM>
""")

def page_files(subfolder=""):
    files = list_shared_files(subfolder)
    if not SHARED_FOLDER:
        content = "<P><I>Kein Shared Folder konfiguriert.</I></P>"
    elif not files:
        content = "<P><I>Keine Dateien gefunden.</I></P>"
    else:
        rows = ""
        for f in files:
            name = f["name"]
            if f["is_dir"]:
                sub = subfolder + "/" + name if subfolder else name
                link = f'<A HREF="/files?sub={html.escape(sub)}">{html.escape(name)}/</A>'
                size = "[Ordner]"
            else:
                sub = subfolder + "/" + name if subfolder else name
                link = f'<A HREF="/readfile?name={html.escape(sub)}">{html.escape(name)}</A>'
                size = f'{f["size"]:,} Bytes'
            rows += f"<TR><TD>{link}</TD><TD ALIGN='RIGHT'>{size}</TD></TR>\n"
        content = f"""
<TABLE BORDER="1" CELLPADDING="4" CELLSPACING="0" WIDTH="80%">
<TR BGCOLOR="#CCCCCC"><TH ALIGN="LEFT">Datei</TH><TH ALIGN="RIGHT">Groesse</TH></TR>
{rows}
</TABLE>"""
    return html_page("Shared Folder", f"""
<P><B>Pfad:</B> <CODE>{html.escape(SHARED_FOLDER or '(nicht gesetzt)')}</CODE>
{(' / ' + html.escape(subfolder)) if subfolder else ''}</P>
{content}
""")

def page_readfile(filename):
    content = read_shared_file(filename)
    if content is None:
        return html_page("Datei nicht gefunden",
            f"<P>Datei <CODE>{html.escape(filename)}</CODE> nicht gefunden.</P>")
    escaped = html.escape(sanitize(content))
    content_val = html.escape(sanitize(content), quote=True)
    return html_page(f"Datei: {filename}", f"""
<PRE>{escaped}</PRE>
<HR>
<P><B>Claude fragen zu dieser Datei:</B></P>
<FORM METHOD="POST" ACTION="/code">
<TEXTAREA NAME="prompt" ROWS="4" COLS="72" WRAP="virtual">Analysiere diesen Code und erklaere was er tut:</TEXTAREA>
<INPUT TYPE="HIDDEN" NAME="code" VALUE="{content_val}">
<P><INPUT TYPE="SUBMIT" VALUE=" An Claude senden "></P>
</FORM>
""")

def page_save_result(filename, success):
    if success:
        msg = f'<P>Datei <CODE>{html.escape(filename)}</CODE> gespeichert.</P>'
        msg += '<P><A HREF="/files">Zum Shared Folder</A></P>'
    else:
        msg = '<P><B>Fehler:</B> Datei konnte nicht gespeichert werden.</P>'
    return html_page("Datei speichern", msg)

def page_history():
    if not conversation_history:
        content = "<P><I>Noch keine Fragen gestellt.</I></P>"
    else:
        rows = ""
        for entry in reversed(conversation_history):
            rows += f"""
<TR BGCOLOR="#FFFFFF">
<TD VALIGN="TOP"><FONT SIZE="-1">{entry['time']}<BR>{entry['mode']}</FONT></TD>
<TD VALIGN="TOP">{html.escape(sanitize(entry['question']))}</TD>
<TD VALIGN="TOP"><FONT SIZE="-1">{html.escape(sanitize(entry['answer'][:200]))}...</FONT></TD>
</TR>"""
        content = f"""
<TABLE BORDER="1" CELLPADDING="4" CELLSPACING="0" WIDTH="100%">
<TR BGCOLOR="#CCCCCC"><TH>Zeit</TH><TH>Frage</TH><TH>Antwort</TH></TR>
{rows}
</TABLE>"""
    return html_page("Verlauf", content)

# --- HTTP Handler ---

class BridgeHandler(BaseHTTPRequestHandler):

    def handle(self):
        try:
            super().handle()
        except (OSError, ConnectionResetError, BrokenPipeError):
            pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/":
            self.send_html(page_index())
        elif path == "/code":
            self.send_html(page_code())
        elif path == "/rez":
            self.send_html(page_rez())
        elif path == "/ask":
            self.send_html(page_ask())
        elif path == "/files":
            self.send_html(page_files(params.get("sub", [""])[0]))
        elif path == "/readfile":
            self.send_html(page_readfile(params.get("name", [""])[0]))
        elif path == "/history":
            self.send_html(page_history())
        elif path.startswith("/result/"):
            self.handle_result(path.split("/result/")[1])
        elif path.startswith("/text/"):
            self.handle_text(path.split("/text/")[1])
        else:
            self.send_error(404)

    def handle_result(self, job_id):
        if job_id not in jobs:
            self.send_html(html_page("Fehler",
                "<P>Job nicht gefunden. <A HREF='/'>Zurueck</A></P>"))
            return
        job = jobs[job_id]

        # Check for timeout
        if job["status"] == "working":
            elapsed = time.time() - job["started"]
            if elapsed > JOB_TIMEOUT_SECONDS:
                with job_lock:
                    jobs[job_id]["status"] = "timeout"
                    jobs[job_id]["answer"] = f"[Timeout]: Die Anfrage hat mehr als {JOB_TIMEOUT_SECONDS} Sekunden gedauert und wurde abgebrochen."
            else:
                self.send_html(page_waiting(job_id, job["mode"]))
                return

        # Show result (done, error, or timeout)
        mode = job["mode"]
        if mode == "Code":
            self.send_html(page_code_result(job["prompt"], job["answer"], job_id))
        elif mode == "Rez":
            self.send_html(page_rez_result(job["prompt"], job["answer"], job_id))
        else:
            self.send_html(page_ask_result(job["prompt"], job["answer"], job_id))

        # Cleanup old jobs (with lock to prevent race condition)
        with job_lock:
            if len(jobs) > 10:
                for k in sorted(jobs.keys(), key=int)[:-10]:
                    if k in jobs:  # Double-check before deleting
                        del jobs[k]

    def handle_text(self, job_id):
        """Serve answer as plain text for easy Cmd+A, Cmd+C."""
        if job_id not in jobs or jobs[job_id]["status"] != "done":
            self.send_text("Job nicht gefunden oder noch nicht fertig.")
            return
        self.send_text(sanitize(jobs[job_id]["answer"]))

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("iso-8859-1", errors="replace")
        params = parse_qs(body)
        path = urlparse(self.path).path

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            self.send_html(html_page("Fehler",
                "<P><B>ANTHROPIC_API_KEY nicht gesetzt!</B></P>"
                "<PRE>export ANTHROPIC_API_KEY='sk-ant-...'</PRE>"))
            return

        if path == "/code":
            prompt = params.get("prompt", [""])[0]
            code = params.get("code", [""])[0]
            full = prompt + (f"\n\nHier ist der Code:\n\n{code}" if code else "")
            job_id = create_job("Code", full, SYSTEM_PROMPT_CODE)
            self.send_html(page_waiting(job_id, "Code"))

        elif path == "/rez":
            prompt = params.get("prompt", [""])[0]
            types = params.get("types", [""])[0]
            full = prompt + (f"\n\nBenoetigte Resource-Typen: {types}" if types else "")
            job_id = create_job("Rez", full, SYSTEM_PROMPT_REZ)
            self.send_html(page_waiting(job_id, "Rez"))

        elif path == "/ask":
            prompt = params.get("prompt", [""])[0]
            job_id = create_job("Frage", prompt, SYSTEM_PROMPT_GENERAL)
            self.send_html(page_waiting(job_id, "Frage"))

        elif path == "/save":
            filename = params.get("filename", ["output.txt"])[0]
            content = params.get("content", [""])[0]
            # Sanitize filename: only allow alphanumeric, dots, dashes, underscores
            import re
            filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
            # Prevent hidden files and ensure non-empty
            if not filename or filename.startswith('.'):
                filename = "output.txt"
            self.send_html(page_save_result(filename, save_shared_file(filename, content)))

        else:
            self.send_error(404)

    def send_html(self, content):
        data = content.encode("iso-8859-1", errors="replace")
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)

    def send_text(self, content):
        data = content.encode("iso-8859-1", errors="replace")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        logging.info(f"{args[0]}")

# --- Main ---

def load_api_key():
    """Load API key from multiple locations (in priority order):
    1. Environment variable (already set via export)
    2. ~/.config/anthropic/api_key
    3. .env file in script directory
    """
    # 1. Already in environment?
    if os.environ.get("ANTHROPIC_API_KEY"):
        logging.info("API Key: loaded from environment variable")
        return

    # 2. ~/.config/anthropic/api_key
    config_file = Path.home() / ".config" / "anthropic" / "api_key"
    if config_file.exists():
        key = config_file.read_text().strip()
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key
            logging.info(f"API Key: loaded from {config_file}")
            return

    # 3. .env file next to script
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("'").strip('"')
                os.environ[key] = value
        if os.environ.get("ANTHROPIC_API_KEY"):
            logging.info(f"API Key: loaded from {env_file}")
            return

def main():
    # Setup logging first (before anything else)
    setup_logging()

    # Load configuration
    load_config()

    parser = argparse.ArgumentParser(description="Claude Bridge Server")
    parser.add_argument("--port", type=int, default=CONFIG["server"]["port"])
    parser.add_argument("--host", default=CONFIG["server"]["host"])
    parser.add_argument("--shared-folder", default=CONFIG["files"]["shared_folder"])
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    args = parser.parse_args()

    # Reload config if custom path specified
    if args.config != "config.yaml":
        load_config(args.config)

    global SHARED_FOLDER, CLAUDE_MODEL, MAX_TOKENS, REFRESH_SECONDS, JOB_TIMEOUT_SECONDS
    SHARED_FOLDER = args.shared_folder or CONFIG["files"]["shared_folder"]
    CLAUDE_MODEL = CONFIG["claude"]["model"]
    MAX_TOKENS = CONFIG["claude"]["max_tokens"]
    REFRESH_SECONDS = CONFIG["jobs"]["refresh_interval"]
    JOB_TIMEOUT_SECONDS = CONFIG["jobs"]["timeout"]

    # Load API key from config files
    load_api_key()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logging.warning("=" * 60)
        logging.warning("ANTHROPIC_API_KEY nicht gefunden!")
        logging.warning("")
        logging.warning("Option 1 (empfohlen):")
        logging.warning("  mkdir -p ~/.config/anthropic")
        logging.warning("  echo 'sk-ant-...' > ~/.config/anthropic/api_key")
        logging.warning("  chmod 600 ~/.config/anthropic/api_key")
        logging.warning("")
        logging.warning("Option 2: .env Datei im Script-Ordner")
        logging.warning("Option 3: export ANTHROPIC_API_KEY='sk-ant-...'")
        logging.warning("=" * 60)
    else:
        logging.info(f"API Key: ...{api_key[-8:]}")

    server = HTTPServer((args.host, args.port), BridgeHandler)
    logging.info("=" * 60)
    logging.info(f"Claude Bridge Server 1.2")
    logging.info(f"Server: http://{args.host}:{args.port}/")
    logging.info(f"Shared: {SHARED_FOLDER or '(nicht gesetzt)'}")
    logging.info(f"Model: {CLAUDE_MODEL}")
    logging.info(f"Config: {args.config}")
    logging.info("=" * 60)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("\n" + "=" * 60)
        logging.info("Shutdown-Signal empfangen, fahre herunter...")

        # Signal shutdown to running jobs
        shutdown_event.set()

        # Wait for running jobs to complete (max 30 seconds)
        logging.info("Warte auf laufende Jobs...")
        max_wait = 30
        start_wait = time.time()

        while time.time() - start_wait < max_wait:
            with job_lock:
                working_jobs = [j for j in jobs.values() if j["status"] == "working"]
            if not working_jobs:
                break
            logging.info(f"Noch {len(working_jobs)} Job(s) aktiv...")
            time.sleep(2)

        with job_lock:
            working_jobs = [j for j in jobs.values() if j["status"] == "working"]
            if working_jobs:
                logging.warning(f"{len(working_jobs)} Job(s) wurden nicht rechtzeitig beendet")
            else:
                logging.info("Alle Jobs abgeschlossen")

        server.server_close()
        logging.info("Server beendet.")
        logging.info("=" * 60)

if __name__ == "__main__":
    main()

