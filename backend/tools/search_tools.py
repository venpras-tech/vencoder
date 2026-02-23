from pathlib import Path
import re
from langchain_core.tools import tool
from config import WORKSPACE_ROOT


def _resolve(path: str) -> Path:
    p = (WORKSPACE_ROOT / path).resolve()
    if not str(p).startswith(str(WORKSPACE_ROOT.resolve())):
        raise PermissionError("Path outside workspace")
    return p


@tool
def grep_search(pattern: str, path: str = ".", recursive: bool = True) -> str:
    """Search for a regex pattern in files. path: directory or file relative to workspace. recursive: search subdirs."""
    root = _resolve(path)
    if root.is_file():
        files = [root]
    else:
        files = list(root.rglob("*")) if recursive else list(root.glob("*"))
        files = [f for f in files if f.is_file()]
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"Invalid regex: {e}"
    results = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    rel = f.relative_to(WORKSPACE_ROOT)
                    results.append(f"{rel}:{i}: {line.strip()}")
        except Exception:
            continue
    return "\n".join(results[:200]) if results else "No matches"


@tool
def glob_search(pattern: str, path: str = ".") -> str:
    """Find files matching a glob pattern (e.g. '**/*.py'). path: directory relative to workspace."""
    root = _resolve(path)
    if not root.is_dir():
        return f"Error: not a directory: {path}"
    matches = list(root.glob(pattern))
    paths = [str(m.relative_to(WORKSPACE_ROOT)) for m in matches if m.is_file()]
    return "\n".join(paths[:500]) if paths else "No matches"
