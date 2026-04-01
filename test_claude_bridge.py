#!/usr/bin/env python3
"""
Unit Tests for Claude Bridge Server
====================================
Tests critical security and functionality components.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
import sys
import os

# Add parent directory to path to import claude_bridge
sys.path.insert(0, os.path.dirname(__file__))

# Import after path setup
import claude_bridge


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
        result = claude_bridge.validate_safe_path(self.test_dir, "test.txt")
        self.assertIsNotNone(result)
        self.assertTrue(str(result).startswith(str(Path(self.test_dir).resolve())))

    def test_subdirectory_path(self):
        """Test that subdirectory paths are accepted."""
        result = claude_bridge.validate_safe_path(self.test_dir, "subdir/test.txt")
        self.assertIsNotNone(result)

    def test_path_traversal_parent(self):
        """Test that ../ path traversal is blocked."""
        result = claude_bridge.validate_safe_path(self.test_dir, "../etc/passwd")
        self.assertIsNone(result)

    def test_path_traversal_absolute(self):
        """Test that absolute paths outside base are blocked."""
        result = claude_bridge.validate_safe_path(self.test_dir, "/etc/passwd")
        self.assertIsNone(result)

    def test_path_traversal_multiple(self):
        """Test that multiple ../ are blocked."""
        result = claude_bridge.validate_safe_path(self.test_dir, "../../../../../../etc/passwd")
        self.assertIsNone(result)

    def test_path_traversal_sneaky(self):
        """Test sneaky path traversal attempts."""
        result = claude_bridge.validate_safe_path(self.test_dir, "subdir/../../etc/passwd")
        self.assertIsNone(result)


class TestSanitization(unittest.TestCase):
    """Test character sanitization for ISO-8859-1."""

    def test_ascii_passthrough(self):
        """Test that ASCII characters pass through unchanged."""
        text = "Hello World 123"
        result = claude_bridge.sanitize(text)
        self.assertEqual(text, result)

    def test_german_umlauts(self):
        """Test that German umlauts are preserved (they exist in ISO-8859-1)."""
        text = "äöüÄÖÜß"
        result = claude_bridge.sanitize(text)
        self.assertEqual(text, result)

    def test_unicode_quotes_replaced(self):
        """Test that Unicode quotes are replaced with ASCII."""
        text = "\u201cHello\u201d \u2018World\u2019"  # Unicode quotes
        result = claude_bridge.sanitize(text)
        self.assertIn('"', result)
        self.assertIn("'", result)
        self.assertNotIn("\u201c", result)  # left double quote
        self.assertNotIn("\u2018", result)  # left single quote

    def test_unicode_dashes_replaced(self):
        """Test that Unicode dashes are replaced with ASCII."""
        text = "Hello\u2014World\u2013Test"  # em-dash and en-dash
        result = claude_bridge.sanitize(text)
        self.assertIn("-", result)
        self.assertNotIn("\u2014", result)  # em-dash
        self.assertNotIn("\u2013", result)  # en-dash

    def test_emoji_removed(self):
        """Test that emojis are replaced with ?."""
        text = "Hello \U0001f916 World"  # robot emoji
        result = claude_bridge.sanitize(text)
        self.assertNotIn("\U0001f916", result)
        self.assertIn("?", result)

    def test_mixed_content(self):
        """Test mixed ASCII, umlauts, and Unicode."""
        text = "Hällo\u2014Wörld \u201cTest\u201d \U0001f680"  # em-dash, quotes, rocket emoji
        result = claude_bridge.sanitize(text)
        self.assertIn("Hällo", result)
        self.assertIn("Wörld", result)
        self.assertIn("-", result)  # em-dash should be replaced with dash
        self.assertIn('"', result)  # Unicode quotes should be replaced


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
        self.assertIn("server", claude_bridge.CONFIG)
        self.assertIn("claude", claude_bridge.CONFIG)
        self.assertIn("jobs", claude_bridge.CONFIG)
        self.assertIn("files", claude_bridge.CONFIG)
        self.assertIn("history", claude_bridge.CONFIG)
        self.assertIn("logging", claude_bridge.CONFIG)

    def test_config_values(self):
        """Test that config values have correct types."""
        self.assertIsInstance(claude_bridge.CONFIG["server"]["port"], int)
        self.assertIsInstance(claude_bridge.CONFIG["server"]["host"], str)
        self.assertIsInstance(claude_bridge.CONFIG["claude"]["max_tokens"], int)
        self.assertIsInstance(claude_bridge.CONFIG["jobs"]["timeout"], int)


class TestFileManagement(unittest.TestCase):
    """Test file management functions."""

    def setUp(self):
        """Create temporary directory with test files."""
        self.test_dir = tempfile.mkdtemp()
        # Create test file
        self.test_file = Path(self.test_dir) / "test.txt"
        self.test_file.write_text("Hello World", encoding='utf-8')

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir)

    def test_read_shared_file_valid(self):
        """Test reading a valid file."""
        # Set shared folder
        original_shared = claude_bridge.SHARED_FOLDER
        claude_bridge.SHARED_FOLDER = self.test_dir

        content = claude_bridge.read_shared_file("test.txt")
        self.assertIsNotNone(content)
        self.assertEqual("Hello World", content)

        # Restore
        claude_bridge.SHARED_FOLDER = original_shared

    def test_read_shared_file_invalid(self):
        """Test reading with path traversal attempt."""
        original_shared = claude_bridge.SHARED_FOLDER
        claude_bridge.SHARED_FOLDER = self.test_dir

        content = claude_bridge.read_shared_file("../../../etc/passwd")
        self.assertIsNone(content)

        claude_bridge.SHARED_FOLDER = original_shared

    def test_save_shared_file_valid(self):
        """Test saving a valid file."""
        original_shared = claude_bridge.SHARED_FOLDER
        claude_bridge.SHARED_FOLDER = self.test_dir

        result = claude_bridge.save_shared_file("output.txt", "Test Content")
        self.assertTrue(result)

        # Verify file was created
        saved_file = Path(self.test_dir) / "output.txt"
        self.assertTrue(saved_file.exists())
        self.assertEqual("Test Content", saved_file.read_text())

        claude_bridge.SHARED_FOLDER = original_shared

    def test_save_shared_file_invalid(self):
        """Test saving with path traversal attempt."""
        original_shared = claude_bridge.SHARED_FOLDER
        claude_bridge.SHARED_FOLDER = self.test_dir

        result = claude_bridge.save_shared_file("../../../tmp/evil.txt", "Evil")
        self.assertFalse(result)

        claude_bridge.SHARED_FOLDER = original_shared


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
