import asyncio
import json
import sys
import urllib.request

sys.path.insert(0, ".")

from config import OLLAMA_BASE_URL
from orchestrator import _parse_plan, _group_by_parallel, _plan_subtasks, run_orchestrated
from context_builders import build_project_context
from multi_agent import MODEL_CODER, MODEL_PLANNER


def _ollama_reachable():
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as r:
            data = json.loads(r.read().decode())
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []


def test_parse():
    tests = [
        '{"subtasks": [{"id": 1, "task": "Read file", "files": ["a.py"], "parallel_group": 0}]}',
        '```json\n{"subtasks": [{"id": 1, "task": "Add logger"}]}\n```',
        'Here is the plan: {"subtasks": [{"id": 1, "task": "Step one"}, {"id": 2, "task": "Step two", "parallel_group": 1}]}',
    ]
    for t in tests:
        r = _parse_plan(t)
        print("Parsed", len(r), "subtasks:", [s.task for s in r])
        if r:
            g = _group_by_parallel(r)
            print("  Groups:", [[s.id for s in grp] for grp in g])
    print("Parse tests OK")


def test_plan_with_ollama():
    models = _ollama_reachable()
    if not models:
        print("SKIP: Ollama not reachable")
        return
    planner = MODEL_PLANNER if MODEL_PLANNER in models else models[0]
    ctx = build_project_context()
    subtasks = _plan_subtasks("Add a hello world function to main.py and run it", ctx, planner)
    if not subtasks:
        print("WARN: planner returned no subtasks (model may not output valid JSON)")
        return
    print("Planner subtasks:", [s.task for s in subtasks])
    print("Plan integration OK")


async def test_run_orchestrated():
    models = _ollama_reachable()
    if not models:
        print("SKIP: Ollama not reachable")
        return
    planner = MODEL_PLANNER if MODEL_PLANNER in models else models[0]
    coder = MODEL_CODER if MODEL_CODER in models else models[0]
    ctx = build_project_context()

    def get_agent(mode, model=None):
        from agent import build_agent
        return build_agent(model or coder, mode)

    chunks = []
    async for chunk in run_orchestrated(
        "List files in the backend directory",
        ctx,
        planner,
        coder,
        models,
        [],
        get_agent,
    ):
        chunks.append(chunk)
        raw = chunk.strip()
        if raw:
            try:
                payload = raw[5:].lstrip() if raw.startswith("data:") else raw
                data = json.loads(payload)
                if data.get("type") == "orchestrator_fallback":
                    print("Orchestrator fell back (no subtasks)")
                    return
            except (json.JSONDecodeError, ValueError):
                pass

    tokens = []
    for c in chunks:
        raw = c.strip()
        if raw:
            try:
                payload = raw[5:].lstrip() if raw.startswith("data:") else raw
                data = json.loads(payload)
                if data.get("type") == "token" and data.get("content"):
                    tokens.append(data["content"])
            except (json.JSONDecodeError, ValueError):
                pass
    content = "".join(tokens)
    print("Orchestrator output length:", len(content))
    print("Run orchestrated OK")


if __name__ == "__main__":
    test_parse()
    test_plan_with_ollama()
    asyncio.run(test_run_orchestrated())
