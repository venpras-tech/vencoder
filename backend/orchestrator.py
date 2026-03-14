import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Optional

from langchain_core.messages import HumanMessage

from llm_builder import build_llm
from multi_agent import MODEL_CODER, MODEL_PLANNER

log = logging.getLogger("orchestrator")

PLANNER_PROMPT = """You are a task planner. Break the user's coding request into 2-6 ordered subtasks.

Reply with ONLY this JSON structure, nothing else (no markdown, no explanation):
{"subtasks": [{"id": 1, "task": "action description", "files": ["path"], "parallel_group": 0}, {"id": 2, "task": "...", "files": [], "parallel_group": 0}]}

Example for "add hello world to main.py":
{"subtasks": [{"id": 1, "task": "Read main.py to understand structure", "files": ["main.py"], "parallel_group": 0}, {"id": 2, "task": "Add hello world function", "files": ["main.py"], "parallel_group": 0}, {"id": 3, "task": "Run main.py to verify", "files": [], "parallel_group": 0}]}

Rules: id=1,2,3... | task=one focused action | files=paths this subtask touches | parallel_group: 0=sequential, same number=parallel. Keep 2-6 subtasks.

User request: {message}"""


@dataclass
class Subtask:
    id: int
    task: str
    files: list[str] = field(default_factory=list)
    parallel_group: int = 0
    result: Optional[str] = None
    error: Optional[str] = None


def _parse_plan(text: str) -> list[Subtask]:
    out = []
    t = (text or "").strip()
    for pattern in ("```json", "```", "{"):
        idx = t.find(pattern)
        if idx >= 0:
            t = t[idx:].replace("```json", "").replace("```", "").strip()
            break
    start = t.find("{")
    if start >= 0:
        depth = 0
        end = -1
        for i, c in enumerate(t[start:], start):
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end >= 0:
            t = t[start : end + 1]
    t = t.replace(",]", "]").replace(",}", "}")
    try:
        data = json.loads(t)
        for s in data.get("subtasks", [])[:10]:
            task_str = str(s.get("task", "")).strip()
            if not task_str:
                continue
            out.append(Subtask(
                id=int(s.get("id", len(out) + 1)),
                task=task_str,
                files=list(s.get("files", [])) if isinstance(s.get("files"), list) else [],
                parallel_group=int(s.get("parallel_group", 0)),
            ))
    except Exception as e:
        log.info("parse_plan failed: %s (raw: %s)", e, (text or "")[:200])
    return out


def _plan_subtasks(
    message: str,
    project_context: str,
    planner_model: str,
    fallback_models: Optional[list[str]] = None,
) -> list[Subtask]:
    models_to_try = [planner_model]
    if fallback_models:
        for m in fallback_models:
            if m and m != planner_model and m not in models_to_try:
                models_to_try.append(m)
    for model in models_to_try:
        try:
            llm = build_llm(model, temperature=0.1, num_predict=600)
            prompt = PLANNER_PROMPT.format(message=(message or "")[:600])
            full = f"[Project context - use for file paths]\n{project_context[:2000]}\n\n{prompt}" if project_context else prompt
            response = llm.invoke([HumanMessage(content=full)])
            raw = getattr(response, "content", "") or str(response)
            result = _parse_plan(raw)
            if result:
                log.info("orchestrator: planned %s subtasks (model=%s)", len(result), model)
                return result
        except Exception as e:
            log.info("plan_subtasks failed with %s: %s", model, e)
    return []


def _group_by_parallel(subtasks: list[Subtask]) -> list[list[Subtask]]:
    if not subtasks:
        return []
    by_group: dict[int, list[Subtask]] = {}
    for s in subtasks:
        g = s.parallel_group if s.parallel_group > 0 else -s.id
        if g not in by_group:
            by_group[g] = []
        by_group[g].append(s)
    ordered = []
    seen = set()
    for s in subtasks:
        g = s.parallel_group if s.parallel_group > 0 else -s.id
        if g not in seen:
            seen.add(g)
            ordered.append(by_group[g])
    return ordered


async def _run_subtask(
    subtask: Subtask,
    message: str,
    project_context: str,
    coder_model: str,
    history: list,
    get_agent_fn,
) -> Subtask:
    from agent_harness import run as harness_run
    focused = f"[Subtask {subtask.id}] {subtask.task}\n\nPart of larger request: {message[:200]}"
    full_message = f"{project_context}\n\n--- Task ---\n\n{focused}" if project_context else focused
    try:
        agent = get_agent_fn("agent", coder_model)
        result = await harness_run(agent, full_message, history=history, max_steps=15)
        subtask.result = result.get("content", "")
        subtask.error = result.get("error")
    except Exception as e:
        subtask.error = str(e)
        log.debug("subtask %s failed: %s", subtask.id, e)
    return subtask


