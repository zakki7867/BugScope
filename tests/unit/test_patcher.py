"""Unit tests for deterministic unified diff patcher."""

import pytest
from pathlib import Path

from app.services.patcher import (
    PatchError,
    apply_patch_to_directory,
    parse_unified_diff,
)


@pytest.fixture
def target_repo(tmp_path):
    """Create a temporary project file for patching."""
    src_dir = tmp_path / "app"
    src_dir.mkdir()
    code = """
def calc_discount(price, rate):
    return price * (1 - rate)
"""
    (src_dir / "pricing.py").write_text(code.strip(), encoding="utf-8")
    return tmp_path


def test_parse_unified_diff():
    """Test parsing a standard unified diff string."""
    diff = """
--- a/app/pricing.py
+++ b/app/pricing.py
@@ -1,2 +1,2 @@
 def calc_discount(price, rate):
-    return price * (1 - rate)
+    return price * (1 - float(rate))
"""
    patches = parse_unified_diff(diff)
    assert "app/pricing.py" in patches
    hunks = patches["app/pricing.py"]
    assert len(hunks) == 1
    old_l, new_l = hunks[0]
    assert any("1 - rate" in l for l in old_l)
    assert any("float(rate)" in l for l in new_l)


def test_apply_patch_successfully(target_repo):
    """Test applying a valid patch modifies file correctly."""
    diff = """
--- a/app/pricing.py
+++ b/app/pricing.py
@@ -1,2 +1,2 @@
 def calc_discount(price, rate):
-    return price * (1 - rate)
+    return price * (1 - float(rate))
"""
    modified = apply_patch_to_directory(str(target_repo), diff)
    assert len(modified) == 1
    assert "pricing.py" in modified[0]

    updated = (target_repo / "app" / "pricing.py").read_text(encoding="utf-8")
    assert "float(rate)" in updated


def test_apply_patch_invalid_target_file(target_repo):
    """Test PatchError raised when diff targets non-existent file."""
    diff = """
--- a/app/nonexistent.py
+++ b/app/nonexistent.py
@@ -1,1 +1,1 @@
-old
+new
"""
    with pytest.raises(PatchError) as exc_info:
        apply_patch_to_directory(str(target_repo), diff)
    assert "not found" in str(exc_info.value).lower()
