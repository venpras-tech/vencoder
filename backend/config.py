import os
from pathlib import Path

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-oss:20b")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
CHROMA_PERSIST_DIR = Path(os.getenv("CHROMA_PERSIST_DIR", "./chroma_data"))
FAISS_PERSIST_DIR = Path(os.getenv("FAISS_PERSIST_DIR", "./faiss_data"))
WORKSPACE_ROOT = Path(os.getenv("WORKSPACE_ROOT", ".")).resolve()
AGENT_TIMEOUT_SEC = int(os.getenv("AGENT_TIMEOUT_SEC", "600"))
AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "0"))
STEP_TIMEOUT_SEC = int(os.getenv("STEP_TIMEOUT_SEC", "600"))
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))
MAX_READ_FILE_SIZE = int(os.getenv("MAX_READ_FILE_SIZE", "1000000"))
