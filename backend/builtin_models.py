import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from config import BUILTIN_MODELS_DIR, HUGGINGFACE_BASE_URL

_SEARCH_CACHE_TTL_SEC = 300
_SEARCH_CACHE_MAX = 64
_search_cache: dict[tuple[str, int], tuple[float, list]] = {}

_MODEL_CARD_CACHE_TTL_SEC = 600
_MODEL_CARD_CACHE_MAX = 128
_model_card_cache: dict[str, tuple[float, dict]] = {}


def _llama_cpp_available() -> bool:
    try:
        from llama_cpp import Llama
        return True
    except ImportError:
        return False


def ensure_llama_cpp_python() -> tuple[bool, str]:
    if _llama_cpp_available():
        return True, ""
    try:
        args = [sys.executable, "-m", "pip", "install", "llama-cpp-python>=0.2.0"]
        if sys.platform == "win32":
            args.extend(["--extra-index-url", "https://abetlen.github.io/llama-cpp-python/whl/cpu"])
        subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if _llama_cpp_available():
            return True, ""
        return False, "llama-cpp-python install failed. Run: pip install llama-cpp-python"
    except subprocess.TimeoutExpired:
        return False, "llama-cpp-python install timed out. Run: pip install llama-cpp-python"
    except Exception as e:
        return False, f"llama-cpp-python required. Run: pip install llama-cpp-python ({e})"

SUGGESTED_MODELS = [
    {"id": "qwen2.5-0.5b-q4", "name": "Qwen2.5 0.5B (Q4)", "repo": "Qwen/Qwen2.5-0.5B-Instruct-GGUF", "file": "qwen2.5-0.5b-instruct-q4_k_m.gguf", "size_gb": 0.5, "tier": "low", "params": "0.5B"},
    {"id": "qwen2.5-1.5b-q4", "name": "Qwen2.5 1.5B (Q4)", "repo": "Qwen/Qwen2.5-1.5B-Instruct-GGUF", "file": "qwen2.5-1.5b-instruct-q4_k_m.gguf", "size_gb": 1.1, "tier": "low", "params": "1.5B"},
    {"id": "qwen2.5-3b-q4", "name": "Qwen2.5 3B (Q4)", "repo": "Qwen/Qwen2.5-3B-Instruct-GGUF", "file": "qwen2.5-3b-instruct-q4_k_m.gguf", "size_gb": 2.0, "tier": "low", "params": "3B"},
    {"id": "llama-3.2-1b-q8", "name": "Llama 3.2 1B (Q8)", "repo": "hugging-quants/Llama-3.2-1B-Instruct-Q8_0-GGUF", "file": "Llama-3.2-1B-Instruct-Q8_0.gguf", "size_gb": 1.2, "tier": "low", "params": "1B"},
    {"id": "llama-3.2-3b-q4", "name": "Llama 3.2 3B (Q4)", "repo": "bartowski/Llama-3.2-3B-Instruct-GGUF", "file": "Llama-3.2-3B-Instruct-Q4_K_M.gguf", "size_gb": 2.0, "tier": "medium", "params": "3B"},
    {"id": "phi-3.5-mini-q4", "name": "Phi-3.5 Mini (Q4)", "repo": "MaziyarPanahi/Phi-3.5-mini-instruct-GGUF", "file": "Phi-3.5-mini-instruct.Q4_K_M.gguf", "size_gb": 2.3, "tier": "medium", "params": "3.8B"},
    {"id": "qwen3.5-4b-q4", "name": "Qwen3.5 4B (Q4)", "repo": "unsloth/Qwen3.5-4B-GGUF", "file": "Qwen3.5-4B-Q4_K_M.gguf", "size_gb": 2.7, "tier": "medium", "params": "4B"},
    {"id": "qwen3.5-9b-q4", "name": "Qwen3.5 9B (Q4)", "repo": "lmstudio-community/Qwen3.5-9B-GGUF", "file": "Qwen3.5-9B-Q4_K_M.gguf", "size_gb": 5.5, "tier": "high", "params": "9B"},
    {"id": "gpt-oss-20b-q4", "name": "GPT-OSS 20B (Q4)", "repo": "msohail32/GPT-OSS-20B-GGUF", "file": "GPT-OSS-20B-Q4_K_M.gguf", "size_gb": 13.0, "tier": "high", "params": "20B"},
]


def get_system_ram_gb() -> float:
    try:
        import psutil
        return round(psutil.virtual_memory().total / (1024**3), 1)
    except ImportError:
        return 8.0
    except Exception:
        return 8.0


def get_system_tier() -> str:
    ram = get_system_ram_gb()
    if ram < 8:
        return "low"
    if ram < 16:
        return "medium"
    return "high"


def get_installed_models() -> list[str]:
    BUILTIN_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(f.stem for f in BUILTIN_MODELS_DIR.glob("*.gguf"))


