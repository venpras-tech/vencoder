from langchain_core.tools import tool
from semantic_index import get_vector_store, query_index


@tool
def search_context(query: str, k: int = 5) -> str:
    """Search the semantic index for relevant code/files by meaning. Use before editing to find where things are."""
    store = get_vector_store()
    results = query_index(store, query, k=k)
    if not results:
        return "No relevant context found. Index may be empty; consider indexing the workspace."
    out = []
    for r in results:
        out.append(f"--- {r['path']} ---\n{r['content'][:2000]}")
    return "\n\n".join(out)
