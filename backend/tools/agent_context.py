import hashlib
import json
from contextvars import ContextVar
from typing import Any, Callable

_agent_run_calls: ContextVar[list] = ContextVar("agent_run_calls", default=[])

READ_ONLY_TOOLS = frozenset({
    "read_file", "list_directory", "grep_search", "glob_search",
    "web_search", "search_context", "git_status", "git_diff",
})


def init_agent_run():
    _agent_run_calls.set([])


def check_duplicate_tool_call(tool_name: str, args: dict[str, Any]) -> bool:
    if tool_name in READ_ONLY_TOOLS:
        return False
    calls = _agent_run_calls.get([])
    key = (tool_name, hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest())
    recent = [(n, h) for n, h in calls[-5:]]
    if key in [(n, h) for n, h in recent]:
        return True
    calls.append(key)
    return False
