"""Safe ZIP archive handling and extraction service.

Enforces strict security checks:
1. Max 20 MB archive size.
2. Max 1,000 file count cap.
3. Strict path traversal rejection (Zip Slip defense).
4. Rejection of symlinks and hardlinks.
5. Exclusion of sensitive directories, virtual environments, .env files, and binary artifacts.
6. Extraction only into isolated temporary directories.
"""

import io
import os
import stat
import tempfile
import zipfile
from pathlib import Path
from typing import List, Set

MAX_ZIP_BYTES = 20 * 1024 * 1024  # 20 MB
MAX_FILE_COUNT = 1000

# Directories and patterns to ignore during extraction
IGNORED_DIR_NAMES = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env_dir",
    "__pycache__",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
}

# Binary file extensions to ignore
IGNORED_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dll",
    ".dylib",
    ".exe",
    ".bin",
    ".whl",
    ".tar",
    ".gz",
    ".zip",
    ".rar",
    ".7z",
    ".iso",
    ".sqlite",
    ".sqlite3",
    ".db",
}


class ZipSecurityError(Exception):
    """Raised when an uploaded zip violates safety policies."""
    pass


def is_symlink(info: zipfile.ZipInfo) -> bool:
    """Check if a ZipInfo entry is a symbolic link."""
    # The upper 16 bits of external_attr store POSIX file mode bits
    mode = info.external_attr >> 16
    return stat.S_ISLNK(mode)


def should_ignore_entry(filename: str) -> bool:
    """Determine if an archive entry should be excluded from extraction."""
    normalized = filename.replace("\\", "/").strip("/")
    parts = normalized.split("/")

    # Check for excluded directory components
    for part in parts:
        if part in IGNORED_DIR_NAMES:
            return True

    base_name = parts[-1].lower() if parts else ""
    # Reject .env files
    if base_name == ".env" or base_name.startswith(".env."):
        return True

    # Check for binary extension
    suffix = Path(base_name).suffix.lower()
    if suffix in IGNORED_EXTENSIONS:
        return True

    return False


def extract_zip_safely(zip_data: bytes, target_dir: str) -> List[str]:
    """Extract zip bytes safely into target_dir after validating all security rules.

    Args:
        zip_data: Raw byte string of the uploaded ZIP file.
        target_dir: Absolute path of destination directory.

    Returns:
        List of extracted relative file paths.

    Raises:
        ZipSecurityError: If size, count, traversal, or symlink violations are found.
    """
    if len(zip_data) > MAX_ZIP_BYTES:
        raise ZipSecurityError(
            f"Archive size {len(zip_data)} bytes exceeds maximum allowed limit of {MAX_ZIP_BYTES} bytes (20 MB)."
        )

    try:
        archive = zipfile.ZipFile(io.BytesIO(zip_data))
    except zipfile.BadZipFile as exc:
        raise ZipSecurityError(f"Invalid or corrupted ZIP archive: {str(exc)}") from exc

    namelist = archive.namelist()
    if len(namelist) > MAX_FILE_COUNT:
        raise ZipSecurityError(
            f"Archive contains {len(namelist)} items, which exceeds the limit of {MAX_FILE_COUNT} files."
        )

    target_dir_path = Path(target_dir).resolve()
    extracted_files: List[str] = []

    with archive:
        for info in archive.infolist():
            raw_name = info.filename
            if should_ignore_entry(raw_name):
                continue

            # Reject symlinks
            if is_symlink(info):
                raise ZipSecurityError(f"Symlinks are prohibited in project archive: {raw_name}")

            # Normalize and guard against Zip Slip (directory traversal)
            resolved_dest = (target_dir_path / raw_name).resolve()
            try:
                # Path must be inside target_dir_path
                resolved_dest.relative_to(target_dir_path)
            except ValueError as exc:
                raise ZipSecurityError(
                    f"Path traversal detected: '{raw_name}' escapes destination directory."
                ) from exc

            # Skip directory entries themselves
            if info.is_dir():
                resolved_dest.mkdir(parents=True, exist_ok=True)
                continue

            # Ensure parent directories exist
            resolved_dest.parent.mkdir(parents=True, exist_ok=True)

            # Write file content safely
            with archive.open(info, "r") as src, open(resolved_dest, "wb") as dst:
                dst.write(src.read())

            rel_path = str(resolved_dest.relative_to(target_dir_path)).replace("\\", "/")
            extracted_files.append(rel_path)

    return extracted_files


def create_temp_repo_from_zip(zip_data: bytes) -> str:
    """Extract ZIP bytes into a new isolated temporary directory.

    Returns:
        Absolute path to the newly created temporary directory.
    """
    temp_dir = tempfile.mkdtemp(prefix="bugscope_repo_")
    try:
        extract_zip_safely(zip_data, temp_dir)
        return temp_dir
    except Exception:
        # Clean up directory if extraction fails
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
