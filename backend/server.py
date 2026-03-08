import asyncio
import json
import urllib.request
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from chat_db import (
    add_message,
    create_conversation,
    delete_conversations,
    get_messages,
    list_conversations,
    set_conversation_title,
)
from config import (
    KV_WARM_ENABLED,
    LLM_MODEL,
    MULTI_AGENT_ORCHESTRATOR_ENABLED,
    MULTI_MODEL_ENABLED,
    OLLAMA_BASE_URL,
    PREFERRED_MODELS,
)
from file_tree import get_file_tree, read_file_content

try:
    from logger import get_logger
    log = get_logger("server")
except Exception:
    import logging
    log = logging.getLogger("server")
    log.setLevel(logging.INFO)
    if not log.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(h)
app = FastAPI(title="AI Codec API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

current_model = LLM_MODEL
_agent_cache: dict = {}


def get_ollama_models():
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception as e:
        log.debug("get_ollama_models failed: %s", e)
        return []


models = get_ollama_models()
if models and current_model not in models:
    for m in PREFERRED_MODELS:
        if m in models:
            current_model = m
            break
    else:
        current_model = models[0]
    log.warning("model '%s' not found, using '%s'", LLM_MODEL, current_model)


def get_agent(mode: str = "agent", model: Optional[str] = None):
    from agent import build_agent
    m = model or current_model
    key = (m, mode)
    if key not in _agent_cache:
        _agent_cache[key] = build_agent(m, mode)
    return _agent_cache[key]


class VisualInteraction(BaseModel):
    type: Optional[str] = "click"
    x: Optional[float] = 0
    y: Optional[float] = 0
    w: Optional[float] = None
    h: Optional[float] = None
    x2: Optional[float] = None
    y2: Optional[float] = None
    element: Optional[str] = None
    color: Optional[str] = None


class VisualContext(BaseModel):
    image: Optional[str] = None
    interactions: Optional[list[dict]] = None


class ContextConfig(BaseModel):
    files: Optional[list[str]] = None
    code: Optional[list[dict]] = None
    codebase: Optional[bool] = None
    docs: Optional[list[str]] = None
    git: Optional[dict] = None
    web: Optional[str] = None
    past_chats: Optional[bool] = None
    browser: Optional[bool] = None
    visual: Optional[VisualContext] = None


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None
    context_paths: Optional[list[str]] = None
    context: Optional[ContextConfig] = None
    mode: Optional[str] = "agent"


class ModelUpdate(BaseModel):
    model: str


class DeleteHistoryRequest(BaseModel):
    ids: list[int]


def model_exists(name: str) -> bool:
    return name in get_ollama_models()


def ensure_model_exists(model: str) -> None:
    models = get_ollama_models()
    if model in models:
        return
    hint = f"Model '{model}' not found. Run: ollama pull {model}"
    if models:
        hint += f" — or switch to an available model: {', '.join(models[:8])}{'...' if len(models) > 8 else ''}"
    raise HTTPException(status_code=400, detail=hint)


async def _build_message_with_context(
    message: str,
    context_paths: Optional[list[str]] = None,
    context: Optional["ContextConfig"] = None,
    conversation_id: Optional[int] = None,
    mode: Optional[str] = None,
) -> str:
    from context_builders import (
        build_code_context,
        build_codebase_context,
        build_docs_context,
        build_files_context,
        build_git_context,
        build_past_chats_context,
        build_project_context,
        build_project_file_context,
        build_web_context,
    )
    sections = []
    files = list(context_paths or [])
    if context and context.files:
        files.extend(context.files)
    tasks = []
    task_keys = []
    project_file = asyncio.to_thread(build_project_file_context)
    tasks.append(project_file)
    task_keys.append("project_file")
    tasks.append(asyncio.to_thread(build_project_context))
    task_keys.append("project")
    if context:
        if context.code:
            tasks.append(asyncio.to_thread(build_code_context, context.code))
            task_keys.append("code")
        if context.codebase:
            tasks.append(asyncio.to_thread(build_codebase_context, message))
            task_keys.append("codebase")
        if context.docs:
            tasks.append(asyncio.to_thread(build_docs_context, context.docs))
            task_keys.append("docs")
        if context.git:
            tasks.append(asyncio.to_thread(
                build_git_context,
                ref=context.git.get("ref"),
                diff=context.git.get("diff", False),
                n=int(context.git.get("n", 5)),
            ))
            task_keys.append("git")
        if context.web:
            tasks.append(asyncio.to_thread(build_web_context, context.web))
            task_keys.append("web")
        if context.past_chats:
            tasks.append(asyncio.to_thread(build_past_chats_context, conversation_id))
            task_keys.append("past_chats")
    if files:
        tasks.append(asyncio.to_thread(build_files_context, files))
        task_keys.append("files")
    order = ["project_file", "project", "files", "code", "codebase", "docs", "git", "web", "past_chats"]
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        result_map = {}
        for key, r in zip(task_keys, results):
            if isinstance(r, Exception):
                log.debug("context builder %s failed: %s", key, r)
                continue
            if r:
                result_map[key] = r
        for key in order:
            if key in result_map:
                sections.append(result_map[key])
    if context and context.browser:
        sections.append("[Browser context requested: User may want to inspect browser state. Use available tools.]")
    if not sections:
        return message
    instruction = (
        "Use the project context below to orient yourself and decide your next action. "
        "The project type and file structure tell you where to add files, what patterns to follow, and what tools exist. "
        "Prefer acting on the provided context directly—do not re-read files already in context unless you need to verify current state. "
        "Apply the user's prompt to the context: edit, analyze, fix, or answer based on what they asked."
    )
    return f"[Context - use for the user's request]\n{instruction}\n\n" + "\n\n".join(sections) + "\n\n--- User message ---\n\n" + message


async def stream_agent_events_with_history(
    message: str,
    conversation_id: Optional[int] = None,
    context_paths: Optional[list[str]] = None,
    context: Optional["ContextConfig"] = None,
    mode: str = "agent",
) -> AsyncGenerator[str, None]:
    conv_id = conversation_id
    is_new = conv_id is None
    if is_new:
        conv_id = create_conversation("New chat")
        add_message(conv_id, "user", message)
        yield json.dumps({"type": "conversation", "id": conv_id, "title": "New chat"}) + "\n"
    else:
        add_message(conv_id, "user", message)

    selected_model = current_model
    plan_prefix = ""
    _conv = (message or "").strip().lower()
    _greetings = ("hi", "hello", "hey", "hi there", "hello there", "thanks", "thank you", "bye", "ok", "okay", "yes", "no")
    if len(_conv) <= 50 and (_conv in _greetings or _conv.rstrip("!?.") in _greetings):
        try:
            from langchain_ollama import ChatOllama
            from langchain_core.messages import HumanMessage
            llm = ChatOllama(model=current_model, base_url=OLLAMA_BASE_URL, temperature=0.3, num_predict=80)
            reply = await asyncio.to_thread(
                llm.invoke,
                [HumanMessage(content=f"User said: {message}\n\nReply briefly and naturally as a friendly coding assistant. One short sentence.")],
            )
            content = (getattr(reply, "content", "") or str(reply)).strip()
            if content:
                add_message(conv_id, "assistant", content)
                for ch in content:
                    yield json.dumps({"type": "token", "content": ch}) + "\n"
                if is_new:
                    try:
                        from title_gen import generate_chat_title
                        title = await asyncio.to_thread(generate_chat_title, message)
                        set_conversation_title(conv_id, title)
                        yield json.dumps({"type": "conversation_title", "id": conv_id, "title": title}) + "\n"
                    except Exception:
                        pass
                return
        except Exception as e:
            log.debug("conversational reply failed: %s", e)
    use_visual_flow = context and context.visual and context.visual.image
    if use_visual_flow:
        models = get_ollama_models()
        try:
            from visual_agents import process_visual_request, MODEL_VL
            if MODEL_VL in models or any(m in models for m in ["llava", "llama3.2-vision", "qwen3-vl"]):
                result = await asyncio.to_thread(
                    process_visual_request,
                    message,
                    context.visual.image,
                    context.visual.interactions or [],
                    models,
                )
                add_message(conv_id, "assistant", result)
                yield json.dumps({"type": "phase", "phase": "streaming"}) + "\n"
                for ch in result:
                    yield json.dumps({"type": "token", "content": ch}) + "\n"
                if is_new:
                    try:
                        from title_gen import generate_chat_title
                        title = await asyncio.to_thread(generate_chat_title, message)
                        set_conversation_title(conv_id, title)
                        yield json.dumps({"type": "conversation_title", "id": conv_id, "title": title}) + "\n"
                    except Exception as e:
                        log.debug("title generation failed: %s", e)
                return
        except Exception as e:
            log.exception("visual flow failed: %s", e)
            yield json.dumps({"type": "error", "content": str(e)}) + "\n"
            return
    request_intent = "simple"
    if MULTI_MODEL_ENABLED:
        try:
            from multi_agent import classify_request, build_execution_plan, MODEL_PLANNER, INTENT_HINTS
            models = get_ollama_models()
            selected_model, request_intent = await asyncio.to_thread(classify_request, message, mode, models)
            if selected_model != current_model:
                log.info("multi-model routing: %s -> %s (mode=%s)", current_model, selected_model, mode)
                yield json.dumps({"type": "status", "content": f"Using {selected_model} for this task"}) + "\n"
            if mode == "agent" and selected_model == MODEL_PLANNER and request_intent in ("complex", "plan"):
                plan = await asyncio.to_thread(build_execution_plan, message, selected_model, models)
                if plan:
                    plan_prefix = plan
                    log.info("plan-prep: added execution plan for %s", request_intent)
        except Exception as e:
            log.debug("multi-model routing failed: %s", e)
    intent_hint = ""
    try:
        from multi_agent import INTENT_HINTS
        intent_hint = INTENT_HINTS.get(request_intent, "")
        if intent_hint:
            intent_hint = f"[Request type: {request_intent}] {intent_hint}\n\n"
    except ImportError:
        pass
    agent_message = await _build_message_with_context(intent_hint + plan_prefix + message, context_paths, context, conv_id, mode)
    tokens = []
    msgs = get_messages(conv_id) if conv_id else []
    history = msgs[:-1] if msgs else []
    if plan_prefix:
        yield json.dumps({"type": "phase", "phase": "processing", "step": "Execution plan ready…"}) + "\n"
    from multi_agent import MODEL_CODER, MODEL_PLANNER
    use_orchestrator = (
        MULTI_AGENT_ORCHESTRATOR_ENABLED
        and mode == "agent"
        and (selected_model == MODEL_PLANNER or len(message) > 80)
    )
    orchestrator_succeeded = False
    if use_orchestrator:
        try:
            from context_builders import build_project_context
            from orchestrator import run_orchestrated
            models = get_ollama_models()
            project_ctx = await asyncio.to_thread(build_project_context)
            async for chunk in run_orchestrated(
                message,
                project_ctx,
                selected_model,
                MODEL_CODER if MODEL_CODER in models else selected_model,
                models,
                history,
                get_agent,
            ):
                raw = chunk.strip()
                if raw:
                    try:
                        payload = raw[5:].lstrip() if raw.startswith("data:") else raw
                        data = json.loads(payload)
                        if data.get("type") == "orchestrator_fallback":
                            use_orchestrator = False
                            break
                        if data.get("type") == "token" and data.get("content"):
                            tokens.append(data["content"])
                    except (json.JSONDecodeError, ValueError):
                        pass
                yield chunk
            else:
                orchestrator_succeeded = True
        except Exception as e:
            log.info("orchestrator failed, using single agent: %s", e)
            use_orchestrator = False
    if not orchestrator_succeeded:
        try:
            from agent_harness import stream_events as harness_stream_events
            async for chunk in harness_stream_events(get_agent(mode, model=selected_model), agent_message, history=history):
                raw = chunk.strip()
                if raw:
                    try:
                        payload = raw[5:].lstrip() if raw.startswith("data:") else raw
                        data = json.loads(payload)
                        if data.get("type") == "token" and data.get("content"):
                            tokens.append(data["content"])
                    except (json.JSONDecodeError, ValueError):
                        pass
                yield chunk
        except Exception as e:
            log.exception("stream_agent_events failed")
            yield json.dumps({"type": "error", "content": str(e)}) + "\n"
            return

    full_content = "".join(tokens)
    add_message(conv_id, "assistant", full_content)
    if is_new:
        try:
            from title_gen import generate_chat_title
            title = await asyncio.to_thread(generate_chat_title, message)
            set_conversation_title(conv_id, title)
            yield json.dumps({"type": "conversation_title", "id": conv_id, "title": title}) + "\n"
        except Exception as e:
            log.debug("title generation failed: %s", e)


class WarmRequest(BaseModel):
    text: Optional[str] = ""
    model: Optional[str] = ""


@app.post("/warm")
def warm_cache(req: Optional[WarmRequest] = None):
    if not KV_WARM_ENABLED:
        return {"status": "disabled"}
    req = req or WarmRequest()
    text = (req.text or "")[:500]
    m = req.model or current_model
    ensure_model_exists(m)
    try:
        body = json.dumps({
            "model": m,
            "prompt": text or "Hi",
            "stream": False,
            "options": {"num_predict": 1},
            "keep_alive": "5m",
        }).encode()
        http_req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(http_req, timeout=10) as r:
            r.read()
        return {"status": "ok", "model": m}
    except Exception as e:
        log.debug("warm failed: %s", e)
        return {"status": "error", "detail": str(e)}


@app.get("/health")
def health():
    ollama_ok = False
    model_available = False
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as r:
            if r.status == 200:
                ollama_ok = True
                model_available = model_exists(current_model)
    except Exception as e:
        log.debug("health ollama check failed: %s", e)
    return {"status": "ok", "ollama": ollama_ok, "model_available": model_available, "model": current_model}


@app.get("/history")
def get_history(limit: int = 100, offset: int = 0):
    try:
        items, total = list_conversations(limit=limit, offset=offset)
        return {"conversations": items, "total": total}
    except Exception as e:
        log.exception("get_history failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history/export")
def export_history(ids: str = ""):
    try:
        id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
        if not id_list:
            return {"conversations": []}
        convos, _ = list_conversations(limit=10000, offset=0)
        result = []
        for c in convos:
            if c["id"] in id_list:
                msgs = get_messages(c["id"])
                result.append({"id": c["id"], "title": c["title"], "created_at": c["created_at"], "messages": msgs})
        return {"conversations": result}
    except Exception as e:
        log.exception("export_history failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/history")
def delete_history(req: DeleteHistoryRequest):
    try:
        count = delete_conversations(req.ids)
        return {"deleted": count}
    except Exception as e:
        log.exception("delete_history failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history/{conversation_id}")
def get_conversation_messages(conversation_id: int):
    try:
        messages = get_messages(conversation_id)
        return {"messages": messages}
    except Exception as e:
        log.exception("get_conversation_messages failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
async def chat(req: ChatRequest):
    ensure_model_exists(current_model)
    log.info("chat request: %s (mode=%s)", req.message[:80] + "..." if len(req.message) > 80 else req.message, req.mode or "agent")
    async def gen():
        async for chunk in stream_agent_events_with_history(
            req.message, req.conversation_id, req.context_paths, req.context, req.mode or "agent"
        ):
            yield {"data": chunk}

    return EventSourceResponse(gen())


@app.post("/chat/run")
async def chat_run(req: ChatRequest):
    ensure_model_exists(current_model)
    try:
        from agent_harness import run as harness_run
        agent_message = await _build_message_with_context(
            req.message, req.context_paths, req.context, req.conversation_id, req.mode or "agent"
        )
        history = get_messages(req.conversation_id) if req.conversation_id else None
        mode = req.mode or "agent"
        selected_model = current_model
        if MULTI_MODEL_ENABLED:
            try:
                from multi_agent import select_model_for_request
                models = get_ollama_models()
                selected_model = await asyncio.to_thread(select_model_for_request, req.message, mode, models)
            except Exception:
                pass
        result = await harness_run(get_agent(mode, model=selected_model), agent_message, history=history)
        return {"content": result["content"], "tool_calls": result["tool_calls"], "error": result["error"]}
    except Exception as e:
        log.exception("chat_run failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/models")
def list_models():
    models = get_ollama_models()
    return {"provider": "Ollama", "models": models}


@app.get("/model")
def get_model():
    return {"provider": "Ollama", "model": current_model}


@app.patch("/model")
def set_model(req: ModelUpdate):
    global _agent_cache, current_model
    models = get_ollama_models()
    if models and req.model not in models:
        raise HTTPException(status_code=400, detail=f"Model not found: {req.model}. Available: {', '.join(models[:10])}{'...' if len(models) > 10 else ''}")
    current_model = req.model
    _agent_cache.clear()
    log.info("model set to %s", current_model)
    return {"provider": "Ollama", "model": current_model}


def _etag_for_tree(tree: list) -> str:
    import hashlib
    data = json.dumps(tree, sort_keys=True)
    return hashlib.md5(data.encode()).hexdigest()


@app.get("/files/tree")
def files_tree(if_none_match: Optional[str] = Header(None)):
    try:
        tree = get_file_tree()
        etag = _etag_for_tree(tree)
        if if_none_match and if_none_match.strip('"') == etag:
            return Response(status_code=304)
        return JSONResponse(content={"tree": tree}, headers={"ETag": f'"{etag}"', "Cache-Control": "private, max-age=10"})
    except Exception as e:
        log.exception("files_tree failed")
        raise HTTPException(status_code=500, detail=str(e))


def _etag_for_file(path: str) -> str:
    import hashlib
    from config import WORKSPACE_ROOT
    try:
        p = (WORKSPACE_ROOT / path).resolve()
        mtime = p.stat().st_mtime if p.exists() else 0
    except OSError:
        mtime = 0
    return hashlib.md5(f"{path}:{mtime}".encode()).hexdigest()


@app.get("/files/content")
def files_content(path: str = "", if_none_match: Optional[str] = Header(None)):
    if not path:
        raise HTTPException(status_code=400, detail="path required")
    try:
        content, ext = read_file_content(path)
        etag = _etag_for_file(path)
        if if_none_match and if_none_match.strip('"') == etag:
            return Response(status_code=304)
        return JSONResponse(
            content={"content": content, "language": _ext_to_language(ext)},
            headers={"ETag": f'"{etag}"', "Cache-Control": "private, max-age=30"},
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Path outside workspace")
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception("files_content failed")
        raise HTTPException(status_code=500, detail=str(e))


def _ext_to_language(ext: str) -> str:
    m = {
        ".py": "python", ".js": "javascript", ".ts": "typescript", ".jsx": "javascript",
        ".tsx": "typescript", ".json": "json", ".md": "markdown", ".html": "html",
        ".css": "css", ".scss": "scss", ".yaml": "yaml", ".yml": "yaml",
        ".sh": "shell", ".bash": "shell", ".sql": "sql", ".xml": "xml",
        ".go": "go", ".rs": "rust", ".java": "java", ".kt": "kotlin",
        ".cs": "csharp", ".cpp": "cpp", ".c": "c", ".h": "c",
    }
    return m.get(ext, "plaintext")


@app.post("/index")
async def index_workspace():
    log.info("index_workspace started")
    try:
        from semantic_index import get_vector_store, index_workspace_files
        store = get_vector_store(clear=True)
        count = index_workspace_files(store)
        log.info("index_workspace done: indexed %s files", count)
        return {"status": "ok", "indexed": count}
    except Exception as e:
        log.exception("index_workspace failed")
        raise HTTPException(status_code=500, detail=str(e))


def run_server(host: str = "127.0.0.1", port: int = 8765):
    import uvicorn
    log.info("starting server %s:%s", host, port)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
