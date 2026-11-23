"""Deterministic repository investigator node.

Analyzes the local or extracted repository:
1. Builds a clean repository file tree.
2. Parses Python code with ast to identify enclosing functions/classes at the crash line.
3. Discovers callees (functions called by the failing symbol).
4. Scans the codebase for callers invoking the failing symbol.
5. Identifies related test files.
6. Slices formatted, line-numbered code snippets constrained to a token budget.
No LLM calls are made in this node.
"""

import ast
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from app.schemas.context import ContextBundle, Snippet
from app.schemas.failure import FailureReport

# Approximate token-to-character ratio
CHARS_PER_TOKEN = 4


class FunctionVisitor(ast.NodeVisitor):
    """AST visitor to locate functions and classes covering a target line."""

    def __init__(self, target_line: int):
        self.target_line = target_line
        self.target_node: Optional[ast.AST] = None
        self.target_name: Optional[str] = None
        self.enclosing_class: Optional[str] = None

    def visit_ClassDef(self, node: ast.ClassDef):
        if hasattr(node, "end_lineno") and node.lineno <= self.target_line <= node.end_lineno:
            self.enclosing_class = node.name
            self.generic_visit(node)
            if self.target_node is None:
                self.target_node = node
                self.target_name = node.name
        else:
            self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._check_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._check_func(node)

    def _check_func(self, node: ast.AST):
        lineno = getattr(node, "lineno", 0)
        end_lineno = getattr(node, "end_lineno", lineno)
        if lineno <= self.target_line <= end_lineno:
            self.target_node = node
            func_name = getattr(node, "name", "<anonymous>")
            if self.enclosing_class:
                self.target_name = f"{self.enclosing_class}.{func_name}"
            else:
                self.target_name = func_name
        self.generic_visit(node)


class CalleeVisitor(ast.NodeVisitor):
    """AST visitor to extract function call names inside an AST node."""

    def __init__(self):
        self.callees: Set[str] = set()

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            self.callees.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.callees.add(node.func.attr)
        self.generic_visit(node)


def build_file_tree(repo_path: Path) -> List[str]:
    """Return a sorted list of relative paths for all files in repo_path."""
    tree: List[str] = []
    for item in sorted(repo_path.rglob("*")):
        if item.is_file():
            # Skip hidden files and cache folders
            rel = item.relative_to(repo_path).as_posix()
            parts = rel.split("/")
            if any(p.startswith(".") or p == "__pycache__" for p in parts):
                continue
            tree.append(rel)
    return tree


def find_failing_file_path(repo_path: Path, raw_file: str) -> Optional[Path]:
    """Resolve the reported failing file against the repository root."""
    clean_raw = raw_file.replace("\\", "/").strip().lstrip("/")

    # 1. Exact match relative to repo
    candidate = (repo_path / clean_raw).resolve()
    if candidate.is_file():
        return candidate

    # 2. Check by filename suffix (e.g. app/processor.py matching src/app/processor.py)
    for p in repo_path.rglob("*.py"):
        rel_posix = p.relative_to(repo_path).as_posix()
        if rel_posix.endswith(clean_raw) or clean_raw.endswith(rel_posix):
            return p

    # 3. Check by basename
    base = Path(clean_raw).name
    for p in repo_path.rglob(base):
        if p.is_file():
            return p

    return None


def format_numbered_snippet(
    lines: List[str], start_1idx: int, end_1idx: int
) -> str:
    """Format lines with line numbers for clean reading."""
    formatted = []
    for idx in range(start_1idx, min(end_1idx + 1, len(lines) + 1)):
        line_content = lines[idx - 1]
        formatted.append(f"{idx:4d} | {line_content}")
    return "\n".join(formatted)


def find_callers_across_repo(
    repo_path: Path, target_func: str, skip_file: Optional[Path] = None
) -> List[str]:
    """Scan all Python files in repo to find functions that invoke target_func."""
    callers: List[str] = []
    base_target = target_func.split(".")[-1]

    for py_file in repo_path.rglob("*.py"):
        if skip_file and py_file.resolve() == skip_file.resolve():
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError):
            continue

        rel_path = py_file.relative_to(repo_path).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call):
                        name = None
                        if isinstance(sub.func, ast.Name):
                            name = sub.func.id
                        elif isinstance(sub.func, ast.Attribute):
                            name = sub.func.attr
                        if name == base_target:
                            callers.append(f"{rel_path}::{node.name}")
                            break
    return sorted(list(set(callers)))


