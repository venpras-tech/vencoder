import re
from pathlib import Path
from typing import List

from langchain_community.embeddings import OllamaEmbeddings

from config import CHROMA_PERSIST_DIR, EMBEDDING_MODEL, FAISS_PERSIST_DIR, OLLAMA_BASE_URL, WORKSPACE_ROOT

_CHROMA_AVAILABLE = False
Chroma = None
FAISS = None

try:
    import chromadb
    from chromadb.config import Settings
    from langchain_community.vectorstores import Chroma
    _CHROMA_AVAILABLE = True
except Exception:
    try:
        from langchain_community.vectorstores import FAISS
    except Exception:
        pass

_INDEX_IGNORE = re.compile(
    r"(^|/)(\.git|node_modules|__pycache__|\.venv|venv|\.env|dist|build|chroma_data|faiss_data|\.codec-agent)(/|$)",
    re.I,
)
_INDEX_EXTENSIONS = frozenset(
    ".py .js .ts .jsx .tsx .mjs .cjs .java .kt .go .rs .rb .php .cs .swift .md .json .yaml .yml .toml .ini .cfg .conf .sh .bash .sql .html .css .scss .vue .svelte".split()
)


def _should_index(path: Path, rel: str) -> bool:
    if _INDEX_IGNORE.search(rel.replace("\\", "/")):
        return False
    return path.suffix.lower() in _INDEX_EXTENSIONS


def get_embeddings():
    return OllamaEmbeddings(
        model=EMBEDDING_MODEL,
        base_url=OLLAMA_BASE_URL,
    )


def get_vector_store(collection_name: str = "code_context", clear: bool = False):
    embeddings = get_embeddings()
    if _CHROMA_AVAILABLE:
        CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(
            path=str(CHROMA_PERSIST_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        if clear:
            try:
                client.delete_collection(collection_name)
            except Exception:
                pass
        return Chroma(
            client=client,
            collection_name=collection_name,
            embedding_function=embeddings,
        )
    if FAISS is None:
        raise RuntimeError(
            "ChromaDB failed to import (e.g. Python 3.14) and FAISS is not installed. "
            "Install faiss-cpu: pip install faiss-cpu"
        )
    FAISS_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    index_path = str(FAISS_PERSIST_DIR / collection_name)
    if clear:
        for p in Path(index_path).parent.glob(f"{collection_name}*"):
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass
        dim = len(embeddings.embed_query("x"))
        import faiss
        index = faiss.IndexFlatL2(dim)
        from langchain_community.docstore.in_memory import InMemoryDocstore
        return FAISS(embedding_function=embeddings, index=index, docstore=InMemoryDocstore(), index_to_docstore_id={})
    try:
        return FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
    except Exception:
        dim = len(embeddings.embed_query("x"))
        import faiss
        index = faiss.IndexFlatL2(dim)
        from langchain_community.docstore.in_memory import InMemoryDocstore
        return FAISS(embedding_function=embeddings, index=index, docstore=InMemoryDocstore(), index_to_docstore_id={})


def index_workspace_files(vector_store, max_file_size: int = 100_000) -> int:
    texts = []
    metadatas = []
    for f in WORKSPACE_ROOT.rglob("*"):
        if not f.is_file():
            continue
        try:
            rel = str(f.relative_to(WORKSPACE_ROOT))
            if not _should_index(f, rel):
                continue
            if f.stat().st_size > max_file_size:
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
            texts.append(text)
            metadatas.append({"path": rel})
        except Exception:
            continue
    if not texts:
        return 0
    vector_store.add_texts(texts, metadatas=metadatas)
    if not _CHROMA_AVAILABLE and FAISS is not None:
        index_path = str(FAISS_PERSIST_DIR / "code_context")
        vector_store.save_local(index_path)
    return len(texts)


def query_index(vector_store, query: str, k: int = 6) -> List[dict]:
    docs = vector_store.similarity_search_with_score(query, k=k)
    return [
        {"path": d.metadata.get("path", ""), "content": d.page_content, "score": float(s)}
        for d, s in docs
    ]
