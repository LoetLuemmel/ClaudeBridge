#!/usr/bin/env python3
"""
Claude Bridge Server 2.0 - Modular Architecture
================================================

Main entry point with routing to Claude Interface and Web Proxy.

Features:
- Modular architecture with separate Claude and Proxy modules
- No shared state between features (separate caches, job queues, rate limiters)
- Configuration file support (config.yaml)
- Structured logging
- Graceful error handling
- Background threading for Claude API calls

Usage:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python3 claude_bridge.py [--port 8080] [--host 0.0.0.0]
"""

import argparse
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from applebridge.config import (load_config, setup_logging, load_api_key,
                                check_bind_host, CONFIG)
from applebridge.claude.server import ClaudeHandler
from applebridge.claude.history import load_history
from applebridge.proxy.server import ProxyHandler
from applebridge.setup import SetupHandler


class UnifiedHandler(BaseHTTPRequestHandler):
    """Routes requests to appropriate handler based on URL path."""

    def __init__(self, *args, **kwargs):
        # Initialize handlers
        self.claude = ClaudeHandler()
        self.proxy = ProxyHandler()
        self.setup_page = SetupHandler()
        super().__init__(*args, **kwargs)

    def handle(self):
        """Handle connection with error suppression."""
        try:
            super().handle()
        except (OSError, ConnectionResetError, BrokenPipeError):
            # Client disconnected, ignore
            pass

    def do_GET(self):
        """Route GET requests to appropriate handler."""
        path = urlparse(self.path).path

        # Route to Proxy for /web, /proxy, /proxyimg
        if path in ['/web', '/proxy', '/proxyimg']:
            self.proxy.handle_get(self)
        # Host configuration - loopback only, see applebridge/setup.py
        elif path == '/setup':
            self.setup_page.handle_get(self)
        # All other paths go to Claude Interface
        else:
            self.claude.handle_get(self)

    def do_POST(self):
        """Route POST requests."""
        path = urlparse(self.path).path
        if path == '/setup/save':
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("iso-8859-1", errors="replace")
            self.setup_page.handle_post(self, parse_qs(body, encoding="iso-8859-1"))
        else:
            self.claude.handle_post(self)

    def log_message(self, format, *args):
        """Log HTTP requests using configured logging.

        The client address is included because it decides whether /setup is
        served, and because it is the only way to tell a loopback request
        (slirp) from a LAN one (bridge) after the fact.
        """
        logging.info(f"{self.client_address[0]} {args[0]}")


def main():
    """Main entry point."""
    # Setup logging first (before anything else)
    setup_logging()

    # Load configuration
    load_config()

    # Load API key
    load_api_key()

    # Load persistent history
    load_history()

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Claude Bridge Server 2.0")
    parser.add_argument("--port", type=int, default=CONFIG["server"]["port"],
                        help="Port to listen on (default: 8080)")
    parser.add_argument("--host", default=CONFIG["server"]["host"],
                        help="Host to bind to (default: 0.0.0.0)")
    args = parser.parse_args()

    # slirp-only: refuse any non-loopback bind before opening the socket
    problem = check_bind_host(args.host)
    if problem:
        logging.error(problem)
        raise SystemExit(2)

    # Start server
    logging.info(f"Starting Claude Bridge Server 2.0 on {args.host}:{args.port}")
    logging.info(f"Claude Model: {CONFIG['claude']['model']}")
    logging.info(f"Shared Folder: {CONFIG['files']['shared_folder'] or '(not set)'}")

    server = HTTPServer((args.host, args.port), UnifiedHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Server shutting down...")
        server.shutdown()
        logging.info("Server stopped")


if __name__ == "__main__":
    main()
