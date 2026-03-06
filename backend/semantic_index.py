import hashlib
import re
import time
from collections import OrderedDict
from pathlib import Path
from typing import List

try:
    from langchain_ollama import OllamaEmbeddings
except ImportError:
    from langchain_community.embeddings import OllamaEmbeddings

from config import (
    CHROMA_PERSIST_DIR,
    EMBEDDING_MODEL,
    FAISS_PERSIST_DIR,
    OLLAMA_BASE_URL,
    VECTOR_CACHE_TTL,
    WORKSPACE_ROOT,
)

def _lru_cache_get(cache: OrderedDict, key, ttl: float, now: float):
    if key not in cache:
        return None
    val, ts = cache[key]
    if now - ts >= ttl:
        del cache[key]
        return None
    cache.move_to_end(key)
    return val

def _lru_cache_set(cache: OrderedDict, key, val, max_size: int, now: float):
    if key in cache:
        cache.move_to_end(key)
    cache[key] = (val, now)
    while len(cache) > max_size:
        cache.popitem(last=False)

_QUERY_CACHE: OrderedDict = OrderedDict()
_QUERY_CACHE_MAX = 128
_VECTOR_STORE_CACHE = None

_CHROMA_AVAILABLE: bool | None = None
_chroma_module = None
_chroma_Settings = None
Chroma = None
FAISS = None


def _check_chroma():
    global _CHROMA_AVAILABLE, _chroma_module, _chroma_Settings, Chroma, FAISS
    if _CHROMA_AVAILABLE is not None:
        return _CHROMA_AVAILABLE
    try:
        import chromadb
        from chromadb.config import Settings
        from langchain_community.vectorstores import Chroma as _Chroma
        _chroma_module = chromadb
        _chroma_Settings = Settings
        Chroma = _Chroma
        _CHROMA_AVAILABLE = True
        return True
    except Exception:
        _CHROMA_AVAILABLE = False
        try:
            from langchain_community.vectorstores import FAISS as _FAISS
            FAISS = _FAISS
        except Exception:
            pass
        return False

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
    global _VECTOR_STORE_CACHE
    if clear:
        _VECTOR_STORE_CACHE = None
    elif _VECTOR_STORE_CACHE is not None:
        return _VECTOR_STORE_CACHE
    embeddings = get_embeddings()
    if _check_chroma():
        CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        client = _chroma_module.PersistentClient(
            path=str(CHROMA_PERSIST_DIR),
            settings=_chroma_Settings(anonymized_telemetry=False),
        )
        if clear:
            try:
                client.delete_collection(collection_name)
            except Exception:
                pass
        store = Chroma(
            client=client,
            collection_name=collection_name,
            embedding_function=embeddings,
        )
        _VECTOR_STORE_CACHE = store
        return store
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
        store = FAISS(embedding_function=embeddings, index=index, docstore=InMemoryDocstore(), index_to_docstore_id={})
        _VECTOR_STORE_CACHE = store
        return store
    try:
        store = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
        _VECTOR_STORE_CACHE = store
        return store
    except Exception:
        dim = len(embeddings.embed_query("x"))
        import faiss
        index = faiss.IndexFlatL2(dim)
        from langchain_community.docstore.in_memory import InMemoryDocstore
        store = FAISS(embedding_function=embeddings, index=index, docstore=InMemoryDocstore(), index_to_docstore_id={})
        _VECTOR_STORE_CACHE = store
        return store


def index_workspace_files(vector_store, max_file_size: int = 100_000, batch_size: int = 300) -> int:
    batch_texts = []
    batch_metadatas = []
    total = 0
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
            batch_texts.append(text)
            batch_metadatas.append({"path": rel})
            if len(batch_texts) >= batch_size:
                vector_store.add_texts(batch_texts, metadatas=batch_metadatas)
                total += len(batch_texts)
                batch_texts = []
                batch_metadatas = []
        except Exception:
            continue
    if batch_texts:
        vector_store.add_texts(batch_texts, metadatas=batch_metadatas)
        total += len(batch_texts)
    if total == 0:
        return 0
    if not _check_chroma() and FAISS is not None:
        index_path = str(FAISS_PERSIST_DIR / "code_context")
        vector_store.save_local(index_path)
    return total


def query_index(vector_store, query: str, k: int = 6) -> List[dict]:
    key = hashlib.sha256(f"{query}:{k}".encode()).hexdigest()
    now = time.monotonic()
    cached = _lru_cache_get(_QUERY_CACHE, key, VECTOR_CACHE_TTL, now)
    if cached is not None:
        return cached
    docs = vector_store.similarity_search_with_score(query, k=k)
    result = [
        {"path": d.metadata.get("path", ""), "content": d.page_content, "score": float(s)}
        for d, s in docs
    ]
    _lru_cache_set(_QUERY_CACHE, key, result, _QUERY_CACHE_MAX, now)
    return result
