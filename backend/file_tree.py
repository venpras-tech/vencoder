import re
from pathlib import Path
from typing import Any

from config import MAX_READ_FILE_SIZE, WORKSPACE_ROOT

_TREE_IGNORE = re.compile(
    r"(^|/)(\.git|node_modules|__pycache__|\.venv|venv|\.env|dist|build|chroma_data|\.codec-agent)(/|$)",
    re.I,
)


def _should_show(rel: str) -> bool:
    return not _TREE_IGNORE.search(rel.replace("\\", "/"))


def _build_tree(p: Path, rel_prefix: str) -> list[dict[str, Any]]:
    items = []
    try:
        entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
    except PermissionError:
        return items
    for e in entries:
        rel = f"{rel_prefix}/{e.name}" if rel_prefix else e.name
        if not _should_show(rel):
            continue
        if e.is_dir():
            children = _build_tree(e, rel)
            items.append({"name": e.name, "path": rel, "type": "folder", "children": children})
        elif e.is_file():
            items.append({"name": e.name, "path": rel, "type": "file"})
    return items


def get_file_tree() -> list[dict[str, Any]]:
    root = WORKSPACE_ROOT.resolve()
    if not root.exists() or not root.is_dir():
        return []
    return _build_tree(root, "")


def read_file_content(rel_path: str) -> tuple[str, str | None]:
    root = WORKSPACE_ROOT.resolve()
    p = (root / rel_path).resolve()
    try:
        p.relative_to(root)
    except ValueError:
        raise PermissionError("Path outside workspace")
    if not p.exists():
        raise FileNotFoundError(f"Not found: {rel_path}")
    if p.is_dir():
        raise ValueError(f"Is a directory: {rel_path}")
    size = p.stat().st_size
    if size > MAX_READ_FILE_SIZE:
        raise ValueError(f"File too large ({size} bytes)")
    text = p.read_text(encoding="utf-8", errors="replace")
    return text, p.suffix.lower()
