import subprocess
import urllib.request
from typing import Any, Optional

from config import WORKSPACE_ROOT
from file_tree import read_file_content, get_file_structure_summary, get_project_context


def build_file_structure_context() -> str:
    return get_file_structure_summary()


def build_project_context() -> str:
    return get_project_context()


def build_files_context(paths: list[str]) -> str:
    if not paths:
        return ""
    parts = []
    for p in paths:
        try:
            content, _ = read_file_content(p)
            parts.append(f"--- {p} ---\n{content}")
        except Exception:
            parts.append(f"--- {p} ---\n[Could not read file]")
    return "\n\n".join(parts)


def build_code_context(segments: list[dict[str, Any]]) -> str:
    if not segments:
        return ""
    parts = []
    for s in segments:
        path = s.get("path", "")
        start = int(s.get("startLine", 1))
        end = int(s.get("endLine", start))
        excerpt = s.get("excerpt", "")
        if excerpt:
            parts.append(f"--- {path} (excerpt) ---\n{excerpt}")
        else:
            try:
                content, _ = read_file_content(path)
                lines = content.splitlines()
                segment_lines = lines[max(0, start - 1) : end]
                segment_text = "\n".join(segment_lines)
                parts.append(f"--- {path} (lines {start}-{end}) ---\n{segment_text}")
            except Exception:
                parts.append(f"--- {path} ---\n[Could not read]")
    return "\n\n".join(parts)


def build_codebase_context(query: str, k: int = 6) -> str:
    if not query or not query.strip():
        return ""
    try:
        from semantic_index import get_vector_store, query_index
        store = get_vector_store()
        results = query_index(store, query.strip(), k=k)
        if not results:
            return "[Codebase search: no relevant results found. Index may be empty.]"
        out = []
        for r in results:
            out.append(f"--- {r['path']} ---\n{r['content']}")
        return "[Codebase search results]\n\n" + "\n\n".join(out)
    except Exception as e:
        return f"[Codebase search failed: {e}. Try indexing the workspace first.]"


def build_docs_context(urls: list[str]) -> str:
    if not urls:
        return ""
    parts = []
    for url in urls:
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; AICodec/1.0)"})
            with urllib.request.urlopen(req, timeout=10) as r:
                html = r.read().decode("utf-8", errors="replace")
            text = _extract_text_from_html(html)
            if len(text) > 15000:
                text = text[:15000] + "\n[... truncated ...]"
            parts.append(f"--- {url} ---\n{text}")
        except Exception as e:
            parts.append(f"--- {url} ---\n[Could not fetch: {e}]")
    if not parts:
        return ""
    return "[Documentation]\n\n" + "\n\n".join(parts)


def _extract_text_from_html(html: str) -> str:
    import re
    html = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.I)
    html = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", html, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def build_git_context(ref: Optional[str] = None, diff: bool = False, n: int = 5) -> str:
    root = WORKSPACE_ROOT.resolve()
    if not root.exists():
        return "[Git: workspace not found]"
    try:
        if diff:
            if ref:
                result = subprocess.run(
                    ["git", "diff", ref, "--"],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            else:
                result = subprocess.run(
                    ["git", "diff", "HEAD"],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            out = result.stdout or result.stderr or "[No diff]"
            return f"[Git diff]\n\n{out[:20000]}"
        result = subprocess.run(
            ["git", "log", f"-{n}", "--oneline", "--no-decorate"] + ([ref] if ref else []),
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        log = result.stdout or "[No commits]"
        return f"[Git log]\n\n{log}"
    except FileNotFoundError:
        return "[Git: not installed or not a git repo]"
    except subprocess.TimeoutExpired:
        return "[Git: timeout]"
    except Exception as e:
        return f"[Git error: {e}]"


def build_web_context(query: str, max_results: int = 5) -> str:
    if not query or not query.strip():
        return ""
    try:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            from ddgs import DDGS
        results = list(DDGS().text(query.strip(), max_results=max_results))
        if not results:
            return "[Web search: no results]"
        out = []
        for r in results[:max_results]:
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            out.append(f"• {title}\n  {body}\n  {href}")
        return "[Web search results]\n\n" + "\n\n".join(out)
    except ImportError:
        return "[Web search: install duckduckgo-search (pip install duckduckgo-search)]"
    except Exception as e:
        return f"[Web search failed: {e}]"


def build_past_chats_context(conversation_id: Optional[int], include_other_ids: Optional[list[int]] = None) -> str:
    try:
        from chat_db import get_messages, list_conversations
        msgs = []
        if conversation_id:
            msgs.extend(get_messages(conversation_id))
        if include_other_ids:
            for cid in include_other_ids:
                if cid != conversation_id:
                    msgs.extend(get_messages(cid))
        if not msgs:
            return ""
        lines = []
        for m in msgs[-50:]:
            role = m.get("role", "")
            content = (m.get("content", "") or "")[:2000]
            lines.append(f"{role}: {content}")
        return "[Past conversation context]\n\n" + "\n\n".join(lines)
    except Exception as e:
        return f"[Past chats error: {e}]"
