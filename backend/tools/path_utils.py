from pathlib import Path
from config import WORKSPACE_ROOT


def resolve_workspace_path(path: str) -> Path:
    root = WORKSPACE_ROOT.resolve()
    p = (root / path).resolve()
    try:
        p.relative_to(root)
    except ValueError:
        raise PermissionError("Path outside workspace")
    return p
