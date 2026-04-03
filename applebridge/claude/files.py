"""
Shared Folder File Management
==============================

Handles file operations for the shared folder feature.
Includes path traversal protection.
"""

import logging
from pathlib import Path
from applebridge.config import CONFIG


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
    """List files in shared folder (or subfolder).

    Returns:
        List of dicts with 'name', 'is_dir', 'size' keys
    """
    shared_folder = CONFIG["files"]["shared_folder"]
    if not shared_folder:
        return []
    target = validate_safe_path(shared_folder, subfolder)
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
    """Read a file from shared folder.

    Tries mac_roman encoding first (Classic Mac files), then UTF-8.

    Returns:
        File contents as string, or None if error
    """
    shared_folder = CONFIG["files"]["shared_folder"]
    if not shared_folder:
        return None
    filepath = validate_safe_path(shared_folder, filename)
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
    """Save content to a file in shared folder.

    Args:
        filename: Filename (path traversal protected)
        content: File content as string

    Returns:
        True if successful, False otherwise
    """
    shared_folder = CONFIG["files"]["shared_folder"]
    if not shared_folder:
        return False
    filepath = validate_safe_path(shared_folder, filename)
    if not filepath:
        return False
    try:
        filepath.write_text(content, encoding="utf-8")
        return True
    except:
        return False
