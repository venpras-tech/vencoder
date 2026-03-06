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


def _tree_to_text(items: list[dict[str, Any]], prefix: str = "", depth: int = 0, max_depth: int = 3, max_children: int = 15) -> list[str]:
    lines = []
    for i, item in enumerate(items[:max_children]):
        is_last = i == min(len(items), max_children) - 1
        connector = "└── " if is_last else "├── "
        name = item["name"]
        if item.get("type") == "folder":
            lines.append(prefix + connector + name + "/")
            if depth < max_depth:
                sub_prefix = prefix + ("    " if is_last else "│   ")
                children = item.get("children", [])
                if children:
                    lines.extend(_tree_to_text(children, sub_prefix, depth + 1, max_depth, max_children))
        else:
            lines.append(prefix + connector + name)
    return lines


def get_file_structure_summary() -> str:
    tree = get_file_tree()
    if not tree:
        return "[Workspace structure: empty or inaccessible]"
    lines = _tree_to_text(tree)
    return "[Workspace structure]\n\n```\n.\n" + "\n".join(lines) + "\n```"


_PROJECT_INDICATORS = (
    ("package.json", "Node.js/JavaScript"),
    ("package-lock.json", "Node.js/JavaScript"),
    ("yarn.lock", "Node.js/JavaScript"),
    ("pnpm-lock.yaml", "Node.js/JavaScript"),
    ("requirements.txt", "Python"),
    ("pyproject.toml", "Python"),
    ("setup.py", "Python"),
    ("Pipfile", "Python"),
    ("Cargo.toml", "Rust"),
    ("go.mod", "Go"),
    ("pom.xml", "Java (Maven)"),
    ("build.gradle", "Java (Gradle)"),
    ("build.gradle.kts", "Java (Gradle Kotlin)"),
    ("settings.gradle", "Java (Gradle)"),
    ("app/build.gradle", "Android"),
    ("app/build.gradle.kts", "Android"),
    ("android/build.gradle", "Android (Flutter)"),
    ("*.csproj", "C#/.NET"),
    ("*.sln", "C#/.NET"),
    ("Gemfile", "Ruby"),
    ("composer.json", "PHP"),
    ("Makefile", "C/C++/Make"),
    ("CMakeLists.txt", "C/C++/CMake"),
    ("mix.exs", "Elixir"),
    ("project.clj", "Clojure"),
    ("dub.json", "D"),
    ("shard.yml", "Crystal"),
    ("pubspec.yaml", "Dart/Flutter"),
    ("BUILD", "Bazel"),
    ("BUILD.bazel", "Bazel"),
)


def _detect_project_types(root: Path) -> list[str]:
    seen = set()
    out = []
    for name, label in _PROJECT_INDICATORS:
        if label in seen:
            continue
        path = root / name
        if name.startswith("*"):
            try:
                for p in root.glob(name):
                    if p.is_file():
                        out.append(f"{label} ({p.name})")
                        seen.add(label)
                        break
            except OSError:
                pass
        elif path.is_file():
            out.append(f"{label} ({name})")
            seen.add(label)
    return out


def get_project_context() -> str:
    root = WORKSPACE_ROOT.resolve()
    if not root.exists() or not root.is_dir():
        return "[Project context: workspace not found]"
    parts = []
    detected = _detect_project_types(root)
    if detected:
        parts.append("[Project type]\n" + "\n".join(detected))
    parts.append(get_file_structure_summary())
    return "\n\n".join(parts)


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
