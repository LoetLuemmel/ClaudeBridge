#!/usr/bin/env python3
"""
Unit Tests for Claude Bridge Server
====================================
Tests critical security and functionality components.

Imports target the v2.0 module layout under applebridge/ - the monolithic
claude_bridge module these tests were originally written against no longer
exists, it is now just the entry point.

Run with:  uv run python test_claude_bridge.py
"""

import unittest
import tempfile
import shutil
import email.message
import urllib.request
import urllib.error
from pathlib import Path
import sys
import os

# Add parent directory to path so the applebridge package is importable
sys.path.insert(0, os.path.dirname(__file__))

from applebridge.config import CONFIG, check_bind_host
from applebridge.encoding import sanitize, escape_html
from applebridge.claude.files import (
    validate_safe_path,
    read_shared_file,
    save_shared_file,
)
from applebridge.proxy.ssrf import check_url, _ValidatingRedirectHandler


class TestPathValidation(unittest.TestCase):
    """Test path traversal prevention."""

    def setUp(self):
        """Create temporary directory for testing."""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir)

    def test_valid_path(self):
        """Test that valid paths are accepted."""
        result = validate_safe_path(self.test_dir, "test.txt")
        self.assertIsNotNone(result)
        self.assertTrue(str(result).startswith(str(Path(self.test_dir).resolve())))

    def test_subdirectory_path(self):
        """Test that subdirectory paths are accepted."""
        result = validate_safe_path(self.test_dir, "subdir/test.txt")
        self.assertIsNotNone(result)

    def test_path_traversal_parent(self):
        """Test that ../ path traversal is blocked."""
        result = validate_safe_path(self.test_dir, "../etc/passwd")
        self.assertIsNone(result)

    def test_path_traversal_absolute(self):
        """Test that absolute paths outside base are blocked."""
        result = validate_safe_path(self.test_dir, "/etc/passwd")
        self.assertIsNone(result)

    def test_path_traversal_multiple(self):
        """Test that multiple ../ are blocked."""
        result = validate_safe_path(self.test_dir, "../../../../../../etc/passwd")
        self.assertIsNone(result)

    def test_path_traversal_sneaky(self):
        """Test sneaky path traversal attempts."""
        result = validate_safe_path(self.test_dir, "subdir/../../etc/passwd")
        self.assertIsNone(result)


class TestSanitization(unittest.TestCase):
    """Test character sanitization for ISO-8859-1."""

    def test_ascii_passthrough(self):
        """Test that ASCII characters pass through unchanged."""
        text = "Hello World 123"
        result = sanitize(text)
        self.assertEqual(text, result)

    def test_german_umlauts(self):
        """Test that German umlauts are preserved (they exist in ISO-8859-1)."""
        text = "äöüÄÖÜß"
        result = sanitize(text)
        self.assertEqual(text, result)

    def test_unicode_quotes_replaced(self):
        """Test that Unicode quotes are replaced with ASCII."""
        text = "“Hello” ‘World’"  # Unicode quotes
        result = sanitize(text)
        self.assertIn('"', result)
        self.assertIn("'", result)
        self.assertNotIn("“", result)  # left double quote
        self.assertNotIn("‘", result)  # left single quote

    def test_unicode_dashes_replaced(self):
        """Test that Unicode dashes are replaced with ASCII."""
        text = "Hello—World–Test"  # em-dash and en-dash
        result = sanitize(text)
        self.assertIn("-", result)
        self.assertNotIn("—", result)  # em-dash
        self.assertNotIn("–", result)  # en-dash

    def test_emoji_removed(self):
        """Test that emojis are replaced with ?."""
        text = "Hello \U0001f916 World"  # robot emoji
        result = sanitize(text)
        self.assertNotIn("\U0001f916", result)
        self.assertIn("?", result)

    def test_mixed_content(self):
        """Test mixed ASCII, umlauts, and Unicode."""
        text = "Hällo—Wörld “Test” \U0001f680"  # em-dash, quotes, rocket emoji
        result = sanitize(text)
        self.assertIn("Hällo", result)
        self.assertIn("Wörld", result)
        self.assertIn("-", result)  # em-dash should be replaced with dash
        self.assertIn('"', result)  # Unicode quotes should be replaced


