"""Code search and pattern matching tools for BugScope."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def search_code(
    repo_path: Path,
    query: str,
    file_pattern: Optional[str] = None,
    max_results: int = 20,
    case_sensitive: bool = False,
) -> List[Dict[str, Any]]:
    """Search for string or regex query across files in the repository.

    Args:
        repo_path: Root path of the repository.
        query: Substring or regular expression pattern.
        file_pattern: Optional glob pattern, e.g. '*.py'. Defaults to '*.py'.
        max_results: Maximum number of matches to return.
        case_sensitive: Whether match should be case-sensitive.

    Returns:
        List of dicts: {"file": rel_path, "line": line_no, "content": stripped_line}
    """
    pattern_glob = file_pattern or "*.py"
    flags = 0 if case_sensitive else re.IGNORECASE

    try:
        regex = re.compile(query, flags)
    except re.error:
        # Fallback to literal search if invalid regex
        regex = re.compile(re.escape(query), flags)

    results: List[Dict[str, Any]] = []

    for file_path in repo_path.rglob(pattern_glob):
        if not file_path.is_file():
            continue
        # Skip git, cache, and venv dirs
        parts = file_path.parts
        if any(p.startswith(".") or p in ("venv", "node_modules", "__pycache__") for p in parts):
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        rel_path = str(file_path.relative_to(repo_path)).replace("\\", "/")
        for line_no, line in enumerate(content.splitlines(), start=1):
            if regex.search(line):
                results.append({
                    "file": rel_path,
                    "line": line_no,
                    "content": line.strip(),
                })
                if len(results) >= max_results:
                    return results

    return results
