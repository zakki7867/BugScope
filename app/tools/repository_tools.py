"""Repository analysis tools using Python AST and file inspection."""

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional


def _resolve_safe_path(repo_path: Path, relative_file_path: str) -> Optional[Path]:
    """Resolve file path ensuring it does not escape repo root."""
    resolved = (repo_path / relative_file_path).resolve()
    try:
        resolved.relative_to(repo_path.resolve())
    except ValueError:
        return None
    return resolved if resolved.is_file() else None


def get_file_content(
    repo_path: Path,
    file_path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> Dict[str, Any]:
    """Retrieve file content with line numbers within line range.

    Args:
        repo_path: Repository root.
        file_path: Relative path to file.
        start_line: 1-indexed starting line.
        end_line: 1-indexed ending line.

    Returns:
        Dict with keys: "file", "total_lines", "start_line", "end_line", "lines", "content"
    """
    target = _resolve_safe_path(repo_path, file_path)
    if not target:
        return {"error": f"File '{file_path}' not found or invalid."}

    try:
        raw = target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"error": f"Failed reading file: {e}"}

    all_lines = raw.splitlines()
    total = len(all_lines)

    start = max(1, start_line or 1)
    end = min(total, end_line or total)

    selected = all_lines[start - 1 : end]
    numbered_lines = [
        {"line_number": start + idx, "code": line}
        for idx, line in enumerate(selected)
    ]

    return {
        "file": file_path.replace("\\", "/"),
        "total_lines": total,
        "start_line": start,
        "end_line": end,
        "lines": numbered_lines,
        "content": "\n".join(selected),
    }


def get_function_info(
    repo_path: Path, file_path: str, function_name: str
) -> Dict[str, Any]:
    """Extract AST information for a specified function."""
    target = _resolve_safe_path(repo_path, file_path)
    if not target:
        return {"error": f"File '{file_path}' not found."}

    try:
        source = target.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(target))
    except Exception as e:
        return {"error": f"AST parse failed: {e}"}

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == function_name:
                args = [a.arg for a in node.args.args]
                decorators = [
                    ast.unparse(d) if hasattr(ast, "unparse") else getattr(d, "id", "")
                    for d in node.decorator_list
                ]
                docstring = ast.get_docstring(node)
                end_lineno = getattr(node, "end_lineno", node.lineno)
                lines = source.splitlines()[node.lineno - 1 : end_lineno]
                body_source = "\n".join(lines)

                return {
                    "name": node.name,
                    "file": file_path.replace("\\", "/"),
                    "start_line": node.lineno,
                    "end_line": end_lineno,
                    "arguments": args,
                    "decorators": decorators,
                    "docstring": docstring,
                    "code": body_source,
                }

    return {"error": f"Function '{function_name}' not found in '{file_path}'."}


def get_class_info(
    repo_path: Path, file_path: str, class_name: str
) -> Dict[str, Any]:
    """Extract AST information for a specified class."""
    target = _resolve_safe_path(repo_path, file_path)
    if not target:
        return {"error": f"File '{file_path}' not found."}

    try:
        source = target.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(target))
    except Exception as e:
        return {"error": f"AST parse failed: {e}"}

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if node.name == class_name:
                bases = [
                    ast.unparse(b) if hasattr(ast, "unparse") else getattr(b, "id", "")
                    for b in node.bases
                ]
                methods = [
                    n.name
                    for n in node.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                docstring = ast.get_docstring(node)
                end_lineno = getattr(node, "end_lineno", node.lineno)
                lines = source.splitlines()[node.lineno - 1 : end_lineno]
                body_source = "\n".join(lines)

                return {
                    "name": node.name,
                    "file": file_path.replace("\\", "/"),
                    "start_line": node.lineno,
                    "end_line": end_lineno,
                    "bases": bases,
                    "methods": methods,
                    "docstring": docstring,
                    "code": body_source,
                }

    return {"error": f"Class '{class_name}' not found in '{file_path}'."}


def find_related_tests(
    repo_path: Path, path_or_symbol: str
) -> List[Dict[str, Any]]:
    """Locate tests referencing a module or symbol."""
    results: List[Dict[str, Any]] = []
    symbol = Path(path_or_symbol).stem

    for test_file in repo_path.rglob("test_*.py"):
        if not test_file.is_file():
            continue
        try:
            content = test_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        rel_path = str(test_file.relative_to(repo_path)).replace("\\", "/")
        if symbol.lower() in content.lower():
            try:
                tree = ast.parse(content)
                matching_funcs = []
                for n in ast.walk(tree):
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_"):
                        matching_funcs.append(n.name)
            except Exception:
                matching_funcs = []

            results.append({
                "test_file": rel_path,
                "matching_tests": matching_funcs,
                "references_count": content.lower().count(symbol.lower()),
            })

    return results


def dependency_analysis(repo_path: Path, file_path: str) -> Dict[str, Any]:
    """Analyze imports in a file distinguishing internal vs external dependencies."""
    target = _resolve_safe_path(repo_path, file_path)
    if not target:
        return {"error": f"File '{file_path}' not found."}

    try:
        source = target.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except Exception as e:
        return {"error": f"AST parse failed: {e}"}

    internal_imports: List[str] = []
    external_imports: List[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                if (repo_path / f"{mod}.py").exists() or (repo_path / mod).is_dir():
                    internal_imports.append(alias.name)
                else:
                    external_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod = node.module.split(".")[0]
                if node.level > 0 or (repo_path / f"{mod}.py").exists() or (repo_path / mod).is_dir():
                    internal_imports.append(node.module)
                else:
                    external_imports.append(node.module)

    return {
        "file": file_path.replace("\\", "/"),
        "internal_dependencies": sorted(list(set(internal_imports))),
        "external_dependencies": sorted(list(set(external_imports))),
    }
