import asyncio
import json
import logging
import queue
import threading
import time
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from config import AGENT_MAX_STEPS, AGENT_TIMEOUT_SEC, MAX_HISTORY_MESSAGES, RUN_LLM_IN_THREAD, STEP_TIMEOUT_SEC

MAX_HISTORY_MSG_CHARS = 4000

try:
    from logger import get_logger
    log = get_logger("agent_harness")
except Exception:
    import logging
    log = logging.getLogger("agent_harness")

_active_cancel_events: set = set()
_events_lock = threading.Lock()


def _register_cancel_event(e: threading.Event) -> None:
    with _events_lock:
        _active_cancel_events.add(e)


def _unregister_cancel_event(e: threading.Event) -> None:
    with _events_lock:
        _active_cancel_events.discard(e)


def shutdown_llm_threads() -> None:
    with _events_lock:
        for e in _active_cancel_events:
            e.set()


def _response_meta_json(token_count: int, start_time: float, stop_reason: str) -> str:
    duration_ms = int((time.monotonic() - start_time) * 1000)
    tok_per_sec = token_count / (duration_ms / 1000) if duration_ms > 0 else 0
    return json.dumps({
        "type": "response_meta",
        "tokens": token_count,
        "duration_ms": duration_ms,
        "tok_per_sec": round(tok_per_sec, 2),
        "stop_reason": stop_reason,
    })


def _emit_log(level: str, message: str, model: str = "", extra: Optional[dict] = None) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = f"[{model}] " if model else ""
    return json.dumps({"type": "log", "level": level, "message": f"{ts} [{level}] {prefix}{message}", "extra": extra or {}})


def _init_agent_run():
    try:
        from tools.agent_context import init_agent_run
        init_agent_run()
    except ImportError:
        pass


def _step_timeout_for_run(timeout_sec: Optional[int]) -> int:
    if timeout_sec is not None and timeout_sec > 0:
        return min(timeout_sec, STEP_TIMEOUT_SEC)
    return STEP_TIMEOUT_SEC


