import json
import sys
from pathlib import Path

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
            _history_path = Path.home() / ".codec-agent" / "history"
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
            "[bold]AI Codec[/bold] - coding agent with Ollama\n\n"
            "[dim]Commands: /quit /continue /session /help[/dim]\n"
            "[dim]Mode: %s[/dim]" % mode,
            border_style="green",
        ))
        _console.print()
    else:
        print("AI Codec - type your message and press Enter. Ctrl+C to exit, /quit to exit.")
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
