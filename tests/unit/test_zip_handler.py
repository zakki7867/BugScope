"""Unit tests for safe ZIP archive extraction and security filters."""

import io
import stat
import zipfile
import pytest
from pathlib import Path

from app.services.zip_handler import (
    ZipSecurityError,
    extract_zip_safely,
    should_ignore_entry,
)


def _make_zip(files: dict) -> bytes:
    """Helper to build in-memory zip bytes from a dict of {filename: content}."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_safe_zip_extraction(tmp_path):
    """Test extracting a normal zip file safely."""
    files = {
        "app/main.py": "print('hello')",
        "app/utils.py": "def add(a, b): return a + b",
        "README.md": "# Sample Project",
    }
    zip_bytes = _make_zip(files)
    extracted = extract_zip_safely(zip_bytes, str(tmp_path))

    assert "app/main.py" in extracted
    assert "app/utils.py" in extracted
    assert "README.md" in extracted
    assert (tmp_path / "app" / "main.py").read_text() == "print('hello')"


def test_zip_slip_traversal_rejection(tmp_path):
    """Test that archive attempting path traversal is strictly rejected."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        # Add entry with path traversal
        zf.writestr("../outside.txt", "malicious payload")
    zip_bytes = buf.getvalue()

    with pytest.raises(ZipSecurityError) as exc_info:
        extract_zip_safely(zip_bytes, str(tmp_path))
    assert "traversal" in str(exc_info.value).lower()


def test_ignore_sensitive_and_binary_entries(tmp_path):
    """Test that .git, node_modules, .env, and binary files are filtered out."""
    files = {
        "valid.py": "x = 1",
        ".git/config": "secret git data",
        "node_modules/pkg/index.js": "js code",
        ".env": "SECRET_KEY=12345",
        "app/cache.pyc": b"\x00\x01\x02",
        "lib/native.so": b"\x7fELF",
    }
    zip_bytes = _make_zip(files)
    extracted = extract_zip_safely(zip_bytes, str(tmp_path))

    assert "valid.py" in extracted
    assert len(extracted) == 1
    assert not (tmp_path / ".git").exists()
    assert not (tmp_path / ".env").exists()
    assert not (tmp_path / "node_modules").exists()


def test_file_count_cap_rejection(tmp_path):
    """Test that archives exceeding the file count limit are rejected."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for i in range(1005):
            zf.writestr(f"file_{i}.txt", "data")
    zip_bytes = buf.getvalue()

    with pytest.raises(ZipSecurityError) as exc_info:
        extract_zip_safely(zip_bytes, str(tmp_path))
    assert "limit" in str(exc_info.value).lower()
