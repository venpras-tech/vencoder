from pathlib import Path
from typing import Any, Optional

from config import (
    BUILTIN_MODELS_DIR,
    LLM_PROVIDER,
    LM_STUDIO_BASE_URL,
    NUM_CTX,
    NUM_PREDICT,
    OLLAMA_BASE_URL,
    OLLAMA_KEEP_ALIVE,
    REPEAT_PENALTY,
    TEMPERATURE,
)


def get_builtin_models() -> list[str]:
    BUILTIN_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(
        f.stem for f in BUILTIN_MODELS_DIR.glob("*.gguf")
    )


def resolve_builtin_model_path(model: str) -> str:
    if model.endswith(".gguf") and Path(model).exists():
        return model
    if model.endswith(".gguf"):
        p = BUILTIN_MODELS_DIR / Path(model).name
        if p.exists():
            return str(p)
    candidates = list(BUILTIN_MODELS_DIR.glob(f"*{model}*.gguf"))
    if not candidates:
        candidates = list(BUILTIN_MODELS_DIR.glob("*.gguf"))
    if candidates:
        return str(candidates[0])
    return str(BUILTIN_MODELS_DIR / model) if not model.endswith(".gguf") else model


def build_llm(
    model: str,
    temperature: Optional[float] = None,
    num_predict: Optional[int] = None,
    num_ctx: Optional[int] = None,
    **kwargs: Any,
):
    provider = (LLM_PROVIDER or "ollama").lower()
    if provider == "builtin":
        try:
            from langchain_community.chat_models.llamacpp import ChatLlamaCpp
        except ImportError:
            raise ImportError(
                "Built-in provider requires llama-cpp-python. Install with: pip install -r requirements-builtin.txt "
                "(needs Visual Studio Build Tools on Windows)"
            ) from None

        path = resolve_builtin_model_path(model)
        n_pred = num_predict if num_predict is not None else (NUM_PREDICT if NUM_PREDICT > 0 else 4096)
        n_ctx = num_ctx or NUM_CTX
        return ChatLlamaCpp(
            model_path=path,
            temperature=temperature if temperature is not None else TEMPERATURE,
            max_tokens=n_pred,
            n_ctx=n_ctx,
            n_gpu_layers=-1,
            verbose=False,
            **kwargs,
        )
    if provider == "lmstudio":
        from langchain_openai import ChatOpenAI
        base = (LM_STUDIO_BASE_URL or "http://localhost:1234").rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        n_pred = num_predict if num_predict is not None else (NUM_PREDICT if NUM_PREDICT > 0 else 4096)
        return ChatOpenAI(
            model=model,
            base_url=base,
            api_key="lm-studio",
            temperature=temperature if temperature is not None else TEMPERATURE,
            max_tokens=n_pred,
            **kwargs,
        )
    from langchain_ollama import ChatOllama

    n_pred = num_predict if num_predict is not None else (NUM_PREDICT if NUM_PREDICT > 0 else 4096)
    return ChatOllama(
        model=model,
        base_url=OLLAMA_BASE_URL,
        temperature=temperature if temperature is not None else TEMPERATURE,
        num_predict=n_pred,
        num_ctx=num_ctx or NUM_CTX,
        repeat_penalty=REPEAT_PENALTY,
        keep_alive=OLLAMA_KEEP_ALIVE,
        **kwargs,
    )
