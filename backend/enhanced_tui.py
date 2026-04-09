import asyncio
import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime

_tui_available = False
_console = None
_prompt_session = None
_use_plain_input = False


def _try_import():
    global _tui_available, _console, _use_plain_input
    if _tui_available is not False:
        return _tui_available
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.rule import Rule
        from rich.theme import Theme
        _console = Console(theme=Theme({
            "user": "bold cyan",
            "assistant": "bold green",
            "tool": "dim yellow",
            "error": "bold red",
            "info": "dim blue",
            "warning": "bold yellow",
            "success": "bold green",
            "diff_add": "bold green",
            "diff_remove": "bold red",
        }))
        _tui_available = True
        return True
    except ImportError:
        _tui_available = False
        return False


def _get_prompt_session():
    global _prompt_session, _use_plain_input
    if _use_plain_input:
        return None
    if _prompt_session is None and _try_import():
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.history import FileHistory
            _history_path = Path.home() / ".ai-dev" / "history"
            _history_path.parent.mkdir(parents=True, exist_ok=True)
            _prompt_session = PromptSession(
                history=FileHistory(str(_history_path)),
                multiline=True,
            )
        except Exception:
            _use_plain_input = True
    return _prompt_session


def is_available():
    return _try_import()


class DiffType(Enum):
    ADDED = "+"
    REMOVED = "-"
    UNCHANGED = " "


@dataclass
class DiffLine:
    type: DiffType
    content: str
    line_num_old: Optional[int] = None
    line_num_new: Optional[int] = None


@dataclass
class DiffResult:
    old_path: str
    new_path: str
    lines: List[DiffLine] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)


class ProgressTracker:
    def __init__(self, total: int = 100, description: str = "Processing"):
        self.total = total
        self.current = 0
        self.description = description
        self.tasks: Dict[str, "ProgressTask"] = {}
        self._enabled = _try_import()

    def add_task(self, task_id: str, description: str, total: int = 100) -> "ProgressTask":
        task = ProgressTask(task_id, description, total, self)
        self.tasks[task_id] = task
        return task

    def update(self, task_id: str, advance: int = 1, description: str = None):
        if task_id in self.tasks:
            self.tasks[task_id].advance(advance, description)

    def complete(self, task_id: str):
        if task_id in self.tasks:
            self.tasks[task_id].complete()


class ProgressTask:
    def __init__(self, task_id: str, description: str, total: int, tracker: ProgressTracker):
        self.task_id = task_id
        self.description = description
        self.total = total
        self.current = 0
        self.tracker = tracker
        self.completed = False
        self._start_time = datetime.now()

    def advance(self, n: int = 1, description: str = None):
        if self.completed:
            return
        self.current = min(self.current + n, self.total)
        if description:
            self.description = description
        self._render()

    def complete(self):
        if self.completed:
            return
        self.completed = True
        self.current = self.total
        self._render_complete()

    def _render(self):
        if not self._enabled:
            return
        pct = int(100 * self.current / max(self.total, 1))
        bar_len = 30
        filled = int(bar_len * self.current / max(self.total, 1))
        bar = "█" * filled + "░" * (bar_len - filled)
        elapsed = (datetime.now() - self._start_time).total_seconds()
        rate = self.current / max(elapsed, 0.1)
        remaining = (self.total - self.current) / max(rate, 0.1)
        _console.print(
            f"[cyan]{self.description}[/cyan] [{bar}] {pct}% "
            f"[dim]({rate:.1f}/s, {remaining:.0f}s remaining)[/dim]",
            end="\r"
        )

    def _render_complete(self):
        if not self._enabled:
            return
        _console.print(f"[green]✓[/green] {self.description} [dim](completed)[/dim]")


class ErrorCategory(Enum):
    SYNTAX = "syntax"
    TYPE = "type"
    RUNTIME = "runtime"
    LOGIC = "logic"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    DEPRECATION = "deprecation"
    UNKNOWN = "unknown"


