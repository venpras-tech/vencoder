import json
import re
from collections import OrderedDict

from langchain_core.tools import tool
from config import MAX_READ_FILE_SIZE, WORKSPACE_ROOT
from .path_utils import resolve_workspace_path

_UI_MARKER = "\n__UI__\n"
_READ_CACHE: OrderedDict = OrderedDict()
_READ_CACHE_MAX = 128


def _invalidate_read_cache(path: str) -> None:
    keys = [k for k in _READ_CACHE if k.startswith(path + ":")]
    for k in keys:
        _READ_CACHE.pop(k, None)


@tool
def read_file(path: str) -> str:
    """Read the full contents of a file. Give a path relative to workspace root."""
    p = resolve_workspace_path(path)
    if not p.is_file():
        return f"Error: not a file or not found: {path}"
    size = p.stat().st_size
    if size > MAX_READ_FILE_SIZE:
        return f"Error: file too large ({size} bytes, max {MAX_READ_FILE_SIZE})"
    try:
        mtime = p.stat().st_mtime
        key = f"{path}:{mtime}"
        if key in _READ_CACHE:
            _READ_CACHE.move_to_end(key)
            return _READ_CACHE[key]
    except OSError:
        pass
    content = p.read_text(encoding="utf-8", errors="replace")
    try:
        key = f"{path}:{p.stat().st_mtime}"
        if len(_READ_CACHE) >= _READ_CACHE_MAX:
            _READ_CACHE.popitem(last=False)
        _READ_CACHE[key] = content
    except OSError:
        pass
    return content


@tool
def write_file(path: str, content: str) -> str:
    """Create or overwrite a file with the given content. Path relative to workspace."""
    p = resolve_workspace_path(path)
    old_content = ""
    if p.exists() and p.is_file():
        old_content = p.read_text(encoding="utf-8", errors="replace")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    _invalidate_read_cache(path)
    ui = {"type": "file_edit", "path": path, "old": old_content, "new": content}
    return f"Wrote {path}{_UI_MARKER}{json.dumps(ui)}"


@tool
def edit_file(path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """Replace old_string with new_string in the file. Use exact text for old_string. replace_all: replace all occurrences (default: first only)."""
    p = resolve_workspace_path(path)
    if not p.is_file():
        return f"Error: not a file or not found: {path}"
    text = p.read_text(encoding="utf-8", errors="replace")
    if old_string not in text:
        return f"Error: old_string not found in {path}"
    count = text.count(old_string)
    new_text = text.replace(old_string, new_string) if replace_all else text.replace(old_string, new_string, 1)
    p.write_text(new_text, encoding="utf-8")
    _invalidate_read_cache(path)
    ui = {"type": "file_edit", "path": path, "old": text, "new": new_text}
    return f"Edited {path} ({count} occurrence(s) replaced){_UI_MARKER}{json.dumps(ui)}"


@tool
def delete_file(path: str) -> str:
    """Delete a file. Path relative to workspace. Fails if path is a directory."""
    p = resolve_workspace_path(path)
    if not p.exists():
        return f"Error: not found: {path}"
    if p.is_dir():
        return f"Error: is a directory, use shell to remove: {path}"
    old_content = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""
    p.unlink()
    _invalidate_read_cache(path)
    ui = {"type": "file_edit", "path": path, "old": old_content, "new": ""}
    return f"Deleted {path}{_UI_MARKER}{json.dumps(ui)}"


@tool
def save_plan(content: str, title: str = "plan") -> str:
    """Save a Markdown plan to .codec-agent/plans/ in the workspace. Use after creating a plan. title: short slug for the filename (e.g. 'add-login-form')."""
    slug = re.sub(r"[^\w\-]", "-", (title or "plan").lower()).strip("-") or "plan"
    path = f".codec-agent/plans/{slug}.md"
    p = resolve_workspace_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    old_content = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    p.write_text(content, encoding="utf-8")
    ui = {"type": "file_edit", "path": path, "old": old_content, "new": content}
    return f"Saved plan to {path}{_UI_MARKER}{json.dumps(ui)}"
