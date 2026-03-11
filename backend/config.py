import os
from pathlib import Path

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-oss:20b")
_data_home = os.getenv("APPDATA") or os.getenv("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
BUILTIN_MODELS_DIR = Path(os.getenv("BUILTIN_MODELS_DIR", str(Path(_data_home) / "ai-codec" / "models")))
PREFERRED_MODELS = ["gpt-oss:20b", "qwen3-vl:8b"]
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
CHROMA_PERSIST_DIR = Path(os.getenv("CHROMA_PERSIST_DIR", "./chroma_data"))
FAISS_PERSIST_DIR = Path(os.getenv("FAISS_PERSIST_DIR", "./faiss_data"))
WORKSPACE_ROOT = Path(os.getenv("WORKSPACE_ROOT", ".")).resolve()
AGENT_TIMEOUT_SEC = int(os.getenv("AGENT_TIMEOUT_SEC", "1800"))
AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "0"))
STEP_TIMEOUT_SEC = int(os.getenv("STEP_TIMEOUT_SEC", "1200"))
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))
MAX_READ_FILE_SIZE = int(os.getenv("MAX_READ_FILE_SIZE", "1000000"))
NUM_PREDICT = int(os.getenv("NUM_PREDICT", "0"))
NUM_CTX = int(os.getenv("NUM_CTX", "8192"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))
REPEAT_PENALTY = float(os.getenv("REPEAT_PENALTY", "1.1"))
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "10m")

_cache_dir = os.getenv("CACHE_DIR")
if _cache_dir:
    CACHE_DIR = Path(_cache_dir).resolve()
else:
    _cache_home = os.getenv("APPDATA") or os.getenv("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    CACHE_DIR = Path(_cache_home) / "ai-codec" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

VECTOR_CACHE_TTL = int(os.getenv("VECTOR_CACHE_TTL", "300"))
KV_WARM_ENABLED = os.getenv("KV_WARM_ENABLED", "true").lower() in ("1", "true", "yes")
OLLAMA_DRAFT_MODEL = os.getenv("OLLAMA_DRAFT_MODEL", "")
MULTI_MODEL_ENABLED = os.getenv("MULTI_MODEL_ENABLED", "true").lower() in ("1", "true", "yes")
MULTI_AGENT_ORCHESTRATOR_ENABLED = os.getenv("MULTI_AGENT_ORCHESTRATOR_ENABLED", "true").lower() in ("1", "true", "yes")
MODEL_CODER = os.getenv("MODEL_CODER", os.getenv("LLM_MODEL", "gpt-oss:20b"))
MODEL_PLANNER = os.getenv("MODEL_PLANNER", MODEL_CODER)
MODEL_VL = os.getenv("MODEL_VL", "qwen3-vl:8b")