class TestNetscapeEscaping(unittest.TestCase):
    """Test HTML escaping stays within what Netscape Navigator 3 understands.

    html.escape() emits hexadecimal character references (&#x27;), an HTML 4.0
    feature. Netscape 3 renders those literally on screen, so escape_html()
    must never produce them.
    """

    def test_no_hex_character_references(self):
        """The regression that broke the display: ' must not become &#x27;."""
        result = escape_html("I'm doing wonderfully")
        self.assertNotIn("&#x27;", result)
        self.assertNotIn("&#x", result)
        self.assertIn("'", result)  # apostrophe stays literal

    def test_angle_brackets_and_ampersand(self):
        """The characters that genuinely must be escaped."""
        self.assertEqual(escape_html("<PRE>"), "&lt;PRE&gt;")
        self.assertEqual(escape_html("a & b"), "a &amp; b")

    def test_ampersand_escaped_first(self):
        """& must not be double-escaped into &amp;lt;."""
        self.assertEqual(escape_html("<"), "&lt;")
        self.assertEqual(escape_html("&lt;"), "&amp;lt;")

    def test_quote_only_in_attribute_mode(self):
        """Double quotes break attributes, so escape them - but only there."""
        self.assertEqual(escape_html('say "hi"'), 'say "hi"')
        self.assertEqual(escape_html('say "hi"', quote=True), "say &quot;hi&quot;")

    def test_apostrophe_never_escaped(self):
        """Attributes use double quotes, so ' is harmless even in quote mode."""
        self.assertIn("'", escape_html("it's", quote=True))


class TestSSRFProtection(unittest.TestCase):
    """Test that the web proxy cannot be pointed at the local machine.

    Without this the /proxy endpoint is an open relay: anyone on the LAN could
    reach 127.0.0.1 or the router through this server.
    """

    def assertBlocked(self, url):
        self.assertIsNotNone(check_url(url), f"should have been blocked: {url}")

    def assertAllowed(self, url):
        self.assertIsNone(check_url(url), f"should have been allowed: {url}")

    def test_loopback_blocked(self):
        self.assertBlocked("http://127.0.0.1:9001/")
        self.assertBlocked("http://localhost:8080/")
        self.assertBlocked("http://[::1]:8080/")

    def test_private_networks_blocked(self):
        self.assertBlocked("http://192.168.3.1/")      # router admin
        self.assertBlocked("http://10.0.0.1/")
        self.assertBlocked("http://172.16.0.1/")

    def test_link_local_blocked(self):
        """169.254.169.254 is the cloud metadata endpoint."""
        self.assertBlocked("http://169.254.169.254/")

    def test_unspecified_address_blocked(self):
        self.assertBlocked("http://0.0.0.0:8080/")

    def test_ipv4_mapped_ipv6_blocked(self):
        """::ffff:127.0.0.1 must be judged as 127.0.0.1, not as an IPv6 address."""
        self.assertBlocked("http://[::ffff:127.0.0.1]/")

    def test_non_http_schemes_blocked(self):
        self.assertBlocked("file:///etc/passwd")
        self.assertBlocked("gopher://example.com/")
        self.assertBlocked("ftp://example.com/")

    def test_public_addresses_allowed(self):
        """Literal public IPs - no DNS needed, so this stays hermetic."""
        self.assertAllowed("http://93.184.216.34/")
        self.assertAllowed("https://8.8.8.8/")

    def test_redirect_to_private_is_blocked(self):
        """A public URL that 302s to 127.0.0.1 is the classic bypass."""
        handler = _ValidatingRedirectHandler()
        req = urllib.request.Request("http://93.184.216.34/")
        with self.assertRaises(urllib.error.HTTPError):
            handler.redirect_request(
                req, None, 302, "Found", email.message.Message(),
                "http://127.0.0.1:9001/"
            )