async def _run_subtask_stream(
    subtask: Subtask,
    message: str,
    project_context: str,
    coder_model: str,
    history: list,
    get_agent_fn,
) -> AsyncGenerator[str, None]:
    from agent_harness import stream_events
    focused = f"[Subtask {subtask.id}] {subtask.task}\n\nPart of larger request: {message[:200]}"
    full_message = f"{project_context}\n\n--- Task ---\n\n{focused}" if project_context else focused
    tokens = []
    try:
        agent = get_agent_fn("agent", coder_model)
        async for chunk in stream_events(agent, full_message, history=history, max_steps=15, model_name=coder_model):
            if chunk.strip():
                yield chunk
                try:
                    data = json.loads(chunk.strip())
                    if data.get("type") == "token" and data.get("content"):
                        tokens.append(data["content"])
                    elif data.get("type") == "error":
                        subtask.error = data.get("content", "Unknown error")
                except (json.JSONDecodeError, ValueError):
                    pass
        subtask.result = "".join(tokens) if not subtask.error else ""
    except Exception as e:
        subtask.error = str(e)
        log.debug("subtask %s failed: %s", subtask.id, e)


async def run_orchestrated(
    message: str,
    project_context: str,
    planner_model: str,
    coder_model: str,
    available_models: list[str],
    history: list,
    get_agent_fn,
) -> AsyncGenerator[str, None]:
    models_set = set(available_models or [])
    planner = planner_model if planner_model in models_set else (available_models[0] if available_models else MODEL_PLANNER)
    coder = coder_model if coder_model in models_set else (MODEL_CODER if MODEL_CODER in models_set else (available_models[0] if available_models else planner))
    fallback = [m for m in [coder] if m in models_set and m != planner][:2]
    subtasks = await asyncio.to_thread(_plan_subtasks, message, project_context, planner, fallback)
    if not subtasks:
        yield json.dumps({"type": "orchestrator_fallback"}) + "\n"
        return
    yield json.dumps({"type": "status", "content": f"Orchestrator: {len(subtasks)} subtasks planned"}) + "\n"
    groups = _group_by_parallel(subtasks)
    accumulated_context = []
    for group in groups:
        if len(group) > 1:
            yield json.dumps({"type": "status", "content": f"Running {len(group)} subtasks in parallel"}) + "\n"
            ctx_for_group = list(accumulated_context)
            if ctx_for_group:
                ctx_str = "\n\n".join(f"Subtask {s.id} result: {s.result or s.error}" for s in ctx_for_group)
            else:
                ctx_str = ""
            tasks = [
                _run_subtask(s, message, project_context + "\n\n" + ctx_str if ctx_str else project_context, coder, history, get_agent_fn)
                for s in group
            ]
            results = await asyncio.gather(*tasks)
            for s in results:
                accumulated_context.append(s)
                if s.result:
                    yield json.dumps({"type": "step", "phase": "observe", "message": f"Subtask {s.id} done"}) + "\n"
                    yield json.dumps({"type": "token", "content": f"\n--- Subtask {s.id} ---\n{s.result}\n"}) + "\n"
                if s.error:
                    yield json.dumps({"type": "status", "content": f"Subtask {s.id} error: {s.error}"}) + "\n"
        else:
            s = group[0]
            yield json.dumps({"type": "status", "content": f"Subtask {s.id}: {s.task[:60]}…"}) + "\n"
            ctx_str = "\n\n".join(f"Subtask {x.id} result: {x.result or x.error}" for x in accumulated_context) if accumulated_context else ""
            async for chunk in _run_subtask_stream(
                s, message, project_context + "\n\n" + ctx_str if ctx_str else project_context, coder, history, get_agent_fn
            ):
                yield chunk
            accumulated_context.append(s)
            if s.error:
                yield json.dumps({"type": "status", "content": f"Subtask {s.id} error: {s.error}"}) + "\n"
    summary = "\n\n".join(f"**Subtask {s.id}**: {s.result or s.error or '—'}" for s in accumulated_context)
    yield json.dumps({"type": "token", "content": f"\n\n## Summary\n\n{summary}"}) + "\n"
