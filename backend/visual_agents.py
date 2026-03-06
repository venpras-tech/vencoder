import asyncio
import json
import logging
from typing import Any, Optional

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

from config import OLLAMA_BASE_URL, OLLAMA_KEEP_ALIVE, PREFERRED_MODELS
from multi_agent import MODEL_VL
from visual_context import build_visual_instruction, build_visual_message_content

log = logging.getLogger("visual_agents")


def _extract_text(response: Any) -> str:
    raw = getattr(response, "content", None)
    if isinstance(raw, str) and raw:
        return raw
    if isinstance(raw, list):
        parts = []
        for block in raw:
            if isinstance(block, dict):
                t = block.get("text") or block.get("content")
                if t:
                    parts.append(str(t))
            elif isinstance(block, str):
                parts.append(block)
        if parts:
            return "".join(parts)
    meta = getattr(response, "response_metadata", None) or {}
    msg = meta.get("message", {})
    if isinstance(msg, dict):
        c = msg.get("content")
        if isinstance(c, str) and c:
            return c
        if isinstance(c, list):
            return "".join(str(b.get("text", b.get("content", ""))) for b in c if isinstance(b, dict))
    extra = getattr(response, "additional_kwargs", None) or {}
    reasoning = extra.get("reasoning_content")
    if isinstance(reasoning, str) and reasoning:
        return reasoning
    return str(response) if response else ""

ORCHESTRATOR_PROMPT = """You are a visual task orchestrator. Analyze the user's request and the image context.

Classify the primary task type. Reply with ONLY a JSON object, no other text:
{"task": "color"|"layout"|"content"|"analysis"|"mixed", "subtasks": ["task1", "task2"]}

- color: color changes, recoloring, theme adjustment
- layout: position, size, move, resize, alignment
- content: text change, add/remove elements, generate new content
- analysis: describe, explain, identify elements
- mixed: multiple distinct tasks

If multiple tasks, list in subtasks. Be concise."""

COLOR_AGENT_PROMPT = """You are a color specialist. Focus on color-related changes: recoloring, theme, contrast, color correction.
Describe the changes precisely. Reference positions or regions from the user's interactions."""

LAYOUT_AGENT_PROMPT = """You are a layout specialist. Focus on position, size, alignment, spacing.
Describe layout changes precisely. Reference coordinates or regions from the user's interactions."""

CONTENT_AGENT_PROMPT = """You are a content specialist. Focus on text changes, adding/removing elements, generating new content.
Describe content changes precisely. Reference the user's target regions."""

ANALYSIS_AGENT_PROMPT = """You are a visual analysis specialist. Describe, explain, or identify elements in the image.
Reference the user's interactions (clicks, highlights) to focus your analysis."""


def _get_agent_prompt(task: str) -> str:
    m = {"color": COLOR_AGENT_PROMPT, "layout": LAYOUT_AGENT_PROMPT, "content": CONTENT_AGENT_PROMPT, "analysis": ANALYSIS_AGENT_PROMPT}
    return m.get(task, ANALYSIS_AGENT_PROMPT)


def _parse_orchestrator_response(text: str) -> dict[str, Any]:
    try:
        t = (text or "").strip()
        for start in ("{", "```json"):
            idx = t.find(start)
            if idx >= 0:
                t = t[idx:].replace("```json", "").replace("```", "").strip()
                break
        return json.loads(t)
    except Exception:
        return {"task": "analysis", "subtasks": []}


VISUAL_ORCHESTRATOR_MODEL = "gpt-oss:20b"
VISUAL_ANALYSIS_MODEL = "qwen3-vl:8b"


def route_visual_task(
    message: str,
    image_b64: Optional[str],
    interactions: Optional[list],
    available_models: list[str],
) -> dict[str, Any]:
    models_set = set(available_models)
    orchestrator = VISUAL_ORCHESTRATOR_MODEL if VISUAL_ORCHESTRATOR_MODEL in models_set else None
    vl = MODEL_VL if MODEL_VL in models_set else None
    fallback = next((m for m in PREFERRED_MODELS if m in models_set), available_models[0] if available_models else None)
    if not orchestrator and not fallback:
        return {"task": "analysis", "subtasks": [], "model": fallback}
    model = orchestrator or vl or fallback
    try:
        llm = ChatOllama(
            model=model,
            base_url=OLLAMA_BASE_URL,
            temperature=0,
            num_predict=150,
            keep_alive=OLLAMA_KEEP_ALIVE,
        )
        if model == VISUAL_ORCHESTRATOR_MODEL:
            text = build_visual_instruction(message, image_b64, interactions)
            content = text
        else:
            content = build_visual_message_content(message, image_b64, interactions)
        response = llm.invoke([HumanMessage(content=content)])
        raw = _extract_text(response)
        parsed = _parse_orchestrator_response(raw)
        parsed["model"] = model
        return parsed
    except Exception as e:
        log.debug("visual orchestrator failed: %s", e)
        return {"task": "analysis", "subtasks": [], "model": model}


def run_visual_subagent(
    task: str,
    message: str,
    image_b64: Optional[str],
    interactions: Optional[list],
    model: str,
) -> str:
    system = _get_agent_prompt(task)
    instruction = build_visual_instruction(message, image_b64, interactions)
    content = build_visual_message_content(message, image_b64, interactions)
    try:
        llm = ChatOllama(
            model=model,
            base_url=OLLAMA_BASE_URL,
            temperature=0.2,
            num_predict=4096,
            keep_alive=OLLAMA_KEEP_ALIVE,
        )
        full = f"{system}\n\n{instruction}"
        content_with_system = [b for b in content if b.get("type") == "image_url"]
        content_with_system.append({"type": "text", "text": full})
        response = llm.invoke([HumanMessage(content=content_with_system)])
        out = _extract_text(response)
        if not out:
            try:
                from ollama import Client
                client = Client(host=OLLAMA_BASE_URL)
                images = []
                for b in content_with_system:
                    if b.get("type") == "image_url":
                        img = b.get("image_url")
                        url = img.get("url", img) if isinstance(img, dict) else (img or "")
                        if isinstance(url, str) and "," in url:
                            images.append(url.split(",", 1)[1])
                        elif url:
                            images.append(url)
                r = client.chat(model=model, messages=[{"role": "user", "content": full, "images": images}], stream=False)
                msg = r.get("message") if isinstance(r, dict) else getattr(r, "message", None)
                out = (msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)) or ""
            except Exception as fallback_err:
                log.debug("ollama direct fallback failed: %s", fallback_err)
        return out or "[No response from vision model]"
    except Exception as e:
        log.debug("visual subagent %s failed: %s", task, e)
        return f"[Error: {e}]"


def process_visual_request(
    message: str,
    image_b64: Optional[str],
    interactions: Optional[list],
    available_models: list[str],
    parallel: bool = True,
) -> str:
    route = route_visual_task(message, image_b64, interactions, available_models)
    task = route.get("task", "analysis")
    subtasks = route.get("subtasks", [task])
    models_set = set(available_models)
    analysis_model = VISUAL_ANALYSIS_MODEL if VISUAL_ANALYSIS_MODEL in models_set else (MODEL_VL if MODEL_VL in models_set else (available_models[0] if available_models else None))
    if not analysis_model:
        return "[No vision model available. Install qwen3-vl:8b for image analysis.]"
    if parallel and len(subtasks) > 1:
        results = []
        for sub in subtasks:
            if sub != task:
                results.append(run_visual_subagent(sub, message, image_b64, interactions, analysis_model))
        if results:
            return "\n\n---\n\n".join(results)
    return run_visual_subagent(task, message, image_b64, interactions, analysis_model)
