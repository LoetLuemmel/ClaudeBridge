"""
Host Setup Page
===============

A configuration page for the host, served as HTML 3.2 so it can be used from
Netscape 3 on the guest.

ACCESS: the page is loopback-only by default (setup.require_loopback). In slirp
mode the guest reaches the host through the loopback interface, so the page
works; in bridge mode the guest is a real host on the LAN and is refused. That
keeps server configuration off the network exactly when the port is exposed to
it - there is no authentication anywhere in this project to fall back on.

The API key is never rendered, only its load status.
"""

import logging
import re
from pathlib import Path

from applebridge.config import CONFIG
from applebridge.encoding import escape_html, sanitize
from applebridge.claude.templates import html_page


CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

# Fields the page may write: (section, key, label, kind, hint)
EDITABLE = [
    ("server", "host", "Bind address", "text",
     "127.0.0.1 for slirp mode, 0.0.0.0 for bridge mode"),
    ("server", "port", "Port", "int", "default 8080"),
    ("claude", "model", "Claude model", "text", ""),
    ("claude", "max_tokens", "Max tokens", "int", ""),
    ("jobs", "refresh_interval", "Refresh interval (s)", "int",
     "not below 2 - Netscape 3 cannot keep up"),
    ("files", "shared_folder", "Shared folder", "text", ""),
    ("proxy", "block_private_networks", "Block private networks (SSRF filter)", "bool",
     "leave on unless you deliberately proxy your own network"),
]


def is_loopback(handler):
    """True if the request came from the local machine."""
    try:
        host = handler.client_address[0]
    except (AttributeError, IndexError):
        return False
    return host in ("127.0.0.1", "::1", "::ffff:127.0.0.1") or host.startswith("127.")


def update_yaml_value(section, key, value):
    """Rewrite one scalar in config.yaml, line by line.

    A parse-and-dump round trip would drop every comment in the file, and those
    comments carry the reasoning for half these settings. So the value is
    replaced in place instead, leaving the rest of the file untouched.

    Returns True if the line was found and rewritten.
    """
    if not CONFIG_PATH.exists():
        return False

    lines = CONFIG_PATH.read_text(encoding="utf-8").splitlines()
    in_section = False
    out = []
    written = False

    for line in lines:
        stripped = line.strip()
        # A top-level key ends the previous section
        if line and not line[0].isspace() and not stripped.startswith("#"):
            in_section = stripped.rstrip(":") == section

        if in_section and not written:
            m = re.match(r"^(\s+)" + re.escape(key) + r":\s*(.*?)(\s+#.*)?$", line)
            if m:
                indent, _, comment = m.group(1), m.group(2), m.group(3) or ""
                if isinstance(value, bool):
                    rendered = "true" if value else "false"
                elif isinstance(value, int):
                    rendered = str(value)
                else:
                    rendered = f'"{value}"'
                out.append(f"{indent}{key}: {rendered}{comment}")
                written = True
                continue
        out.append(line)

    if written:
        CONFIG_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")
    return written


def read_network_mode():
    """Current Basilisk II ether setting, or None if unreadable."""
    prefs = Path.home() / ".basilisk_ii_prefs"
    try:
        for line in prefs.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("ether "):
                return line[len("ether "):].strip()
    except OSError:
        pass
    return None


