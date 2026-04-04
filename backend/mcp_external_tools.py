import asyncio
import json
import os
import re
import threading
from typing import Any, Dict, List, Optional, Type

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field, create_model

from settings_db import get_mcp_settings as _db_get_mcp_settings, set_mcp_setting
from tools.duplicate_wrapper import wrap_tools_with_duplicate_check

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    ClientSession = None
    StdioServerParameters = None
    stdio_client = None

try:
    from logger import get_logger
    log = get_logger("mcp_external_tools")
except Exception:
    import logging
    log = logging.getLogger("mcp_external_tools")

_tools_cache: Optional[List[Any]] = None
_tools_cache_key: str = ""

MAX_SERVERS = 12
MAX_TOOLS_PER_SERVER = 40


def get_servers_config() -> List[Dict[str, Any]]:
    try:
        settings = _db_get_mcp_settings()
        raw = settings.get("servers", [])
    except Exception:
        raw = []
    if not isinstance(raw, list):
        return []
    return raw[:MAX_SERVERS]


def set_mcp_settings(servers: List[Dict[str, Any]]) -> None:
    set_mcp_setting("external_servers", servers)


def _sanitize_name(s: str) -> str:
    out = re.sub(r"[^a-zA-Z0-9_-]", "_", (s or "")[:64])
    if not out or out[0].isdigit():
        out = "t_" + out
    return out[:48]


def _schema_to_model(schema: Dict[str, Any], model_name: str) -> Type[BaseModel]:
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    if not props:
        class EmptyArgs(BaseModel):
            model_config = ConfigDict(extra="allow")

        return EmptyArgs
    fields: Dict[str, Any] = {}
    for key, prop in props.items():
        if not isinstance(prop, dict):
            continue
        typ = prop.get("type")
        desc = prop.get("description", "")
        py_t: Any = str
        if typ == "integer":
            py_t = int
        elif typ == "number":
            py_t = float
        elif typ == "boolean":
            py_t = bool
        elif typ == "array":
            py_t = list
        elif typ == "object":
            py_t = dict
        from typing import Union

        if key in required:
            fields[key] = (py_t, Field(description=desc or key))
        else:
            fields[key] = (Optional[py_t], Field(default=None, description=desc or key))
    return create_model(model_name, **fields)


def _result_to_text(result: Any) -> str:
    if result is None:
        return ""
    content = getattr(result, "content", None)
    if content is None and isinstance(result, dict):
        content = result.get("content")
    if not content:
        return str(result)
    parts: List[str] = []
    for block in content:
        t = getattr(block, "text", None)
        if t is not None:
            parts.append(str(t))
            continue
        if isinstance(block, dict):
            if block.get("type") == "text" and "text" in block:
                parts.append(str(block["text"]))
    return "\n".join(parts) if parts else str(result)


async def _list_tools_stdio(cfg: Dict[str, Any]) -> List[Any]:
    if not stdio_client or not ClientSession or not StdioServerParameters:
        return []
    cmd = (cfg.get("command") or "").strip()
    if not cmd:
        return []
    args = cfg.get("args") if isinstance(cfg.get("args"), list) else []
    env = {**os.environ, **(cfg.get("env") or {})}
    cwd = cfg.get("cwd") or None
    if cwd and not os.path.isdir(cwd):
        cwd = None
    params = StdioServerParameters(command=cmd, args=args, env=env, cwd=cwd)
    async with stdio_client(params) as streams:
        read, write = streams
        async with ClientSession(read, write) as session:
            await session.initialize()
            lr = await session.list_tools()
            return list(lr.tools or [])


async def _call_stdio_tool(cfg: Dict[str, Any], tool_name: str, arguments: Dict[str, Any]) -> str:
    if not stdio_client or not ClientSession or not StdioServerParameters:
        return "Error: MCP client not available"
    cmd = (cfg.get("command") or "").strip()
    if not cmd:
        return "Error: missing command"
    args = cfg.get("args") if isinstance(cfg.get("args"), list) else []
    env = {**os.environ, **(cfg.get("env") or {})}
    cwd = cfg.get("cwd") or None
    if cwd and not os.path.isdir(cwd):
        cwd = None
    params = StdioServerParameters(command=cmd, args=args, env=env, cwd=cwd)
    async with stdio_client(params) as streams:
        read, write = streams
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments or {})
            return _result_to_text(result)