def find_related_test_files(
    repo_path: Path, failing_module_stem: str, target_symbol: Optional[str] = None
) -> List[str]:
    """Locate test files related to the failing module or symbol."""
    related: List[str] = []
    symbol_base = target_symbol.split(".")[-1] if target_symbol else None

    for py_file in repo_path.rglob("*.py"):
        rel_posix = py_file.relative_to(repo_path).as_posix()
        is_test = "test" in py_file.stem.lower() or "tests/" in rel_posix.lower()
        if not is_test:
            continue

        # Check if test file stem references failing module
        if failing_module_stem.lower() in py_file.stem.lower():
            related.append(rel_posix)
            continue

        # Check file content for mentions of target symbol or module
        if symbol_base:
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
                if symbol_base in content or failing_module_stem in content:
                    related.append(rel_posix)
            except Exception:
                continue

    return sorted(list(set(related)))


def repo_investigator(
    repo_dir: str,
    failure_report: FailureReport,
    token_budget: int = 8000,
) -> ContextBundle:
    """Deterministically investigate a repository to extract relevant context.

    Args:
        repo_dir: Absolute path of repository directory.
        failure_report: Parsed failure information from failure_analyzer.
        token_budget: Maximum token budget for extracted code snippets.

    Returns:
        ContextBundle with file tree, symbols, callers, callees, and snippets.
    """
    repo_path = Path(repo_dir).resolve()
    file_tree = build_file_tree(repo_path)
    max_chars = token_budget * CHARS_PER_TOKEN
    current_chars = 0
    snippets: List[Snippet] = []
    total_lines = 0

    failing_path = find_failing_file_path(repo_path, failure_report.file)
    failing_symbol: Optional[str] = None
    callees: List[str] = []
    callers: List[str] = []
    related_tests: List[str] = []

    if failing_path and failing_path.is_file():
        rel_failing = failing_path.relative_to(repo_path).as_posix()
        try:
            content = failing_path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            total_lines += len(lines)
            tree = ast.parse(content, filename=str(failing_path))

            visitor = FunctionVisitor(target_line=failure_report.line)
            visitor.visit(tree)

            if visitor.target_node:
                failing_symbol = visitor.target_name
                start_l = getattr(visitor.target_node, "lineno", 1)
                end_l = getattr(visitor.target_node, "end_lineno", len(lines))

                # Callee extraction
                callee_visitor = CalleeVisitor()
                callee_visitor.visit(visitor.target_node)
                callees = sorted(list(callee_visitor.callees))

                # Sliced snippet for the failing target
                snippet_code = format_numbered_snippet(lines, start_l, end_l)
                if current_chars + len(snippet_code) <= max_chars:
                    snippets.append(
                        Snippet(
                            file=rel_failing,
                            line_start=start_l,
                            line_end=end_l,
                            code=snippet_code,
                            is_target=True,
                        )
                    )
                    current_chars += len(snippet_code)
            else:
                # Fallback: slice 25 lines centered around target line
                start_l = max(1, failure_report.line - 12)
                end_l = min(len(lines), failure_report.line + 12)
                snippet_code = format_numbered_snippet(lines, start_l, end_l)
                if current_chars + len(snippet_code) <= max_chars:
                    snippets.append(
                        Snippet(
                            file=rel_failing,
                            line_start=start_l,
                            line_end=end_l,
                            code=snippet_code,
                            is_target=True,
                        )
                    )
                    current_chars += len(snippet_code)

            # Discover callers and related tests
            if failing_symbol:
                callers = find_callers_across_repo(repo_path, failing_symbol, skip_file=failing_path)
            related_tests = find_related_test_files(
                repo_path, failing_path.stem, failing_symbol
            )

        except (SyntaxError, UnicodeDecodeError):
            rel_failing = failure_report.file

    else:
        rel_failing = failure_report.file

    # Include related test snippets if budget permits
    for test_rel in related_tests:
        if current_chars >= max_chars:
            break
        test_file = repo_path / test_rel
        if test_file.is_file():
            try:
                t_content = test_file.read_text(encoding="utf-8", errors="replace")
                t_lines = t_content.splitlines()
                total_lines += len(t_lines)
                # Take up to the first 40 lines of the test file
                t_end = min(len(t_lines), 40)
                t_snippet = format_numbered_snippet(t_lines, 1, t_end)
                if current_chars + len(t_snippet) <= max_chars:
                    snippets.append(
                        Snippet(
                            file=test_rel,
                            line_start=1,
                            line_end=t_end,
                            code=t_snippet,
                            is_target=False,
                        )
                    )
                    current_chars += len(t_snippet)
            except Exception:
                continue

    return ContextBundle(
        file_tree=file_tree,
        failing_file=rel_failing,
        failing_symbol=failing_symbol,
        callers=callers,
        callees=callees,
        snippets=snippets,
        related_tests=related_tests,
        total_lines_inspected=total_lines,
    )