class SetupHandler:
    """Serves /setup and /setup/save."""

    def _refuse(self, handler, reason):
        logging.warning(f"Setup page refused for {handler.client_address[0]}: {reason}")
        self._send(handler, html_page("Setup -- not available", f"""
<P><B>This page is not available.</B></P>
<P>{escape_html(reason)}</P>
<P>Host configuration lives in <CODE>config.yaml</CODE> and can be edited there
directly. The network mode is switched with <CODE>netmode.py</CODE> on the host.</P>
"""))

    def handle_get(self, handler):
        if not CONFIG["setup"]["enabled"]:
            self._refuse(handler, "The setup page is disabled (setup.enabled is false).")
            return
        if CONFIG["setup"]["require_loopback"] and not is_loopback(handler):
            self._refuse(handler,
                         "It is served to the local machine only. This request came "
                         f"from {handler.client_address[0]}, which means the emulator "
                         "is in bridge mode and the port is reachable from the whole "
                         "network. There is no authentication here, so writing server "
                         "configuration over the network is not offered.")
            return
        self._send(handler, self._page())

    def handle_post(self, handler, params):
        if not CONFIG["setup"]["enabled"]:
            self._refuse(handler, "The setup page is disabled (setup.enabled is false).")
            return
        if CONFIG["setup"]["require_loopback"] and not is_loopback(handler):
            self._refuse(handler, "Writes are accepted from the local machine only.")
            return

        changed, errors = [], []
        for section, key, label, kind, _hint in EDITABLE:
            field = f"{section}__{key}"
            if field not in params:
                continue
            raw = params[field][0].strip()
            try:
                if kind == "int":
                    value = int(raw)
                    if section == "jobs" and key == "refresh_interval" and value < 2:
                        errors.append(f"{label}: below 2 seconds overwhelms Netscape 3")
                        continue
                elif kind == "bool":
                    value = raw.lower() in ("1", "true", "on", "yes")
                else:
                    value = raw
            except ValueError:
                errors.append(f"{label}: '{escape_html(raw)}' is not a number")
                continue

            if CONFIG[section][key] != value:
                if update_yaml_value(section, key, value):
                    CONFIG[section][key] = value
                    changed.append(f"{label} -> {value}")
                else:
                    errors.append(f"{label}: could not be written to config.yaml")

        # Checkboxes that are off are simply absent from the POST body
        for section, key, label, kind, _hint in EDITABLE:
            if kind == "bool" and f"{section}__{key}" not in params:
                if CONFIG[section][key] is not False:
                    if update_yaml_value(section, key, False):
                        CONFIG[section][key] = False
                        changed.append(f"{label} -> false")

        self._send(handler, self._page(changed=changed, errors=errors))

    def _page(self, changed=None, errors=None):
        rows = []
        for section, key, label, kind, hint in EDITABLE:
            value = CONFIG[section][key]
            field = f"{section}__{key}"
            if kind == "bool":
                checked = ' CHECKED' if value else ''
                control = f'<INPUT TYPE="CHECKBOX" NAME="{field}" VALUE="1"{checked}>'
            else:
                shown = escape_html(str(value if value is not None else ""), quote=True)
                control = f'<INPUT TYPE="TEXT" NAME="{field}" SIZE="34" VALUE="{shown}">'
            hint_html = f'<BR><FONT SIZE="-1">{escape_html(hint)}</FONT>' if hint else ""
            rows.append(
                f'<TR><TD VALIGN="TOP"><B>{escape_html(label)}</B>{hint_html}</TD>'
                f'<TD VALIGN="TOP">{control}</TD></TR>')

        notice = ""
        if changed:
            items = "".join(f"<LI>{escape_html(c)}</LI>" for c in changed)
            notice += ('<TABLE WIDTH="100%" BGCOLOR="#CCFFCC" CELLPADDING="8"><TR><TD>'
                       f'<B>Saved to config.yaml:</B><UL>{items}</UL>'
                       '<FONT SIZE="-1">Bind address and port take effect after a '
                       'server restart. The other values apply to the next request.'
                       '</FONT></TD></TR></TABLE><BR>')
        if errors:
            items = "".join(f"<LI>{escape_html(e)}</LI>" for e in errors)
            notice += ('<TABLE WIDTH="100%" BGCOLOR="#FFCCCC" CELLPADDING="8"><TR><TD>'
                       f'<B>Not saved:</B><UL>{items}</UL></TD></TR></TABLE><BR>')

        mode = read_network_mode()
        if mode == "slirp":
            mode_text = ("<B>slirp</B> - the guest sits behind a NAT inside this host "
                         "and reaches it at 10.0.2.2. The server can bind 127.0.0.1 and "
                         "the firewall can stay on.")
        elif mode:
            mode_text = (f"<B>bridge</B> ({escape_html(mode)}) - the guest is its own "
                         "host on the LAN. The server must bind 0.0.0.0 and the "
                         "firewall must be open, which exposes the port to the network.")
        else:
            mode_text = "<I>unknown - ~/.basilisk_ii_prefs could not be read</I>"

        import os
        key_state = "loaded" if os.environ.get("ANTHROPIC_API_KEY") else "NOT set"

        return html_page("Setup", f"""
{notice}
<P>Host configuration. Written to <CODE>config.yaml</CODE>.</P>

<FORM METHOD="POST" ACTION="/setup/save">
<TABLE CELLPADDING="6" CELLSPACING="0" WIDTH="100%">
{"".join(rows)}
</TABLE>
<P><B>&gt;&gt;</B> <INPUT TYPE="SUBMIT" VALUE=" Save "> <B>&lt;&lt;</B></P>
</FORM>

<HR>
<P><B>Network mode:</B> {mode_text}</P>
<P><FONT SIZE="-1">Switching modes cannot be done from here: Basilisk II reads
the setting before the guest boots, so it needs an emulator restart. Use
<CODE>netmode.py slirp</CODE> or <CODE>netmode.py bridge</CODE> on the host, and
remember the guest's TCP/IP control panel has to follow.</FONT></P>

<HR>
<P><B>API key:</B> {key_state}</P>
<P><FONT SIZE="-1">The key itself is never shown on this page and cannot be set
here. It is read from the environment or ~/.config/anthropic/api_key.</FONT></P>
""")

    def _send(self, handler, content):
        data = sanitize(content).encode("iso-8859-1", errors="replace")
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.send_header("Content-Length", str(len(data)))
        handler.send_header("Connection", "close")
        handler.end_headers()
        handler.wfile.write(data)