def _run_async_in_thread(coro):
    out: List[Any] = []
    err: List[BaseException] = []

    def _run():
        try:
            out.append(asyncio.run(coro))
        except BaseException as e:
            err.append(e)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=120)
    if t.is_alive():
        log.warning("external MCP timed out")
        return None
    if err:
        log.warning("external MCP error: %s", err[0])
        return None
    return out[0] if out else None


async def discover_external_servers_async() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for cfg in get_servers_config():
        sid = _sanitize_name(str(cfg.get("id") or cfg.get("name") or "server"))
        if not (cfg.get("command") or "").strip():
            out.append({"id": sid, "error": "missing command"})
            continue
        try:
            mcp_tools = await _list_tools_stdio(cfg)
            names = []
            for mt in mcp_tools or []:
                n = getattr(mt, "name", None)
                if n is None and isinstance(mt, dict):
                    n = mt.get("name")
                if n:
                    names.append(str(n))
            out.append({"id": sid, "tools": names[:MAX_TOOLS_PER_SERVER]})
        except Exception as e:
            out.append({"id": sid, "error": str(e)})
    return out


def discover_external_servers_sync() -> List[Dict[str, Any]]:
    r = _run_async_in_thread(discover_external_servers_async())
    return r if isinstance(r, list) else []


async def _build_tools_async() -> List[Any]:
    if not stdio_client:
        return []
    servers = get_servers_config()
    tools_out: List[Any] = []
    for cfg in servers:
        sid = _sanitize_name(str(cfg.get("id") or cfg.get("name") or "server"))
        if not sid:
            continue
        if not (cfg.get("command") or "").strip():
            continue
        try:
            mcp_tools = await _list_tools_stdio(cfg)
        except Exception as e:
            log.warning("MCP list_tools failed for %s: %s", sid, e)
            continue
        for i, mt in enumerate((mcp_tools or [])[:MAX_TOOLS_PER_SERVER]):
            raw_name = getattr(mt, "name", None)
            if raw_name is None and isinstance(mt, dict):
                raw_name = mt.get("name")
            if not raw_name:
                continue
            desc = getattr(mt, "description", None) or ""
            if isinstance(mt, dict) and not desc:
                desc = mt.get("description") or ""
            schema = getattr(mt, "inputSchema", None)
            if schema is None and isinstance(mt, dict):
                schema = mt.get("inputSchema")
            if not isinstance(schema, dict):
                schema = {}
            lc_name = _sanitize_name(f"ext_{sid}_{raw_name}")
            full_desc = f"[External MCP:{sid}] {desc}".strip()
            model_name = f"Mcp_{sid}_{i}_{_sanitize_name(str(raw_name))}"
            try:
                args_model = _schema_to_model(schema, model_name)
            except Exception as e:
                log.warning("schema skip %s: %s", raw_name, e)
                continue

            cfg_copy = dict(cfg)
            tn = str(raw_name)

            async def _invoke(*, _cfg=cfg_copy, _tn=tn, **kwargs: Any) -> str:
                args = {k: v for k, v in kwargs.items() if v is not None}
                try:
                    return await _call_stdio_tool(_cfg, _tn, args)
                except Exception as ex:
                    return f"Error calling external MCP tool: {ex}"

            st = StructuredTool.from_function(
                coroutine=_invoke,
                name=lc_name,
                description=full_desc,
                args_schema=args_model,
            )
            tools_out.append(st)
    return tools_out


def _cache_key() -> str:
    try:
        return json.dumps(get_servers_config(), sort_keys=True)
    except Exception:
        return ""


def get_external_mcp_tools_sync(mode: str) -> List[Any]:
    global _tools_cache, _tools_cache_key
    if mode != "agent":
        return []
    if not get_servers_config():
        return []
    key = _cache_key()
    if _tools_cache is not None and key == _tools_cache_key:
        return _tools_cache
    built = _run_async_in_thread(_build_tools_async())
    if built is None:
        built = []
    _tools_cache = wrap_tools_with_duplicate_check(built)
    _tools_cache_key = key
    return _tools_cache


def invalidate_external_mcp_cache() -> None:
    global _tools_cache, _tools_cache_key
    _tools_cache = None
    _tools_cache_key = ""
