import logging
from typing import Optional

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

from config import (
    OLLAMA_BASE_URL,
    OLLAMA_KEEP_ALIVE,
    PREFERRED_MODELS,
)

log = logging.getLogger("multi_agent")

MODEL_CODER = "gpt-oss:20b"
MODEL_PLANNER = "gpt-oss:20b"
MODEL_VL = "qwen3-vl:8b"

ROUTER_PROMPT = """Classify this coding request. Reply with ONLY one word, nothing else:
- simple: quick edit, single file, fix typo, add one function
- complex: multi-file, refactor, architecture, large change
- plan: user wants a plan, research, or step-by-step

Message: {message}"""

PLAN_PREP_PROMPT = """Given this coding request, create a brief 3-5 step execution plan. Be concise. Format as numbered list. No code.

Request: {message}"""


def _parse_router_response(text: str) -> str:
    t = (text or "").strip().lower()
    if "complex" in t or "plan" in t:
        return "complex" if "complex" in t else "plan"
    return "simple"


def select_model_for_request(
    message: str,
    mode: str,
    available_models: list[str],
) -> str:
    models_set = set(available_models)
    coder = MODEL_CODER if MODEL_CODER in models_set else None
    planner = MODEL_PLANNER if MODEL_PLANNER in models_set else None
    vl = MODEL_VL if MODEL_VL in models_set else None

    fallback = next((m for m in PREFERRED_MODELS if m in models_set), available_models[0] if available_models else None)
    if not fallback:
        return MODEL_CODER

    if mode == "plan":
        return planner or coder or fallback

    if mode == "ask":
        return coder or planner or fallback

    if mode == "agent":
        try:
            llm = ChatOllama(
                model=coder or fallback,
                base_url=OLLAMA_BASE_URL,
                temperature=0,
                num_predict=10,
                keep_alive=OLLAMA_KEEP_ALIVE,
            )
            prompt = ROUTER_PROMPT.format(message=(message or "")[:400])
            response = llm.invoke([HumanMessage(content=prompt)])
            content = getattr(response, "content", "") or str(response)
            task_type = _parse_router_response(content)
            if task_type in ("complex", "plan"):
                return planner or coder or fallback
            return coder or planner or fallback
        except Exception as e:
            log.debug("router failed, using planner: %s", e)
            return planner or coder or fallback

    return coder or planner or fallback


def build_execution_plan(message: str, planner_model: str, available_models: list[str]) -> Optional[str]:
    if planner_model not in available_models:
        return None
    try:
        llm = ChatOllama(
            model=planner_model,
            base_url=OLLAMA_BASE_URL,
            temperature=0.2,
            num_predict=200,
            keep_alive=OLLAMA_KEEP_ALIVE,
        )
        prompt = PLAN_PREP_PROMPT.format(message=(message or "")[:500])
        response = llm.invoke([HumanMessage(content=prompt)])
        content = (getattr(response, "content", "") or str(response)).strip()
        if content and len(content) > 20:
            return f"[Suggested execution plan]\n{content}\n\n"
    except Exception as e:
        log.debug("plan_prep failed: %s", e)
    return None
