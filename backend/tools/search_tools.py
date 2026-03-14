import re
import urllib.request
from langchain_core.tools import tool
from config import WORKSPACE_ROOT
from .path_utils import resolve_workspace_path


def _extract_text_from_html(html: str) -> str:
    html = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.I)
    html = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", html, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@tool
def scrape_url(url: str, max_chars: int = 25000) -> str:
    """Fetch a webpage and extract its text content. Use when the user shares a URL or asks to analyze a specific webpage (e.g. product pages, docs, articles). JavaScript-heavy sites may return partial content."""
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        return "Error: URL must start with http:// or https://"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; AICodec/1.0)"})
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="replace")
        text = _extract_text_from_html(html)
        if len(text) > max_chars:
            text = text[:max_chars] + "\n[... truncated ...]"
        return f"--- {url} ---\n\n{text}" if text else f"--- {url} ---\n[No text content extracted]"
    except Exception as e:
        return f"Error fetching {url}: {e}"


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for documentation, error messages, APIs, or general info. Use when you need up-to-date docs or to look up unknown errors."""
    if not query or not query.strip():
        return "Error: query is required"
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
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
        return "Web search requires ddgs. Install with: pip install ddgs"
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