@dataclass
class FormattedError:
    category: ErrorCategory
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    column: Optional[int] = None
    suggestion: Optional[str] = None
    severity: str = "error"
    context: List[str] = field(default_factory=list)


def compute_diff(old_content: str, new_content: str, old_path: str = "", new_path: str = "") -> DiffResult:
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    
    from difflib import SequenceMatcher
    matcher = SequenceMatcher(None, old_lines, new_lines)
    
    result = DiffResult(old_path=old_path, new_path=new_path)
    old_line_num = 1
    new_line_num = 1
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for line in old_lines[i1:i2]:
                result.lines.append(DiffLine(
                    type=DiffType.UNCHANGED,
                    content=line.rstrip('\n\r'),
                    line_num_old=old_line_num,
                    line_num_new=new_line_num
                ))
                old_line_num += 1
                new_line_num += 1
        elif tag == "replace":
            for line in old_lines[i1:i2]:
                result.lines.append(DiffLine(
                    type=DiffType.REMOVED,
                    content=line.rstrip('\n\r'),
                    line_num_old=old_line_num
                ))
                old_line_num += 1
            for line in new_lines[j1:j2]:
                result.lines.append(DiffLine(
                    type=DiffType.ADDED,
                    content=line.rstrip('\n\r'),
                    line_num_new=new_line_num
                ))
                new_line_num += 1
        elif tag == "delete":
            for line in old_lines[i1:i2]:
                result.lines.append(DiffLine(
                    type=DiffType.REMOVED,
                    content=line.rstrip('\n\r'),
                    line_num_old=old_line_num
                ))
                old_line_num += 1
        elif tag == "insert":
            for line in new_lines[j1:j2]:
                result.lines.append(DiffLine(
                    type=DiffType.ADDED,
                    content=line.rstrip('\n\r'),
                    line_num_new=new_line_num
                ))
                new_line_num += 1
    
    result.stats = {
        "additions": sum(1 for l in result.lines if l.type == DiffType.ADDED),
        "deletions": sum(1 for l in result.lines if l.type == DiffType.REMOVED),
        "unchanged": sum(1 for l in result.lines if l.type == DiffType.UNCHANGED),
    }
    
    return result


def print_diff(diff: DiffResult, context_lines: int = 3):
    if not _try_import():
        for line in diff.lines:
            prefix = line.type.value
            content = line.content
            if line.type == DiffType.ADDED:
                print(f"+ {content}")
            elif line.type == DiffType.REMOVED:
                print(f"- {content}")
            else:
                print(f"  {content}")
        return
    
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    
    additions = diff.stats.get("additions", 0)
    deletions = diff.stats.get("deletions", 0)
    
    stats_text = f"[green]+{additions}[/green] [red]-{deletions}[/red]"
    if diff.old_path or diff.new_path:
        path_text = f"[dim]{diff.old_path or ''}[/dim] → [dim]{diff.new_path or ''}[/dim]"
        _console.print(Panel(stats_text + "  " + path_text, border_style="blue"))
    else:
        _console.print(f"[dim]Diff:[/dim] {stats_text}")
    
    console = Console()
    for line in diff.lines:
        prefix = f"[{'green' if line.type == DiffType.ADDED else 'red' if line.type == DiffType.REMOVED else 'dim'}]{line.type.value}[/]"
        old_num = f"[dim]{line.line_num_old or '':>4}[/dim]" if line.line_num_old else "    "
        new_num = f"[dim]{line.line_num_new or '':>4}[/dim]" if line.line_num_new else "    "
        
        style = "green" if line.type == DiffType.ADDED else "red" if line.type == DiffType.REMOVED else ""
        console.print(f"{old_num} {new_num} {prefix} {style}{line.content}[/{style}]" if style else f"{old_num} {new_num} {prefix} {line.content}")