def model_is_installed(filename: str) -> bool:
    path = BUILTIN_MODELS_DIR / filename
    return path.exists()


def get_suggested_for_system() -> list[dict]:
    tier = get_system_tier()
    ram_gb = get_system_ram_gb()
    installed = get_installed_models()
    comfort_gb = ram_gb * 0.5
    result = []
    for m in SUGGESTED_MODELS:
        stem = Path(m["file"]).stem
        item = {**m, "installed": stem in installed or model_is_installed(m["file"])}
        if m["tier"] == tier:
            item["recommended"] = True
        elif m["size_gb"] <= ram_gb * 0.5:
            item["recommended"] = True
        else:
            item["recommended"] = m["size_gb"] <= ram_gb
        item["likely_too_large"] = m["size_gb"] > comfort_gb
        result.append(item)
    return sorted(result, key=lambda x: (not x["recommended"], x["size_gb"]))


def hf_file_url(repo_id: str, filename: str) -> str:
    base = HUGGINGFACE_BASE_URL.rstrip("/")
    return f"{base}/{repo_id}/resolve/main/{filename}"


def bytes_likely_too_large(file_size: int) -> bool:
    if file_size <= 0:
        return False
    ram_gb = get_system_ram_gb()
    max_bytes = ram_gb * 0.5 * (1024**3)
    return file_size > max_bytes


def _is_gguf_model_card(m: dict) -> bool:
    tags = m.get("tags") or []
    if any("gguf" in str(t).lower() for t in tags):
        return True
    mid = (m.get("id") or m.get("modelId") or "").lower()
    return "gguf" in mid or mid.endswith("-gguf")


def _prune_cache(cache: dict, max_entries: int) -> None:
    if len(cache) <= max_entries:
        return
    keys = sorted(cache.keys(), key=lambda k: cache[k][0])[: max(0, len(cache) - max_entries)]
    for k in keys:
        cache.pop(k, None)


def hf_search_models(query: str, limit: int = 25) -> list[dict]:
    lim = min(max(1, int(limit)), 50)
    qn = (query or "").strip().lower() or "gguf"
    now = time.monotonic()
    key = (qn, lim)
    if key in _search_cache:
        ts, cached = _search_cache[key]
        if now - ts < _SEARCH_CACHE_TTL_SEC:
            return list(cached)
    base = HUGGINGFACE_BASE_URL.rstrip("/")
    q = (query or "").strip() or "gguf"
    qs = urllib.parse.urlencode({"search": q, "limit": 100, "sort": "downloads", "direction": "-1"})
    url = f"{base}/api/models?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": "AI-Dev/1.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        data = json.loads(r.read().decode())
    if not isinstance(data, list):
        return []
    out = []
    for m in data:
        if not isinstance(m, dict) or not _is_gguf_model_card(m):
            continue
        mid = m.get("id") or m.get("modelId") or ""
        if not mid:
            continue
        out.append({
            "id": mid,
            "downloads": m.get("downloads"),
            "likes": m.get("likes"),
            "pipeline_tag": m.get("pipeline_tag"),
            "last_modified": m.get("lastModified"),
        })
        if len(out) >= lim:
            break
    _search_cache[key] = (now, list(out))
    _prune_cache(_search_cache, _SEARCH_CACHE_MAX)
    return out


def hf_latest_gguf_models(limit: int = 20) -> list[dict]:
    lim = min(max(1, int(limit)), 40)
    base = HUGGINGFACE_BASE_URL.rstrip("/")
    qs = urllib.parse.urlencode({"search": "gguf", "limit": 120, "sort": "lastModified", "direction": "-1"})
    url = f"{base}/api/models?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": "AI-Dev/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    if not isinstance(data, list):
        return []
    out = []
    for m in data:
        if not isinstance(m, dict) or not _is_gguf_model_card(m):
            continue
        mid = m.get("id") or m.get("modelId") or ""
        if not mid:
            continue
        out.append({
            "id": mid,
            "downloads": m.get("downloads"),
            "likes": m.get("likes"),
            "pipeline_tag": m.get("pipeline_tag"),
            "last_modified": m.get("lastModified"),
        })
        if len(out) >= lim:
            break
    return out


