import re
from langchain_core.tools import tool
from config import WORKSPACE_ROOT
from .path_utils import resolve_workspace_path


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for documentation, error messages, APIs, or general info. Use when you need up-to-date docs or to look up unknown errors."""
    if not query or not query.strip():
        return "Error: query is required"
    try:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            from ddgs import DDGS
        results = list(DDGS().text(query.strip(), max_results=max_results))
        if not results:
            return "No results found."
        out = []
        for r in results[:max_results]:
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            out.append(f"• {title}\n  {body}\n  {href}")
        return "\n\n".join(out)
    except ImportError:
        return "Web search requires duckduckgo-search. Install with: pip install duckduckgo-search"
    except Exception as e:
        return f"Web search failed: {e}"


@tool
def grep_search(pattern: str, path: str = ".", recursive: bool = True) -> str:
    """Search for a regex pattern in files. path: directory or file relative to workspace. recursive: search subdirs."""
    root = resolve_workspace_path(path)
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
    root = resolve_workspace_path(path)
    if not root.is_dir():
        return f"Error: not a directory: {path}"
    matches = list(root.glob(pattern))
    paths = [str(m.relative_to(WORKSPACE_ROOT)) for m in matches if m.is_file()]
    return "\n".join(paths[:500]) if paths else "No matches"
