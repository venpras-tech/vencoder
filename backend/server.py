import asyncio
import json
import urllib.request
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agent import build_agent
from agent_harness import run as harness_run, stream_events as harness_stream_events
from chat_db import (
    add_message,
    create_conversation,
    get_messages,
    list_conversations,
    set_conversation_title,
)
from config import LLM_MODEL, OLLAMA_BASE_URL
from semantic_index import get_vector_store, index_workspace_files
from title_gen import generate_chat_title

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
agent = build_agent(current_model)


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None


class ModelUpdate(BaseModel):
    model: str


def get_ollama_models():
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception as e:
        log.debug("get_ollama_models failed: %s", e)
        return []


async def stream_agent_events_with_history(
    message: str, conversation_id: Optional[int] = None
) -> AsyncGenerator[str, None]:
    global agent
    conv_id = conversation_id
    is_new = conv_id is None
    if is_new:
        conv_id = create_conversation("New chat")
        add_message(conv_id, "user", message)
        yield json.dumps({"type": "conversation", "id": conv_id, "title": "New chat"}) + "\n"
    else:
        add_message(conv_id, "user", message)

    tokens = []
    try:
        async for chunk in harness_stream_events(agent, message):
            if chunk.strip().startswith("data:"):
                try:
                    data = json.loads(chunk.strip()[5:].strip())
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
def get_history():
    try:
        items = list_conversations()
        return {"conversations": items}
    except Exception as e:
        log.exception("get_history failed")
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
            req.message, req.conversation_id
        ):
            yield {"data": chunk}

    return EventSourceResponse(gen())


@app.post("/chat/run")
async def chat_run(req: ChatRequest):
    global agent
    try:
        result = await harness_run(agent, req.message)
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
    global agent, current_model
    current_model = req.model
    log.info("model set to %s", current_model)
    agent = build_agent(current_model)
    return {"provider": "Ollama", "model": current_model}


@app.post("/index")
async def index_workspace():
    log.info("index_workspace started")
    try:
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
