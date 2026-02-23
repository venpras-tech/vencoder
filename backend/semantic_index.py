from pathlib import Path
from typing import List

import chromadb
from chromadb.config import Settings
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma

from config import CHROMA_PERSIST_DIR, EMBEDDING_MODEL, OLLAMA_BASE_URL, WORKSPACE_ROOT


def get_embeddings():
    return OllamaEmbeddings(
        model=EMBEDDING_MODEL,
        base_url=OLLAMA_BASE_URL,
    )


def get_vector_store(collection_name: str = "code_context", clear: bool = False):
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
    embeddings = get_embeddings()
    return Chroma(
        client=client,
        collection_name=collection_name,
        embedding_function=embeddings,
    )


def index_workspace_files(vector_store: Chroma, max_file_size: int = 100_000) -> int:
    texts = []
    metadatas = []
    for f in WORKSPACE_ROOT.rglob("*"):
        if not f.is_file():
            continue
        try:
            if f.stat().st_size > max_file_size:
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
            rel = str(f.relative_to(WORKSPACE_ROOT))
            texts.append(text)
            metadatas.append({"path": rel})
        except Exception:
            continue
    if not texts:
        return 0
    vector_store.add_texts(texts, metadatas=metadatas)
    return len(texts)


def query_index(vector_store: Chroma, query: str, k: int = 6) -> List[dict]:
    docs = vector_store.similarity_search_with_score(query, k=k)
    return [
        {"path": d.metadata.get("path", ""), "content": d.page_content, "score": float(s)}
        for d, s in docs
    ]