def fetch_model_card(repo_id: str) -> dict:
    rid = (repo_id or "").strip()
    if not rid or "/" not in rid:
        return {}
    now = time.monotonic()
    if rid in _model_card_cache:
        ts, data = _model_card_cache[rid]
        if now - ts < _MODEL_CARD_CACHE_TTL_SEC and isinstance(data, dict):
            return data
    base = HUGGINGFACE_BASE_URL.rstrip("/")
    enc = "/".join(urllib.parse.quote(p, safe="") for p in rid.split("/"))
    url = f"{base}/api/models/{enc}"
    req = urllib.request.Request(url, headers={"User-Agent": "AI-Dev/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    if not isinstance(data, dict):
        data = {}
    _model_card_cache[rid] = (now, data)
    _prune_cache(_model_card_cache, _MODEL_CARD_CACHE_MAX)
    return data


def _quant_preference(filename: str) -> int:
    n = (filename or "").lower()
    if "q4_k_m" in n or "q4km" in n:
        return 100
    if "q4_k_s" in n:
        return 95
    if "q5_k_m" in n:
        return 90
    if "q4_0" in n or "-q4." in n:
        return 85
    if "q3" in n:
        return 82
    if "q5" in n:
        return 78
    if "q6" in n:
        return 75
    if "q8" in n:
        return 72
    if "f16" in n or "fp16" in n:
        return 35
    if "f32" in n:
        return 15
    return 50


def hf_model_gguf_files(repo_id: str) -> list[dict]:
    data = fetch_model_card(repo_id)
    siblings = data.get("siblings") or []
    out = []
    for s in siblings:
        if not isinstance(s, dict):
            continue
        rf = s.get("rfilename") or ""
        if not rf.lower().endswith(".gguf"):
            continue
        size = int(s.get("size") or 0)
        base_name = Path(rf).name
        out.append({
            "filename": rf,
            "size": size,
            "size_gb": round(size / (1024**3), 2) if size else None,
            "likely_too_large": bytes_likely_too_large(size),
            "quant_score": _quant_preference(base_name),
            "preferred_quant": _quant_preference(base_name) >= 70,
        })
    out.sort(key=lambda x: (-(x.get("quant_score") or 0), x.get("size") or 0))
    return out


def hf_repo_card_summary(repo_id: str) -> dict:
    c = fetch_model_card(repo_id)
    if not isinstance(c, dict):
        return {"id": repo_id, "description": "", "downloads": None, "likes": None, "pipeline_tag": ""}
    desc = ""
    cd = c.get("cardData")
    if isinstance(cd, dict):
        desc = str(cd.get("description") or cd.get("summary") or "")[:1200]
    elif isinstance(cd, str):
        desc = cd[:1200]
    return {
        "id": repo_id,
        "description": desc.strip(),
        "downloads": c.get("downloads"),
        "likes": c.get("likes"),
        "pipeline_tag": c.get("pipeline_tag") or "",
    }


def hf_repos_install_status(repo_ids: list[str]) -> dict[str, bool]:
    installed = set(get_installed_models())
    result: dict[str, bool] = {}
    if not installed:
        for rid in repo_ids:
            result[rid] = False
        return result
    for rid in repo_ids[:40]:
        rid = (rid or "").strip()
        if not rid or "/" not in rid:
            result[rid] = False
            continue
        try:
            files = hf_model_gguf_files(rid)
        except Exception:
            result[rid] = False
            continue
        found = False
        for f in files:
            fn = f.get("filename") or ""
            if not fn:
                continue
            stem = Path(fn).stem
            if stem in installed:
                found = True
                break
            base = Path(fn).name
            if model_is_installed(base):
                found = True
                break
        result[rid] = found
    return result


def download_model(repo_id: str, filename: str) -> tuple[bool, str]:
    ok, err = ensure_llama_cpp_python()
    if not ok:
        return False, err
    BUILTIN_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    dest = BUILTIN_MODELS_DIR / filename
    if dest.exists():
        return True, str(dest)
    url = hf_file_url(repo_id, filename)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "VenCode/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            with open(dest, "wb") as f:
                downloaded = 0
                chunk = 8192
                while True:
                    data = resp.read(chunk)
                    if not data:
                        break
                    f.write(data)
                    downloaded += len(data)
        return True, str(dest)
    except Exception as e:
        if dest.exists():
            dest.unlink()
        return False, str(e)


def download_model_with_progress(repo_id: str, filename: str, should_cancel=None):
    ok, err = ensure_llama_cpp_python()
    if not ok:
        yield {"error": err}
        return
    BUILTIN_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    dest = BUILTIN_MODELS_DIR / filename
    if dest.exists():
        yield {"ok": True, "path": str(dest), "model": dest.stem}
        return
    url = hf_file_url(repo_id, filename)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "VenCode/1.0"})
        cancelled = False
        with urllib.request.urlopen(req, timeout=30) as resp:
            total = int(resp.headers.get("Content-Length", 0)) or 1
            with open(dest, "wb") as f:
                downloaded = 0
                chunk = 8192
                while True:
                    if should_cancel and should_cancel():
                        cancelled = True
                        break
                    data = resp.read(chunk)
                    if not data:
                        break
                    f.write(data)
                    downloaded += len(data)
                    pct = min(1.0, downloaded / total)
                    yield {"progress": pct, "downloaded": downloaded, "total": total}
        if cancelled and dest.exists():
            dest.unlink()
            return
        yield {"ok": True, "path": str(dest), "model": dest.stem}
    except Exception as e:
        if dest.exists():
            try:
                dest.unlink()
            except OSError:
                pass
        yield {"error": str(e)}