def print_diff_inline(old_content: str, new_content: str, max_lines: int = 20):
    diff = compute_diff(old_content, new_content)
    
    if len(diff.lines) > max_lines * 2:
        visible_lines = max_lines
        hidden_count = len(diff.lines) - (visible_lines * 2)
        
        if _try_import():
            print_diff(DiffResult(
                old_path=diff.old_path,
                new_path=diff.new_path,
                lines=diff.lines[:visible_lines],
                stats={"additions": 0, "deletions": 0, "unchanged": 0}
            ))
            from rich.console import Console
            Console().print(f"[dim]... {hidden_count} lines hidden ...[/dim]")
            print_diff(DiffResult(
                old_path="",
                new_path="",
                lines=diff.lines[-visible_lines:],
                stats={"additions": 0, "deletions": 0, "unchanged": 0}
            ))
        else:
            print_diff(diff)
    else:
        print_diff(diff)


def print_formatted_error(error: FormattedError):
    if not _try_import():
        parts = [f"{error.severity.upper()}: {error.message}"]
        if error.file_path:
            parts.append(f"  at {error.file_path}" + (f":{error.line_number}" if error.line_number else ""))
        if error.suggestion:
            parts.append(f"  Suggestion: {error.suggestion}")
        print("\n".join(parts))
        return
    
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    
    category_colors = {
        ErrorCategory.SYNTAX: "red",
        ErrorCategory.TYPE: "yellow",
        ErrorCategory.RUNTIME: "red",
        ErrorCategory.LOGIC: "yellow",
        ErrorCategory.SECURITY: "red",
        ErrorCategory.PERFORMANCE: "yellow",
        ErrorCategory.STYLE: "blue",
        ErrorCategory.DEPRECATION: "magenta",
        ErrorCategory.UNKNOWN: "white",
    }
    
    color = category_colors.get(error.category, "white")
    location = ""
    if error.file_path:
        location = f"{error.file_path}"
        if error.line_number:
            location += f":{error.line_number}"
            if error.column:
                location += f":{error.column}"
    
    severity_prefix = "❌" if error.severity == "error" else "⚠️" if error.severity == "warning" else "ℹ️"
    
    content_parts = []
    if location:
        content_parts.append(f"[{color}]{error.category.value.upper()}[/{color}] [dim]{location}[/dim]")
    else:
        content_parts.append(f"[{color}]{error.category.value.upper()}[/{color}]")
    
    content_parts.append(error.message)
    
    if error.context:
        for ctx in error.context[-3:]:
            content_parts.append(f"[dim]  {ctx}[/dim]")
    
    if error.suggestion:
        content_parts.append(f"[green]💡 Suggestion:[/green] {error.suggestion}")
    
    console = Console()
    console.print(Panel("\n".join(content_parts), border_style=color, title=f"{severity_prefix} {error.category.value}"))


def parse_error_output(output: str, file_path: str = None) -> List[FormattedError]:
    errors = []
    
    import re
    
    patterns = [
        (r'error\[([\w-]+)\]: (.+)', ErrorCategory.TYPE),
        (r'Error: (.+)', ErrorCategory.RUNTIME),
        (r'SyntaxError: (.+)', ErrorCategory.SYNTAX),
        (r'IndentationError: (.+)', ErrorCategory.SYNTAX),
        (r'TypeError: (.+)', ErrorCategory.TYPE),
        (r'AttributeError: (.+)', ErrorCategory.RUNTIME),
        (r'NameError: (.+)', ErrorCategory.RUNTIME),
        (r'File "([^"]+)", line (\d+)', ErrorCategory.UNKNOWN),
        (r'warning: (.+)', ErrorCategory.STYLE),
    ]
    
    for line in output.splitlines():
        for pattern, category in patterns:
            match = re.search(pattern, line)
            if match:
                error = FormattedError(
                    category=category,
                    message=match.group(2) if len(match.groups()) > 1 else match.group(1),
                    file_path=file_path,
                )
                
                if file_path is None and "File" in line:
                    file_match = re.search(r'File "([^"]+)", line (\d+)', line)
                    if file_match:
                        error.file_path = file_match.group(1)
                        error.line_number = int(file_match.group(2))
                
                errors.append(error)
                break
    
    return errors


