"""Deterministic unified diff patch application utility.

Applies standard unified diffs to files on disk without relying on external patch binaries.
Safe, robust, and supports standard unified diff format (with or without a/ b/ prefixes).
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class PatchError(Exception):
    """Raised when a patch cannot be cleanly applied."""
    pass


class DiffResult:
    """Result of an in-memory unified diff application."""
    def __init__(
        self,
        success: bool,
        patched_content: str,
        error_message: Optional[str] = None,
        applied_hunks: int = 0,
    ):
        self.success = success
        self.patched_content = patched_content
        self.error_message = error_message
        self.applied_hunks = applied_hunks


def apply_unified_diff(content: str, diff_text: str) -> DiffResult:
    """Apply a unified diff directly to an in-memory string.

    Returns:
        DiffResult with patched_content and success flag.
    """
    if not diff_text.strip():
        return DiffResult(False, content, "Empty diff.")

    patches = parse_unified_diff(diff_text)
    if not patches:
        return DiffResult(False, content, "Failed parsing diff hunks.")

    current_content = content
    hunks_count = 0

    for _, hunks in patches.items():
        for old_lines, new_lines in hunks:
            old_str = "\n".join(old_lines)
            new_str = "\n".join(new_lines)

            if old_str in current_content:
                current_content = current_content.replace(old_str, new_str, 1)
                hunks_count += 1
                continue

            # Whitespace-relaxed match
            lines = current_content.splitlines()
            old_norm = [re.sub(r"\s+", " ", l).strip() for l in old_lines if l.strip()]
            matched = False

            if old_norm:
                for idx in range(len(lines) - len(old_norm) + 1):
                    window = [
                        re.sub(r"\s+", " ", lines[idx + k]).strip()
                        for k in range(len(old_norm))
                    ]
                    if window == old_norm:
                        before = lines[:idx]
                        after = lines[idx + len(old_norm) :]
                        current_content = "\n".join(before + new_lines + after)
                        matched = True
                        hunks_count += 1
                        break

            if not matched:
                return DiffResult(False, content, f"Could not locate hunk: {old_str[:100]}...")

    return DiffResult(True, current_content, None, hunks_count)



def parse_unified_diff(diff_text: str) -> Dict[str, List[Tuple[List[str], List[str]]]]:
    """Parse unified diff text into a mapping of file_path -> list of (old_lines, new_lines)."""
    file_patches: Dict[str, List[Tuple[List[str], List[str]]]] = {}
    current_file: Optional[str] = None
    current_hunks: List[Tuple[List[str], List[str]]] = []
    old_hunk: List[str] = []
    new_hunk: List[str] = []
    in_hunk = False

    lines = diff_text.strip().splitlines()

    for line in lines:
        if line.startswith("--- "):
            continue
        elif line.startswith("+++ "):
            # Save previous file hunks if any
            if current_file and (old_hunk or new_hunk):
                current_hunks.append((old_hunk, new_hunk))
                file_patches[current_file] = current_hunks
                old_hunk, new_hunk = [], []
                current_hunks = []

            # Extract target file path (strip +++ b/ or +++ )
            raw_path = line[4:].strip()
            if raw_path.startswith("b/"):
                raw_path = raw_path[2:]
            current_file = raw_path.replace("\\", "/").strip().lstrip("/")
            current_hunks = []
            in_hunk = False

        elif line.startswith("@@"):
            if in_hunk and (old_hunk or new_hunk):
                current_hunks.append((old_hunk, new_hunk))
                old_hunk, new_hunk = [], []
            in_hunk = True

        elif in_hunk and current_file:
            if line.startswith("-"):
                old_hunk.append(line[1:])
            elif line.startswith("+"):
                new_hunk.append(line[1:])
            elif line.startswith(" "):
                # Context line present in both
                old_hunk.append(line[1:])
                new_hunk.append(line[1:])

    if current_file:
        if old_hunk or new_hunk:
            current_hunks.append((old_hunk, new_hunk))
        if current_hunks:
            file_patches[current_file] = current_hunks

    return file_patches


DANGEROUS_PATTERNS = [
    (re.compile(r"\b(eval|exec)\s*\("), "Dynamic code execution (eval/exec) prohibited."),
    (re.compile(r"\bos\.system\s*\("), "Direct shell command execution (os.system) prohibited."),
    (re.compile(r"\bsubprocess\.(Popen|call|run|check_call|check_output)\s*\([^)]*shell\s*=\s*True"), "Shell=True subprocess execution prohibited."),
    (re.compile(r"\bshutil\.rmtree\s*\(\s*['\"]/['\"]"), "Destructive root filesystem operation prohibited."),
]


def validate_patch_safety(diff_text: str) -> None:
    """Enforce strict patch safety invariants:

    1. Never modify existing test files (prevents making tests pass by altering assertions).
    2. Path traversal rejection (no .. or escaping repository).
    3. Rejection of unsafe or dangerous execution constructs (eval, exec, shell=True).
    """
    if not diff_text.strip():
        raise PatchError("Diff text is empty.")

    patches = parse_unified_diff(diff_text)
    if not patches:
        raise PatchError("Could not parse any valid hunks from unified diff.")

    for rel_p, hunks in patches.items():
        clean_p = rel_p.lower().replace("\\", "/")

        # 1. Reject edits to existing test files
        if "test_" in clean_p or "_test.py" in clean_p or clean_p.startswith("tests/") or "/tests/" in clean_p:
            raise PatchError(
                f"Patch safety violation: Patch is not permitted to edit existing test file '{rel_p}'. "
                "Fixes must resolve issues in application source code, not by altering test assertions."
            )

        # 2. Reject path traversal
        if ".." in clean_p.split("/") or clean_p.startswith("/"):
            raise PatchError(f"Patch safety violation: Path traversal detected in '{rel_p}'.")

        # 3. Check added lines for dangerous operations
        for _, new_lines in hunks:
            for line in new_lines:
                for pattern, reason in DANGEROUS_PATTERNS:
                    if pattern.search(line):
                        raise PatchError(f"Patch safety violation in added line '{line.strip()}': {reason}")


def apply_patch_to_directory(repo_dir: str, diff_text: str) -> List[str]:
    """Apply a unified diff patch to files in repo_dir with atomic rollback.

    If any hunk fails or an error occurs, all modified files are automatically rolled back
    to their exact pre-patch state.

    Args:
        repo_dir: Absolute path of repository.
        diff_text: Unified diff string.

    Returns:
        List of modified file relative paths.

    Raises:
        PatchError: If patch safety check fails or patch cannot be applied cleanly.
    """
    validate_patch_safety(diff_text)

    patches = parse_unified_diff(diff_text)
    repo_path = Path(repo_dir).resolve()

    # Pre-flight: verify and back up all target files before modifying anything
    backup_contents: Dict[Path, str] = {}
    resolved_targets: Dict[str, Path] = {}

    for rel_path in patches.keys():
        target_path = (repo_path / rel_path).resolve()
        try:
            target_path.relative_to(repo_path)
        except ValueError as exc:
            raise PatchError(f"Target path '{rel_path}' escapes repository boundary.") from exc

        if not target_path.is_file():
            candidates = list(repo_path.rglob(Path(rel_path).name))
            if candidates:
                target_path = candidates[0]
            else:
                raise PatchError(f"Target file for patch not found on disk: {rel_path}")

        try:
            backup_contents[target_path] = target_path.read_text(encoding="utf-8", errors="replace")
            resolved_targets[rel_path] = target_path
        except Exception as exc:
            raise PatchError(f"Could not read {target_path} for pre-patch backup: {exc}") from exc

    modified_files: List[str] = []

    try:
        for rel_path, hunks in patches.items():
            target_path = resolved_targets[rel_path]
            content = backup_contents[target_path]

            # Apply each hunk sequentially
            for old_lines, new_lines in hunks:
                old_str = "\n".join(old_lines)
                new_str = "\n".join(new_lines)

                # 1. Exact match attempt
                if old_str in content:
                    content = content.replace(old_str, new_str, 1)
                    continue

                # 2. Whitespace-relaxed match attempt
                lines = content.splitlines()
                old_norm = [re.sub(r"\s+", " ", l).strip() for l in old_lines if l.strip()]
                matched = False

                if old_norm:
                    for idx in range(len(lines) - len(old_norm) + 1):
                        window = [
                            re.sub(r"\s+", " ", lines[idx + k]).strip()
                            for k in range(len(old_norm))
                        ]
                        if window == old_norm:
                            before = lines[:idx]
                            after = lines[idx + len(old_norm) :]
                            content = "\n".join(before + new_lines + after)
                            matched = True
                            break

                if not matched:
                    raise PatchError(
                        f"Hunk target could not be located in {rel_path}:\nOld lines:\n{old_str}"
                    )

            target_path.write_text(content, encoding="utf-8")
            rel_saved = target_path.relative_to(repo_path).as_posix()
            modified_files.append(rel_saved)

        return modified_files

    except Exception:
        # Atomic rollback: restore every file to its pre-patch state
        for t_path, orig_text in backup_contents.items():
            try:
                t_path.write_text(orig_text, encoding="utf-8")
            except Exception:
                pass
        raise
