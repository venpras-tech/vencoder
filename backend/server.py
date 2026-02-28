import asyncio
import json
import urllib.request
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException
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
from config import LLM_MODEL, OLLAMA_BASE_URL
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
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        from agent import build_agent
        _agent = build_agent(current_model)
    return _agent


class ContextConfig(BaseModel):
    files: Optional[list[str]] = None
    code: Optional[list[dict]] = None
    codebase: Optional[bool] = None
    docs: Optional[list[str]] = None
    git: Optional[dict] = None
    web: Optional[str] = None
    past_chats: Optional[bool] = None
    browser: Optional[bool] = None


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None
    context_paths: Optional[list[str]] = None
    context: Optional[ContextConfig] = None


class ModelUpdate(BaseModel):
    model: str


class DeleteHistoryRequest(BaseModel):
    ids: list[int]


def get_ollama_models():
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception as e:
        log.debug("get_ollama_models failed: %s", e)
        return []


def _build_message_with_context(
    message: str,
    context_paths: Optional[list[str]] = None,
    context: Optional["ContextConfig"] = None,
    conversation_id: Optional[int] = None,
) -> str:
    from context_builders import (
        build_code_context,
        build_codebase_context,
        build_docs_context,
        build_files_context,
        build_git_context,
        build_past_chats_context,
        build_web_context,
    )
    sections = []
    files = list(context_paths or [])
    if context:
        if context.files:
            files.extend(context.files)
        if context.code:
            s = build_code_context(context.code)
            if s:
                sections.append(s)
        if context.codebase:
            s = build_codebase_context(message)
            if s:
                sections.append(s)
        if context.docs:
            s = build_docs_context(context.docs)
            if s:
                sections.append(s)
        if context.git:
            s = build_git_context(
                ref=context.git.get("ref"),
                diff=context.git.get("diff", False),
                n=int(context.git.get("n", 5)),
            )
            if s:
                sections.append(s)
        if context.web:
            s = build_web_context(context.web)
            if s:
                sections.append(s)
        if context.past_chats:
            s = build_past_chats_context(conversation_id)
            if s:
                sections.append(s)
        if context.browser:
            sections.append("[Browser context requested: User may want to inspect browser state. Use available tools.]")
    if files:
        s = build_files_context(files)
        if s:
            sections.insert(0, s)
    if not sections:
        return message
    instruction = (
        "The user has provided context below. Use it to perform the requested action. "
        "Prefer acting on the provided context directly—do not re-read files already in context unless you need to verify current state. "
        "Apply the user's prompt to the context: edit, analyze, fix, or answer based on what they asked."
    )
    return f"[Context - use for the user's request]\n{instruction}\n\n" + "\n\n".join(sections) + "\n\n--- User message ---\n\n" + message


async def stream_agent_events_with_history(
    message: str,
    conversation_id: Optional[int] = None,
    context_paths: Optional[list[str]] = None,
    context: Optional["ContextConfig"] = None,
) -> AsyncGenerator[str, None]:
    conv_id = conversation_id
    is_new = conv_id is None
    if is_new:
        conv_id = create_conversation("New chat")
        add_message(conv_id, "user", message)
        yield json.dumps({"type": "conversation", "id": conv_id, "title": "New chat"}) + "\n"
    else:
        add_message(conv_id, "user", message)

    agent_message = _build_message_with_context(message, context_paths, context, conv_id)
    tokens = []
    msgs = get_messages(conv_id) if conv_id else []
    history = msgs[:-1] if msgs else []
    try:
        from agent_harness import stream_events as harness_stream_events
        async for chunk in harness_stream_events(get_agent(), agent_message, history=history):
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


@app.get("/health")
def health():
    ollama_ok = False
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as r:
            if r.status == 200:
                ollama_ok = True
    except Exception as e:
        log.debug("health ollama check failed: %s", e)
    return {"status": "ok", "ollama": ollama_ok}


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
    log.info("chat request: %s", req.message[:80] + "..." if len(req.message) > 80 else req.message)
    async def gen():
        async for chunk in stream_agent_events_with_history(
            req.message, req.conversation_id, req.context_paths, req.context
        ):
            yield {"data": chunk}

    return EventSourceResponse(gen())


@app.post("/chat/run")
async def chat_run(req: ChatRequest):
    try:
        from agent_harness import run as harness_run
        agent_message = _build_message_with_context(
            req.message, req.context_paths, req.context, req.conversation_id
        )
        history = get_messages(req.conversation_id) if req.conversation_id else None
        result = await harness_run(get_agent(), agent_message, history=history)
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
    global _agent, current_model
    models = get_ollama_models()
    if models and req.model not in models:
        raise HTTPException(status_code=400, detail=f"Model not found: {req.model}. Available: {', '.join(models[:10])}{'...' if len(models) > 10 else ''}")
    current_model = req.model
    from agent import build_agent
    _agent = build_agent(current_model)
    log.info("model set to %s", current_model)
    return {"provider": "Ollama", "model": current_model}


@app.get("/files/tree")
def files_tree():
    try:
        tree = get_file_tree()
        return {"tree": tree}
    except Exception as e:
        log.exception("files_tree failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/files/content")
def files_content(path: str = ""):
    if not path:
        raise HTTPException(status_code=400, detail="path required")
    try:
        content, ext = read_file_content(path)
        return {"content": content, "language": _ext_to_language(ext)}
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
