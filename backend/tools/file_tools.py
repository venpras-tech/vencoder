import json
from langchain_core.tools import tool
from config import MAX_READ_FILE_SIZE, WORKSPACE_ROOT
from .path_utils import resolve_workspace_path

_UI_MARKER = "\n__UI__\n"


@tool
def read_file(path: str) -> str:
    """Read the full contents of a file. Give a path relative to workspace root."""
    p = resolve_workspace_path(path)
    if not p.is_file():
        return f"Error: not a file or not found: {path}"
    size = p.stat().st_size
    if size > MAX_READ_FILE_SIZE:
        return f"Error: file too large ({size} bytes, max {MAX_READ_FILE_SIZE})"
    return p.read_text(encoding="utf-8", errors="replace")


@tool
def write_file(path: str, content: str) -> str:
    """Create or overwrite a file with the given content. Path relative to workspace."""
    p = resolve_workspace_path(path)
    old_content = ""
    if p.exists() and p.is_file():
        old_content = p.read_text(encoding="utf-8", errors="replace")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
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
    ui = {"type": "file_edit", "path": path, "old": old_content, "new": ""}
    return f"Deleted {path}{_UI_MARKER}{json.dumps(ui)}"
