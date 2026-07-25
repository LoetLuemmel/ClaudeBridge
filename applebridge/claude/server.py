"""
Claude Interface HTTP Server
==============================

Handles HTTP requests for the Claude Interface endpoints.
"""

import json
import logging
import os
import re
import time
from urllib.parse import urlparse, parse_qs

from applebridge.encoding import sanitize, strip_markdown
from applebridge.claude.templates import *
from applebridge.claude.prompts import *
from applebridge.claude.jobs import create_job, get_job, check_job_timeout, cleanup_old_jobs
from applebridge.claude.files import save_shared_file
from applebridge.claude.history import clear_chat_history


class ClaudeHandler:
    """Handles all Claude Interface HTTP requests."""

    def _wants_json(self, handler):
        """Check if client wants JSON response (native app)."""
        user_agent = handler.headers.get("User-Agent", "")
        return "ClaudeAssistant" in user_agent

    def _send_json(self, handler, data):
        """Send JSON response."""
        content = json.dumps(data, ensure_ascii=False)
        data_bytes = content.encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(data_bytes)))
        handler.send_header("Connection", "close")
        handler.end_headers()
        handler.wfile.write(data_bytes)

    def handle_get(self, handler):
        """Handle GET requests for Claude Interface."""
        parsed = urlparse(handler.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/":
            self._send_html(handler, page_index())
        elif path == "/code":
            self._send_html(handler, page_code())
        elif path == "/rez":
            self._send_html(handler, page_rez())
        elif path == "/ask":
            self._send_html(handler, page_ask())
        elif path == "/chat":
            self._send_html(handler, page_chat())
        elif path == "/chat/clear":
            clear_chat_history()
            self._send_html(handler, html_page("Chat cleared",
                '<P>Chat history has been cleared.</P><P><A HREF="/chat">Back to Chat</A></P>'))
        elif path == "/files":
            self._send_html(handler, page_files(params.get("sub", [""])[0]))
        elif path == "/readfile":
            self._send_html(handler, page_readfile(params.get("name", [""])[0]))
        elif path == "/history":
            self._send_html(handler, page_history())
        elif path.startswith("/history/chat/"):
            # Chat history detail
            try:
                entry_id = int(path.split("/history/chat/")[1])
                self._send_html(handler, page_chat_history_detail(entry_id))
            except (ValueError, IndexError):
                handler.send_error(404)
        elif path.startswith("/history/"):
            # Code/Rez/Ask history detail
            try:
                entry_id = int(path.split("/history/")[1])
                self._send_html(handler, page_history_detail(entry_id))
            except (ValueError, IndexError):
                handler.send_error(404)
        elif path.startswith("/result/"):
            self._handle_result(handler, path.split("/result/")[1])
        elif path.startswith("/text/"):
            self._handle_text(handler, path.split("/text/")[1])
        else:
            handler.send_error(404)

    def _handle_result(self, handler, job_id):
        """Display job result or waiting page."""
        job = get_job(job_id)
        if not job:
            if self._wants_json(handler):
                self._send_json(handler, {"error": "Job not found"})
            else:
                self._send_html(handler, html_page("Fehler",
                    "<P>Job nicht gefunden. <A HREF='/'>Zurueck</A></P>"))
            return

        # Check for timeout
        if job["status"] == "working":
            if check_job_timeout(job_id):
                # Timeout occurred, reload to show timeout message
                job = get_job(job_id)
            else:
                # Still working
                if self._wants_json(handler):
                    elapsed = int(time.time() - job["started"])
                    self._send_json(handler, {"status": "working", "elapsed": elapsed})
                else:
                    self._send_html(handler, page_waiting(job_id, job["started"]))
                return

        # Job is done (or error/timeout)
        if self._wants_json(handler):
            # Return JSON for native app
            self._send_json(handler, {
                "status": job["status"],
                "answer": job["answer"],
                "mode": job["mode"]
            })
        else:
            # Return HTML for browser
            mode = job["mode"]
            display_text = job.get("display_prompt", job["prompt"])  # Use display_prompt if available
            if mode == "Code":
                self._send_html(handler, page_code_result(display_text, job["answer"], job_id))
            elif mode == "Rez":
                self._send_html(handler, page_rez_result(display_text, job["answer"], job_id))
            elif mode == "Chat":
                self._send_html(handler, page_chat_result(display_text, job["answer"], job_id))
            else:
                self._send_html(handler, page_ask_result(job["prompt"], job["answer"], job_id))

        # Cleanup old jobs
        cleanup_old_jobs()

    def _handle_text(self, handler, job_id):
        """Serve answer as plain text for easy copying."""
        job = get_job(job_id)
        if not job or job["status"] != "done":
            self._send_text(handler, "Job not found or not ready yet.")
            return
        # Strip markdown formatting before sanitizing
        answer = job["answer"]
        answer = strip_markdown(answer)
        self._send_text(handler, sanitize(answer))

    def handle_post(self, handler):
        """Handle POST requests for Claude Interface."""
        content_length = int(handler.headers.get("Content-Length", 0))
        body = handler.rfile.read(content_length).decode("iso-8859-1", errors="replace")
        params = parse_qs(body)
        path = urlparse(handler.path).path

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            if self._wants_json(handler):
                self._send_json(handler, {"error": "ANTHROPIC_API_KEY not set"})
            else:
                self._send_html(handler, html_page("Error",
                    "<P><B>ANTHROPIC_API_KEY not set!</B></P>"
                    "<PRE>export ANTHROPIC_API_KEY='sk-ant-...'</PRE>"))
            return

        if path == "/code":
            prompt = params.get("prompt", [""])[0]
            code = params.get("code", [""])[0]
            if code:
                # Ask for complete modified code only
                full = (f"{prompt}\n\n"
                       f"=== REFERENCE CODE ===\n"
                       f"{code}\n"
                       f"=== END REFERENCE CODE ===\n\n"
                       f"Provide the COMPLETE modified code in a single ```c code block.\n"
                       f"Include the entire working program, not just snippets.")
                # Show only the question, not the code
                job_id = create_job("Code", full, SYSTEM_PROMPT_CODE, display_prompt=prompt)
            else:
                job_id = create_job("Code", prompt, SYSTEM_PROMPT_CODE)
            if self._wants_json(handler):
                self._send_json(handler, {"job_id": job_id})
            else:
                job = get_job(job_id)
                self._send_html(handler, page_waiting(job_id, job["started"]))

        elif path == "/rez":
            prompt = params.get("prompt", [""])[0]
            types = params.get("types", [""])[0]
            full = prompt + (f"\n\nRequired resource types: {types}" if types else "")
            job_id = create_job("Rez", full, SYSTEM_PROMPT_REZ)
            if self._wants_json(handler):
                self._send_json(handler, {"job_id": job_id})
            else:
                job = get_job(job_id)
                self._send_html(handler, page_waiting(job_id, job["started"]))

        elif path == "/ask":
            prompt = params.get("prompt", [""])[0]
            job_id = create_job("Frage", prompt, SYSTEM_PROMPT_GENERAL)
            if self._wants_json(handler):
                self._send_json(handler, {"job_id": job_id})
            else:
                job = get_job(job_id)
                self._send_html(handler, page_waiting(job_id, job["started"]))

        elif path == "/chat":
            message = params.get("message", [""])[0]
            if not message.strip():
                if self._wants_json(handler):
                    self._send_json(handler, {"error": "Empty message"})
                else:
                    self._send_html(handler, html_page("Fehler",
                        '<P>Bitte eine Nachricht eingeben.</P><P><A HREF="/chat">Zurueck</A></P>'))
                return

            job_id = create_job("Chat", message, SYSTEM_PROMPT_CHAT, is_chat=True)
            if self._wants_json(handler):
                self._send_json(handler, {"job_id": job_id})
            else:
                job = get_job(job_id)
                self._send_html(handler, page_waiting(job_id, job["started"]))

        elif path == "/save":
            filename = params.get("filename", ["output.txt"])[0]
            content = params.get("content", [""])[0]
            # Sanitize filename: only allow alphanumeric, dots, dashes, underscores
            filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
            # Prevent hidden files and ensure non-empty
            if not filename or filename.startswith('.'):
                filename = "output.txt"
            self._send_html(handler, page_save_result(filename, save_shared_file(filename, content)))

        else:
            handler.send_error(404)

    def _send_html(self, handler, content):
        """Send HTML response with ISO-8859-1 encoding."""
        data = content.encode("iso-8859-1", errors="replace")
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.send_header("Content-Length", str(len(data)))
        handler.send_header("Connection", "close")
        handler.end_headers()
        handler.wfile.write(data)

    def _send_text(self, handler, content):
        """Send plain text response with ISO-8859-1 encoding."""
        data = content.encode("iso-8859-1", errors="replace")
        handler.send_response(200)
        handler.send_header("Content-Type", "text/plain")
        handler.send_header("Content-Length", str(len(data)))
        handler.send_header("Connection", "close")
        handler.end_headers()
        handler.wfile.write(data)