def print_progress_bar(current: int, total: int, description: str = "", width: int = 40):
    if not _try_import():
        pct = int(100 * current / max(total, 1))
        bar = "=" * int(width * current / max(total, 1)) + "-" * (width - int(width * current / max(total, 1)))
        print(f"\r[{bar}] {pct}% {description}", end="", flush=True)
        if current >= total:
            print()
        return
    
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
    
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
    )


def print_table(headers: List[str], rows: List[List[str]], title: str = None):
    if not _try_import():
        col_widths = [max(len(h), max(len(str(r[i])) for r in rows)) if rows else len(h) for i, h in enumerate(headers)]
        separator = " | ".join("=" * w for w in col_widths)
        header_line = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
        print(separator)
        print(header_line)
        print(separator)
        for row in rows:
            print(" | ".join(str(row[i]).ljust(col_widths[i]) for i in range(len(row))))
        print(separator)
        return
    
    from rich.table import Table as RichTable
    table = RichTable(title=title)
    for h in headers:
        table.add_column(h, style="cyan")
    for row in rows:
        table.add_row(*[str(c) for c in row])
    _console.print(table)


def print_tree(data: Dict[str, Any], indent: int = 0, prefix: str = ""):
    if not _try_import():
        for key, value in data.items():
            if isinstance(value, dict):
                print(f"{prefix}{key}/")
                print_tree(value, indent + 2, prefix + "  ")
            else:
                print(f"{prefix}{key}: {value}")
        return
    
    from rich.tree import Tree as RichTree
    from rich.console import Console
    
    def build_tree(d: Dict[str, Any], tree: RichTree) -> None:
        for key, value in d.items():
            if isinstance(value, dict):
                branch = tree.add(f"[cyan]{key}/[/cyan]")
                build_tree(value, branch)
            else:
                tree.add(f"[yellow]{key}[/yellow]: [white]{value}[/white]")
    
    root = RichTree("[bold]Files[/bold]")
    build_tree(data, root)
    Console().print(root)


def print_json(data: Any, indent: int = 2):
    if not _try_import():
        print(json.dumps(data, indent=indent))
        return
    
    from rich.json import JSON
    _console.print(JSON.from_data(data))


def print_collapsible(title: str, content: str, expanded: bool = False):
    if not _try_import():
        print(f"{title}:")
        print(content)
        return
    
    from rich.panel import Panel
    _console.print(Panel(content, title=title, border_style="blue", expand=expanded))


def print_loading_dots(message: str = "Loading"):
    if not _try_import():
        print(f"{message}...", end="", flush=True)
        return
    
    from rich.console import Console
    from rich.live import Live
    import itertools
    
    console = Console()
    for i in itertools.count():
        dots = "." * (i % 4)
        console.print(f"\r[dim]{message}{dots}[/dim]", end="")
        yield
        if i > 100:
            break


def print_spinner(task: str):
    if not _try_import():
        print(f"{task}...", end="", flush=True)
        yield
        print(" Done")
        return
    
    from rich.console import Console
    from rich.spinner import Spinner as RichSpinner
    
    console = Console()
    with console.status(f"[bold cyan]{task}[/bold cyan]") as status:
        yield


def print_banner(text: str, style: str = "cyan"):
    if not _try_import():
        print(f"=== {text} ===")
        return
    
    from rich.panel import Panel
    _console.print(Panel(f"[bold {style}]{text}[/bold {style}]", border_style=style))


def print_success(message: str):
    if not _try_import():
        print(f"✓ {message}")
        return
    _console.print(f"[green]✓[/green] {message}")


def print_warning(message: str):
    if not _try_import():
        print(f"⚠ {message}", file=sys.stderr)
        return
    _console.print(f"[yellow]⚠[/yellow] {message}")


def print_info(message: str):
    if not _try_import():
        print(f"ℹ {message}")
        return
    _console.print(f"[blue]ℹ[/blue] {message}")


