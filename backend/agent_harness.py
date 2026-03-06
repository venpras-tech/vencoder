import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from config import AGENT_MAX_STEPS, AGENT_TIMEOUT_SEC, MAX_HISTORY_MESSAGES, STEP_TIMEOUT_SEC

log = logging.getLogger("agent_harness")


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

    _init_agent_run()
    yield json.dumps({"type": "phase", "phase": "processing", "step": "Initializing…"}) + "\n"
    yield json.dumps({"type": "step", "phase": "think", "step": 0, "message": "Planning response…"}) + "\n"

    try:
        astream = agent.astream_events(inputs, config=config, version="v2")
        while True:
            try:
                event = await asyncio.wait_for(astream.__anext__(), timeout=step_timeout)
            except asyncio.TimeoutError:
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
                yield json.dumps({
                    "type": "step",
                    "phase": "think",
                    "step": step_num,
                    "message": "Thinking…",
                }) + "\n"
                yield json.dumps({"type": "phase", "phase": "think", "step": step_num}) + "\n"
            elif kind == "on_tool_start":
                tool_count += 1
                if limit and tool_count > limit:
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
            elif kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk", {})
                if hasattr(chunk, "content") and chunk.content:
                    if not stream_started:
                        stream_started = True
                        yield json.dumps({"type": "phase", "phase": "streaming"}) + "\n"
                    yield json.dumps({"type": "token", "content": chunk.content}) + "\n"
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
            elif kind == "on_chain_error":
                err = event.get("data", {}).get("error", "Unknown error")
                log.error("chain_error: %s", err)
                yield json.dumps({"type": "error", "content": str(err)}) + "\n"
                break
    except asyncio.CancelledError:
        yield json.dumps({"type": "error", "content": "Agent run cancelled"}) + "\n"
        raise
    except Exception as e:
        log.exception("harness stream_events failed")
        yield json.dumps({"type": "error", "content": str(e)}) + "\n"


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
