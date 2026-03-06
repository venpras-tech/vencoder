import time
from langchain_core.tools import tool
from semantic_index import get_vector_store, query_index

_SEARCH_RETRIES = 3
_SEARCH_RETRY_DELAY = 0.5


_MAX_CHUNK_CHARS = 4000


@tool
def search_context(query: str, k: int = 6) -> str:
    """Search the semantic index for relevant code/files by meaning. Use first when exploring. One search per task usually enough."""
    last_err = None
    for attempt in range(_SEARCH_RETRIES):
        try:
            store = get_vector_store()
            results = query_index(store, query, k=k)
            break
        except Exception as e:
            last_err = e
            if attempt < _SEARCH_RETRIES - 1:
                time.sleep(_SEARCH_RETRY_DELAY)
    else:
        return f"Search failed: {last_err}. Index may be empty; try indexing the workspace first."
    if not results:
        return "No relevant context found. Index may be empty; consider indexing the workspace."
    out = []
    for r in results:
        content = r["content"]
        if len(content) > _MAX_CHUNK_CHARS:
            content = content[: _MAX_CHUNK_CHARS] + "\n[... truncated ...]"
        out.append(f"--- {r['path']} ---\n{content}")
    return "\n\n".join(out)
