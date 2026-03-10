import logging
from typing import Optional

from langchain_core.messages import HumanMessage

from config import MODEL_CODER, MODEL_PLANNER, MODEL_VL, PREFERRED_MODELS
from llm_builder import build_llm

log = logging.getLogger("multi_agent")

ROUTER_PROMPT = """Classify this request. Reply with ONLY one word:
- greeting: hi, hello, thanks, bye, ok—no task
- question: how does X work, what is Y, where is Z—answer only
- explain: explain this code, why does this happen—explain only
- implement: add feature, create file, write code—needs edits
- fix: fix bug, fix error, correct this—needs edits
- plan: create plan, research, step-by-step—planning
- complex: multi-file refactor, architecture—needs plan

Message: {message}"""

INTENT_HINTS = {
    "greeting": "Respond briefly with text only. No tools.",
    "question": "Answer with text. Use read_file/grep/search only if needed to answer. No edits.",
    "explain": "Explain with text. Use read-only tools only if needed. No edits.",
    "implement": "Implement the request. Use tools: read, edit, write, shell as needed.",
    "fix": "Fix the issue. Use tools: read, edit, write, shell as needed.",
    "plan": "Create a plan. Research first with read-only tools, then produce a plan.",
    "complex": "Large task. Follow the execution plan. Use tools to implement.",
    "simple": "Quick edit. Use tools: read, edit, write as needed.",
}

PLAN_PREP_PROMPT = """Given this coding request, create a brief 3-5 step execution plan. Be concise. Format as numbered list. No code.

Request: {message}"""


def _parse_router_response(text: str) -> str:
    t = (text or "").strip().lower()
    for intent in ("greeting", "question", "explain", "implement", "fix", "plan", "complex", "simple"):
        if intent in t:
            return intent
    return "simple"


def classify_request(message: str, mode: str, available_models: list[str]) -> tuple[str, str]:
    models_set = set(available_models)
    coder = MODEL_CODER if MODEL_CODER in models_set else None
    planner = MODEL_PLANNER if MODEL_PLANNER in models_set else None
    fallback = next((m for m in PREFERRED_MODELS if m in models_set), available_models[0] if available_models else None)
    if not fallback:
        return MODEL_CODER, "simple"
    if mode in ("plan", "ask"):
        return (planner or coder or fallback) if mode == "plan" else (coder or planner or fallback), mode
    try:
        llm = build_llm(coder or fallback, temperature=0, num_predict=15)
        prompt = ROUTER_PROMPT.format(message=(message or "")[:400])
        response = llm.invoke([HumanMessage(content=prompt)])
        content = getattr(response, "content", "") or str(response)
        intent = _parse_router_response(content)
        if intent in ("complex", "plan"):
            model = planner or coder or fallback
        else:
            model = coder or planner or fallback
        return model, intent
    except Exception as e:
        log.debug("classify_request failed: %s", e)
        return planner or coder or fallback, "simple"


def select_model_for_request(message: str, mode: str, available_models: list[str]) -> str:
    model, _ = classify_request(message, mode, available_models)
    return model


def build_execution_plan(message: str, planner_model: str, available_models: list[str]) -> Optional[str]:
    if planner_model not in available_models:
        return None
    try:
        llm = build_llm(planner_model, temperature=0.2, num_predict=200)
        prompt = PLAN_PREP_PROMPT.format(message=(message or "")[:500])
        response = llm.invoke([HumanMessage(content=prompt)])
        content = (getattr(response, "content", "") or str(response)).strip()
        if content and len(content) > 20:
            return f"[Suggested execution plan]\n{content}\n\n"
    except Exception as e:
        log.debug("plan_prep failed: %s", e)
    return None