def print_user(msg: str):
    if _try_import():
        from rich.panel import Panel
        _console.print(Panel(msg, title="[user] You", border_style="cyan"))
    else:
        print(f"You: {msg}")


def print_assistant(msg: str, *, use_markdown: bool = True):
    if _try_import():
        if use_markdown and msg.strip():
            try:
                from rich.markdown import Markdown
                _console.print(Markdown(msg))
            except Exception:
                _console.print(msg)
        else:
            _console.print(msg)
    else:
        print(msg)


def print_assistant_stream_start():
    if _try_import():
        _console.print()


def print_assistant_stream_chunk(chunk: str):
    if _try_import():
        _console.print(chunk, end="")
    else:
        print(chunk, end="", flush=True)


def print_assistant_stream_end():
    if _try_import():
        _console.print()
    else:
        print()


def print_status(msg: str):
    if _try_import():
        _console.print(f"[dim]> {msg}[/dim]")
    else:
        print(f"→ {msg}")


def print_tool(name: str):
    if _try_import():
        _console.print(f"[tool]  {name}[/tool]")
    else:
        print(f"  {name}")


def print_error(msg: str):
    if _try_import():
        _console.print(f"[error]Error: {msg}[/error]")
    else:
        print(f"Error: {msg}", file=sys.stderr)


def print_rule():
    if _try_import():
        from rich.rule import Rule
        _console.print(Rule(style="dim"))
    else:
        print("-" * 40)


def print_welcome(mode: str):
    if _try_import():
        from rich.panel import Panel
        _console.print(Panel(
            "[bold]VenCoder[/bold] - AI coding agent\n\n"
            "[dim]Commands: /quit /continue /session /help[/dim]\n"
            "[dim]Mode: %s[/dim]" % mode,
            border_style="green",
        ))
        _console.print()
    else:
        print("VenCoder - type your message and press Enter. Ctrl+C to exit, /quit to exit.")
        print()


def prompt_input() -> str:
    session = _get_prompt_session()
    if session:
        try:
            return session.prompt("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            raise
        except Exception:
            return input("You: ").strip()
    try:
        return input("You: ").strip()
    except (EOFError, KeyboardInterrupt):
        raise


def print_session_list(items: list):
    if _try_import():
        from rich.table import Table
        table = Table(title="Sessions")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="green")
        table.add_column("Created", style="dim")
        for i in items:
            table.add_row(str(i["id"]), i["title"], i.get("created_at", "")[:19])
        _console.print(table)
    else:
        for i in items:
            print(f"  {i['id']}: {i['title']}")


def print_session_details(session: dict):
    if not _try_import():
        print(f"Session {session['id']}: {session['title']}")
        print(f"Created: {session.get('created_at', 'N/A')}")
        print(f"Messages: {session.get('message_count', 0)}")
        return
    
    from rich.panel import Panel
    from rich.table import Table
    
    table = Table(title=f"Session #{session['id']}", show_header=False)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("Title", session.get("title", "Untitled"))
    table.add_row("Created", session.get("created_at", "N/A")[:19] if session.get("created_at") else "N/A")
    table.add_row("Messages", str(session.get("message_count", 0)))
    
    if session.get("last_message_at"):
        table.add_row("Last Activity", session["last_message_at"][:19])
    
    if session.get("mode"):
        table.add_row("Mode", session["mode"])
    
    if session.get("model"):
        table.add_row("Model", session["model"])
    
    _console.print(table)


def print_tool_result(tool_name: str, result: str, success: bool = True):
    if not _try_import():
        status = "✓" if success else "✗"
        print(f"{status} {tool_name}: {result[:100]}{'...' if len(result) > 100 else ''}")
        return
    
    status_icon = "[green]✓[/green]" if success else "[red]✗[/red]"
    _console.print(f"{status_icon} [yellow]{tool_name}[/yellow]")
    
    if len(result) > 500:
        from rich.panel import Panel
        _console.print(Panel(result[:500] + "...", border_style="green" if success else "red"))
    else:
        _console.print(f"  [dim]{result}[/dim]")