def _to_langchain_messages(history: list) -> list[BaseMessage]:
    out = []
    for m in history[-MAX_HISTORY_MESSAGES:]:
        role, content = m.get("role", ""), m.get("content", "")
        if MAX_HISTORY_MSG_CHARS > 0 and len(content) > MAX_HISTORY_MSG_CHARS:
            content = content[:MAX_HISTORY_MSG_CHARS] + "\n[... truncated ...]"
        if role == "user":
            out.append(HumanMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
    return out


async def stream_events(
    agent: Any,
    message: str,
    config: Optional[Dict[str, Any]] = None,
    timeout_sec: Optional[int] = None,
    max_steps: Optional[int] = None,
    history: Optional[list] = None,
    model_name: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    timeout = timeout_sec if timeout_sec is not None else (AGENT_TIMEOUT_SEC if AGENT_TIMEOUT_SEC > 0 else None)
    step_timeout = _step_timeout_for_run(timeout_sec)
    limit = max_steps if max_steps is not None else (AGENT_MAX_STEPS if AGENT_MAX_STEPS > 0 else None)
    config = config or {"configurable": {}}
    if "recursion_limit" not in config:
        config = {**config, "recursion_limit": 100}
    messages = _to_langchain_messages(history) if history else []
    messages.append(HumanMessage(content=message))
    inputs = {"messages": messages}
    tool_count = 0
    stream_started = False
    step_num = 0
    token_count = 0
    model = model_name or ""
    start_time = time.monotonic()
    stop_reason = "complete"

    _init_agent_run()
    yield json.dumps({"type": "phase", "phase": "processing", "step": "Initializing…"}) + "\n"
    yield json.dumps({"type": "step", "phase": "think", "step": 0, "message": "Planning response…"}) + "\n"
    yield _emit_log("INFO", "Agent run started", model) + "\n"

    try:
        astream = agent.astream_events(inputs, config=config, version="v2")
        while True:
            try:
                event = await asyncio.wait_for(astream.__anext__(), timeout=step_timeout)
            except asyncio.TimeoutError:
                stop_reason = "timeout"
                yield json.dumps({
                    "type": "error",
                    "content": f"Agent step timed out after {step_timeout}s",
                }) + "\n"
                break
            except StopAsyncIteration:
                break

            kind = event.get("event")
            if kind == "on_chat_model_start":
                step_num += 1
                token_count = 0
                yield json.dumps({
                    "type": "step",
                    "phase": "think",
                    "step": step_num,
                    "message": "Thinking…",
                }) + "\n"
                yield json.dumps({"type": "phase", "phase": "think", "step": step_num}) + "\n"
                yield _emit_log("INFO", "Prompt processing started", model, {"n_tokens": 0}) + "\n"
            elif kind == "on_tool_start":
                tool_count += 1
                if limit and tool_count > limit:
                    stop_reason = "max_steps"
                    log.warning("max_steps exceeded: %s", limit)
                    yield json.dumps({
                        "type": "error",
                        "content": f"Agent exceeded max steps ({limit})",
                    }) + "\n"
                    break
                name = event.get("name", "?")
                log.info("tool_start: %s", name)
                yield json.dumps({
                    "type": "step",
                    "phase": "action",
                    "step": step_num,
                    "message": f"Action: {name}",
                    "tool": name,
                }) + "\n"
                yield json.dumps({"type": "tool_start", "tool": name}) + "\n"
                yield json.dumps({"type": "status", "content": f"Executing: {name}"}) + "\n"
                yield _emit_log("INFO", f"Tool: {name}", model) + "\n"
                if name in ("shell_command", "run_tests"):
                    inp = event.get("data", {}).get("input", {}) or {}
                    cmd = inp.get("command", "") if isinstance(inp, dict) else ""
                    if name == "run_tests" and not cmd:
                        cmd = "pytest"
                    yield json.dumps({"type": "shell_start", "command": cmd}) + "\n"
            elif kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk", {})
                if hasattr(chunk, "content") and chunk.content:
                    if not stream_started:
                        stream_started = True
                        yield json.dumps({"type": "phase", "phase": "streaming"}) + "\n"
                    yield json.dumps({"type": "token", "content": chunk.content}) + "\n"
                    token_count += 1
                    if token_count % 64 == 0:
                        yield _emit_log("DEBUG", f"Generating… {token_count} tokens", model, {"n_tokens": token_count}) + "\n"
            elif kind == "on_tool_end":
                name = event.get("name", "?")
                raw = event.get("data", {}).get("output", "")
                output = getattr(raw, "content", raw) if raw else ""
                output_str = str(output) if not isinstance(output, str) else output
                summary = output_str
                yield json.dumps({
                    "type": "step",
                    "phase": "observe",
                    "step": step_num,
                    "message": f"Observed: {name}",
                    "tool": name,
                }) + "\n"
                if "\n__UI__\n" in output_str:
                    parts = output_str.split("\n__UI__\n", 1)
                    summary = parts[0]
                    try:
                        ui = json.loads(parts[1])
                        if ui.get("type") == "file_edit":
                            yield json.dumps({
                                "type": "file_edit",
                                "path": ui.get("path", ""),
                                "old": ui.get("old", ""),
                                "new": ui.get("new", ""),
                            }) + "\n"
                        elif ui.get("type") == "shell_run":
                            yield json.dumps({
                                "type": "shell_run",
                                "command": ui.get("command", ""),
                                "stdout": ui.get("stdout", ""),
                                "stderr": ui.get("stderr", ""),
                                "exit_code": ui.get("exit_code", 0),
                            }) + "\n"
                    except (json.JSONDecodeError, TypeError):
                        pass
                preview = (summary[:500] + "…") if len(summary) > 500 else summary
                yield json.dumps({
                    "type": "tool_done",
                    "tool": name,
                    "preview": preview,
                }) + "\n"
                yield _emit_log("INFO", f"Tool done: {name}", model, {"preview": preview[:100]}) + "\n"
            elif kind == "on_chain_error":
                stop_reason = "error"
                err = event.get("data", {}).get("error", "Unknown error")
                log.error("chain_error: %s", err)
                yield json.dumps({"type": "error", "content": str(err)}) + "\n"
                break
    except asyncio.CancelledError:
        stop_reason = "User Stopped"
        yield json.dumps({"type": "error", "content": "Agent run cancelled"}) + "\n"
        yield _response_meta_json(token_count, start_time, stop_reason) + "\n"
        raise
    except Exception as e:
        stop_reason = "error"
        log.exception("harness stream_events failed")
        yield json.dumps({"type": "error", "content": str(e)}) + "\n"
        yield _response_meta_json(token_count, start_time, stop_reason) + "\n"
        return
    yield _response_meta_json(token_count, start_time, stop_reason) + "\n"


def _run_stream_in_thread(
    agent: Any,
    message: str,
    config: Optional[Dict[str, Any]],
    timeout_sec: Optional[int],
    max_steps: Optional[int],
    history: Optional[list],
    model_name: Optional[str],
    chunk_queue: queue.Queue,
    cancel_event: threading.Event,
) -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        async def consume():
            try:
                async for chunk in stream_events(
                    agent, message, config, timeout_sec, max_steps, history, model_name
                ):
                    if cancel_event.is_set():
                        break
                    chunk_queue.put(chunk)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                if not cancel_event.is_set():
                    chunk_queue.put(json.dumps({"type": "error", "content": str(e)}) + "\n")
            finally:
                chunk_queue.put(None)

        async def watch_cancel(consume_task: asyncio.Task) -> None:
            while not cancel_event.is_set():
                await asyncio.sleep(0.2)
            consume_task.cancel()

        async def run():
            consume_task = loop.create_task(consume())
            cancel_task = loop.create_task(watch_cancel(consume_task))
            try:
                await consume_task
            except asyncio.CancelledError:
                pass
            finally:
                cancel_task.cancel()
                try:
                    await cancel_task
                except asyncio.CancelledError:
                    pass

        loop.run_until_complete(run())
    finally:
        loop.close()


async def stream_events_maybe_threaded(
    agent: Any,
    message: str,
    config: Optional[Dict[str, Any]] = None,
    timeout_sec: Optional[int] = None,
    max_steps: Optional[int] = None,
    history: Optional[list] = None,
    model_name: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    if not RUN_LLM_IN_THREAD:
        async for chunk in stream_events(agent, message, config, timeout_sec, max_steps, history, model_name):
            yield chunk
        return

    cancel_event = threading.Event()
    _register_cancel_event(cancel_event)
    chunk_queue = queue.Queue()
    thread = threading.Thread(
        target=_run_stream_in_thread,
        args=(agent, message, config, timeout_sec, max_steps, history, model_name, chunk_queue, cancel_event),
        daemon=True,
    )
    thread.start()
    loop = asyncio.get_event_loop()
    try:
        while True:
            chunk = await loop.run_in_executor(None, chunk_queue.get)
            if chunk is None:
                break
            yield chunk
    except asyncio.CancelledError:
        cancel_event.set()
        raise
    finally:
        _unregister_cancel_event(cancel_event)


async def run(
    agent: Any,
    message: str,
    config: Optional[Dict[str, Any]] = None,
    timeout_sec: Optional[int] = None,
    max_steps: Optional[int] = None,
    history: Optional[list] = None,
) -> Dict[str, Any]:
    tokens = []
    tool_calls = []
    error_msg = None
    config = config or {"configurable": {}}
    if "recursion_limit" not in config:
        config = {**config, "recursion_limit": 100}

    async def consume():
        nonlocal error_msg
        async for line in stream_events(agent, message, config, timeout_sec, max_steps, history):
            raw = line.strip()
            if not raw:
                continue
            payload = raw[6:] if raw.startswith("data: ") else raw
            try:
                data = json.loads(payload)
                if data.get("type") == "token" and data.get("content"):
                    tokens.append(data["content"])
                elif data.get("type") == "tool_start":
                    tool_calls.append({"tool": data.get("tool", "?"), "done": False})
                elif data.get("type") == "tool_done":
                    for t in reversed(tool_calls):
                        if not t.get("done"):
                            t["done"] = True
                            t["preview"] = data.get("preview", "")
                            break
                elif data.get("type") == "error":
                    error_msg = data.get("content", "Unknown error")
            except json.JSONDecodeError:
                pass

    if timeout_sec and timeout_sec > 0:
        await asyncio.wait_for(consume(), timeout=timeout_sec)
    else:
        await consume()

    return {
        "content": "".join(tokens),
        "tool_calls": tool_calls,
        "error": error_msg,
    }
