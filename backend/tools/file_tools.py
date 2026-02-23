import json
from pathlib import Path
from langchain_core.tools import tool
from config import WORKSPACE_ROOT

_UI_MARKER = "\n__UI__\n"


def _resolve(path: str) -> Path:
    p = (WORKSPACE_ROOT / path).resolve()
    if not str(p).startswith(str(WORKSPACE_ROOT.resolve())):
        raise PermissionError("Path outside workspace")
    return p


@tool
def read_file(path: str) -> str:
    """Read the full contents of a file. Give a path relative to workspace root."""
    p = _resolve(path)
    if not p.is_file():
        return f"Error: not a file or not found: {path}"
    return p.read_text(encoding="utf-8", errors="replace")


@tool
def write_file(path: str, content: str) -> str:
    """Create or overwrite a file with the given content. Path relative to workspace."""
    p = _resolve(path)
    old_content = ""
    if p.exists() and p.is_file():
        old_content = p.read_text(encoding="utf-8", errors="replace")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    ui = {"type": "file_edit", "path": path, "old": old_content, "new": content}
    return f"Wrote {path}{_UI_MARKER}{json.dumps(ui)}"


@tool
def edit_file(path: str, old_string: str, new_string: str) -> str:
    """Replace the first occurrence of old_string with new_string in the file. Use exact text for old_string."""
    p = _resolve(path)
    if not p.is_file():
        return f"Error: not a file or not found: {path}"
    text = p.read_text(encoding="utf-8", errors="replace")
    if old_string not in text:
        return f"Error: old_string not found in {path}"
    new_text = text.replace(old_string, new_string, 1)
    p.write_text(new_text, encoding="utf-8")
    ui = {"type": "file_edit", "path": path, "old": text, "new": new_text}
    return f"Edited {path}{_UI_MARKER}{json.dumps(ui)}"


@tool
def delete_file(path: str) -> str:
    """Delete a file. Path relative to workspace. Fails if path is a directory."""
    p = _resolve(path)
    if not p.exists():
        return f"Error: not found: {path}"
    if p.is_dir():
        return f"Error: is a directory, use shell to remove: {path}"
    old_content = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""
    p.unlink()
    ui = {"type": "file_edit", "path": path, "old": old_content, "new": ""}
    return f"Deleted {path}{_UI_MARKER}{json.dumps(ui)}"
