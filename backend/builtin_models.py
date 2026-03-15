import subprocess
import sys
from pathlib import Path
from typing import Optional

from config import BUILTIN_MODELS_DIR


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
        result.append(item)
    return sorted(result, key=lambda x: (not x["recommended"], x["size_gb"]))


def download_model(repo_id: str, filename: str) -> tuple[bool, str]:
    ok, err = ensure_llama_cpp_python()
    if not ok:
        return False, err
    BUILTIN_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    dest = BUILTIN_MODELS_DIR / filename
    if dest.exists():
        return True, str(dest)
    url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
    try:
        import urllib.request
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


def download_model_with_progress(repo_id: str, filename: str):
    ok, err = ensure_llama_cpp_python()
    if not ok:
        yield {"error": err}
        return
    BUILTIN_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    dest = BUILTIN_MODELS_DIR / filename
    if dest.exists():
        yield {"ok": True, "path": str(dest), "model": dest.stem}
        return
    url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "VenCode/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            total = int(resp.headers.get("Content-Length", 0)) or 1
            with open(dest, "wb") as f:
                downloaded = 0
                chunk = 65536
                while True:
                    data = resp.read(chunk)
                    if not data:
                        break
                    f.write(data)
                    downloaded += len(data)
                    pct = min(1.0, downloaded / total)
                    yield {"progress": pct, "downloaded": downloaded, "total": total}
        yield {"ok": True, "path": str(dest), "model": dest.stem}
    except Exception as e:
        if dest.exists():
            dest.unlink()
        yield {"error": str(e)}
