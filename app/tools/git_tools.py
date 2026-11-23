"""Git history and diff analysis tools."""

import subprocess
from pathlib import Path
from typing import Any, Dict, List


def git_history(
    repo_path: Path, file_path: str, max_commits: int = 5
) -> List[Dict[str, Any]]:
    """Retrieve recent git commit history for a specified file.

    Returns:
        List of dicts: {"commit": hash, "author": author, "date": date, "message": message}
    """
    if not (repo_path / ".git").exists():
        return []

    try:
        cmd = [
            "git",
            "-C",
            str(repo_path),
            "log",
            f"-n{max_commits}",
            "--pretty=format:%H|%an|%ad|%s",
            "--date=short",
            "--",
            file_path,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode != 0:
            return []

        commits = []
        for line in res.stdout.strip().splitlines():
            if not line:
                continue
            parts = line.split("|", 3)
            if len(parts) == 4:
                commits.append({
                    "commit": parts[0][:8],
                    "author": parts[1],
                    "date": parts[2],
                    "message": parts[3],
                })
        return commits
    except Exception:
        return []