class TestSlirpOnlyBinding(unittest.TestCase):
    """ClaudeBridge 2.0 is slirp-only and must refuse a non-loopback bind.

    Binding a LAN address only helps in bridge mode, and bridge mode requires
    the macOS firewall to be switched off entirely - the trade this version
    exists to avoid.
    """

    def test_loopback_accepted(self):
        for host in ("127.0.0.1", "localhost", "::1", "127.0.1.5"):
            self.assertIsNone(check_bind_host(host), f"should accept {host}")

    def test_wildcard_refused(self):
        self.assertIsNotNone(check_bind_host("0.0.0.0"))

    def test_lan_address_refused(self):
        self.assertIsNotNone(check_bind_host("192.168.3.154"))

    def test_slirp_gateway_refused(self):
        """10.0.2.2 is the guest's view of the host, not a bindable address."""
        self.assertIsNotNone(check_bind_host("10.0.2.2"))

    def test_refusal_explains_the_alternative(self):
        """The message has to say where to go, not just what is forbidden."""
        message = check_bind_host("0.0.0.0")
        self.assertIn("AppleBridge", message)
        self.assertIn("slirp", message)


class TestFilenameValidation(unittest.TestCase):
    """Test filename sanitization."""

    def test_safe_filename(self):
        """Test that safe filenames pass through."""
        import re
        filename = "test_file.txt"
        result = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        self.assertEqual(filename, result)

    def test_dangerous_chars_removed(self):
        """Test that dangerous characters are replaced."""
        import re
        filename = "test/file\\name.txt"
        result = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        self.assertEqual("test_file_name.txt", result)

    def test_spaces_replaced(self):
        """Test that spaces are replaced."""
        import re
        filename = "test file name.txt"
        result = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        self.assertEqual("test_file_name.txt", result)

    def test_unicode_removed(self):
        """Test that Unicode characters are replaced."""
        import re
        filename = "tëst_fílé.txt"
        result = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        self.assertEqual("t_st_f_l_.txt", result)


class TestConfigLoading(unittest.TestCase):
    """Test configuration loading."""

    def test_default_config_structure(self):
        """Test that default CONFIG has expected structure."""
        self.assertIn("server", CONFIG)
        self.assertIn("claude", CONFIG)
        self.assertIn("jobs", CONFIG)
        self.assertIn("files", CONFIG)
        self.assertIn("history", CONFIG)
        self.assertIn("logging", CONFIG)
        self.assertIn("proxy", CONFIG)

    def test_config_values(self):
        """Test that config values have correct types."""
        self.assertIsInstance(CONFIG["server"]["port"], int)
        self.assertIsInstance(CONFIG["server"]["host"], str)
        self.assertIsInstance(CONFIG["claude"]["max_tokens"], int)
        self.assertIsInstance(CONFIG["jobs"]["timeout"], int)

    def test_ssrf_protection_on_by_default(self):
        """The proxy must not ship as an open relay."""
        self.assertTrue(CONFIG["proxy"]["block_private_networks"])


class TestFileManagement(unittest.TestCase):
    """Test file management functions."""

    def setUp(self):
        """Create temporary directory with test files and point CONFIG at it."""
        self.test_dir = tempfile.mkdtemp()
        self.test_file = Path(self.test_dir) / "test.txt"
        self.test_file.write_text("Hello World", encoding='utf-8')
        self.original_shared = CONFIG["files"]["shared_folder"]
        CONFIG["files"]["shared_folder"] = self.test_dir

    def tearDown(self):
        """Restore config and clean up temporary directory."""
        CONFIG["files"]["shared_folder"] = self.original_shared
        shutil.rmtree(self.test_dir)

    def test_read_shared_file_valid(self):
        """Test reading a valid file."""
        content = read_shared_file("test.txt")
        self.assertIsNotNone(content)
        self.assertEqual("Hello World", content)

    def test_read_shared_file_invalid(self):
        """Test reading with path traversal attempt."""
        content = read_shared_file("../../../etc/passwd")
        self.assertIsNone(content)

    def test_save_shared_file_valid(self):
        """Test saving a valid file."""
        result = save_shared_file("output.txt", "Test Content")
        self.assertTrue(result)

        saved_file = Path(self.test_dir) / "output.txt"
        self.assertTrue(saved_file.exists())
        self.assertEqual("Test Content", saved_file.read_text())

    def test_save_shared_file_invalid(self):
        """Test saving with path traversal attempt."""
        result = save_shared_file("../../../tmp/evil.txt", "Evil")
        self.assertFalse(result)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
