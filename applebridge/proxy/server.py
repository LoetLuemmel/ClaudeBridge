"""
Web Proxy HTTP Server
======================

Handles HTTP requests for the Web Proxy endpoints.
"""

import time
import logging
from urllib.parse import urlparse, parse_qs

from applebridge.encoding import sanitize
from applebridge.proxy.fetcher import fetch_https_page
from applebridge.proxy.images import fetch_image
from applebridge.proxy.simplifier import page_proxy, page_proxy_result, page_proxy_error


class ProxyHandler:
    """Handles all Web Proxy HTTP requests."""

    def handle_get(self, handler):
        """Handle GET requests for Web Proxy."""
        parsed = urlparse(handler.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/web":
            self._send_html(handler, page_proxy())
        elif path == "/proxy":
            self._handle_proxy(handler, params.get("url", [""])[0])
        elif path == "/proxyimg":
            self._handle_proxy_image(handler, params.get("url", [""])[0])
        else:
            handler.send_error(404)

    def _handle_proxy(self, handler, url):
        """Handle web proxy requests."""
        if not url:
            self._send_html(handler, page_proxy())
            return

        # Validate URL
        if not url.startswith('http://') and not url.startswith('https://'):
            self._send_html(handler, page_proxy_error(url, "URL muss mit http:// oder https:// beginnen"))
            return

        logging.info(f"Proxy request: {url}")
        start_time = time.time()

        # Fetch the page
        html_content, final_url, error = fetch_https_page(url)

        if error:
            logging.warning(f"Proxy error for {url}: {error}")
            self._send_html(handler, page_proxy_error(url, error))
            return

        fetch_time = time.time() - start_time
        logging.info(f"Page fetched in {fetch_time:.1f}s: {len(html_content)} bytes")

        # Simplify and send
        try:
            simplify_start = time.time()
            result = page_proxy_result(url, html_content, final_url)
            simplify_time = time.time() - simplify_start

            # Use sanitize to ensure ISO-8859-1 compatibility
            result = sanitize(result)

            total_time = time.time() - start_time
            logging.info(f"Proxy success: {url} (fetch: {fetch_time:.1f}s, process: {simplify_time:.1f}s, total: {total_time:.1f}s)")

            self._send_html(handler, result)
        except Exception as e:
            logging.error(f"Proxy processing error for {url}: {str(e)}")
            self._send_html(handler, page_proxy_error(url, f"Fehler beim Verarbeiten der Seite: {str(e)}"))

    def _handle_proxy_image(self, handler, url):
        """Handle image proxy requests - fetch HTTPS images and serve as HTTP."""
        if not url:
            handler.send_error(400, "No URL specified")
            return

        # Validate URL
        if not url.startswith('http://') and not url.startswith('https://'):
            handler.send_error(400, "Invalid URL")
            return

        logging.debug(f"Image proxy request: {url}")

        # Fetch and optimize the image
        image_data, content_type, error = fetch_image(url)

        if error:
            logging.warning(f"Image proxy error for {url}: {error}")
            # Send a 1x1 transparent GIF as fallback
            try:
                handler.send_response(200)
                handler.send_header("Content-Type", "image/gif")
                # 1x1 transparent GIF
                transparent_gif = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
                handler.send_header("Content-Length", str(len(transparent_gif)))
                handler.send_header("Connection", "close")
                handler.end_headers()
                handler.wfile.write(transparent_gif)
            except (BrokenPipeError, ConnectionResetError, OSError):
                # Client disconnected, ignore
                pass
            return

        # Send the optimized image
        try:
            handler.send_response(200)
            handler.send_header("Content-Type", content_type)
            handler.send_header("Content-Length", str(len(image_data)))
            handler.send_header("Connection", "close")
            handler.end_headers()
            handler.wfile.write(image_data)
            logging.debug(f"Image proxy success: {url} ({len(image_data)} bytes)")
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            # Netscape 3 disconnected early - this is normal for slow connections
            # Don't log as error, just debug
            logging.debug(f"Client disconnected during image transfer: {url}")

    def _send_html(self, handler, content):
        """Send HTML response with ISO-8859-1 encoding."""
        data = content.encode("iso-8859-1", errors="replace")
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.send_header("Content-Length", str(len(data)))
        handler.send_header("Connection", "close")
        handler.end_headers()
        handler.wfile.write(data)
