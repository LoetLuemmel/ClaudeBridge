"""
SSRF Protection for Web Proxy
==============================

Blocks proxy requests that target the local machine or private networks.

Without this, /proxy?url= is an open relay: anyone on the LAN could make this
server fetch http://127.0.0.1:9001/ or the router's admin page - hosts that are
unreachable from their side of the network but reachable from ours.

Every hop is checked, including redirect targets. A public URL that answers with
a 302 to 127.0.0.1 is the classic way around a naive filter.
"""

import ipaddress
import logging
import socket
import urllib.request
import urllib.error
from urllib.parse import urlparse

from applebridge.config import CONFIG


ALLOWED_SCHEMES = ("http", "https")


def _is_blocked_ip(ip):
    """True if this address points at the local machine or a private network."""
    # ::ffff:127.0.0.1 has to be judged as 127.0.0.1, not as an IPv6 address
    if getattr(ip, "ipv4_mapped", None):
        ip = ip.ipv4_mapped
    return (
        ip.is_private          # 10/8, 172.16/12, 192.168/16, fc00::/7
        or ip.is_loopback      # 127/8, ::1
        or ip.is_link_local    # 169.254/16 (incl. cloud metadata), fe80::/10
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified   # 0.0.0.0, ::
    )


def check_url(url):
    """Validate a URL before fetching it.

    Returns None if the URL is safe, otherwise an error message ready for
    display in the proxy error page.
    """
    if not CONFIG["proxy"]["block_private_networks"]:
        return None

    parsed = urlparse(url)

    if parsed.scheme not in ALLOWED_SCHEMES:
        return "Nur http:// und https:// sind erlaubt"

    host = parsed.hostname
    if not host:
        return "URL enthaelt keinen Hostnamen"

    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return "Ungueltiger Port in der URL"

    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, ValueError):
        return f"Hostname nicht aufloesbar: {host}"

    # A hostname can resolve to several addresses - a single bad one is enough
    # to reject the whole URL.
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if _is_blocked_ip(ip):
            logging.warning(f"SSRF blocked: {url} -> {ip}")
            return f"Zugriff auf lokale/private Adressen gesperrt ({ip})"

    return None


class _ValidatingRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Re-checks every redirect target before following it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        error = check_url(newurl)
        if error:
            logging.warning(f"SSRF blocked on redirect: {newurl}")
            raise urllib.error.HTTPError(
                newurl, code, f"Redirect blockiert: {error}", headers, fp
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def build_opener():
    """Opener that validates redirect targets as well as the initial URL."""
    return urllib.request.build_opener(_ValidatingRedirectHandler)
