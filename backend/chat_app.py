import asyncio
import json
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.events import Key
from textual.widgets import Button, Footer, Header, Input, RichLog, Static, Tree
from textual.widgets.tree import TreeNode
from rich.console import Console
from rich.markup import MarkupError
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from config import WORKSPACE_ROOT


class FileTree(Tree):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._root_path = Path(WORKSPACE_ROOT) if WORKSPACE_ROOT else Path(".")

    def on_mount(self) -> None:
        self.root.label = self._root_path.name or "."
        self._build_tree(self.root, self._root_path)
        self.root.expand()

    def _build_tree(self, parent: TreeNode, path: Path) -> None:
        try:
            for item in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                if item.name.startswith(".") or item.name in ("node_modules", "__pycache__", ".git"):
                    continue
                label = "📁 " + item.name if item.is_dir() else "📄 " + item.name
                node = parent.add(label, data=str(item))
                if item.is_dir():
                    self._build_tree(node, item)
        except PermissionError:
            pass


class StatusBar(Static):
    def __init__(self, model: str = "", mode: str = "agent", session: int | None = None, **kwargs):
        super().__init__("", **kwargs)
        self._model = model or "?"
        self._mode = mode or "agent"
        self._session = session

    def update_status(self, model: str = None, mode: str = None, session: int = None):
        if model is not None:
            self._model = model
        if mode is not None:
            self._mode = mode
        if session is not None:
            self._session = session
        cwd = Path(WORKSPACE_ROOT).name if WORKSPACE_ROOT else "."
        parts = [f"[cyan]{self._model}[/]", f"[green]{self._mode}[/]"]
        if self._session:
            parts.append(f"[dim]#{self._session}[/]")
        parts.append(f"[dim]{cwd}[/]")
        self.update(" | ".join(parts))


class ChatMessage(Static):
    def __init__(self, role: str, content: str, **kwargs):
        super().__init__("", **kwargs)
        self._role = role
        self._content = content

    def compose(self) -> ComposeResult:
        border = "cyan" if self._role == "user" else "green"
        icon = "👤" if self._role == "user" else "🤖"
        title = f"[{border}]{icon} {self._role.title()}[/{border}]"
        
        try:
            content = Text.from_markup(self._content)
        except MarkupError:
            content = self._content
        
        with Vertical(id=f"msg-{self._role}"):
            yield Static(content, markup=True)


class ToolPanel(Static):
    def __init__(self, **kwargs):
        super().__init__("", **kwargs)
        self._tools: list[tuple[str, str]] = []

    def add_tool(self, name: str, status: str = "running") -> None:
        self._tools.append((name, status))
        self._render_tools()

    def update_tool(self, name: str, status: str) -> None:
        for i, (n, _) in enumerate(self._tools):
            if n == name:
                self._tools[i] = (name, status)
                break
        self._render_tools()

    def _render_tools(self) -> None:
        if not self._tools:
            self.update("[dim]No active tools[/dim]")
            return
        lines = []
        for name, status in self._tools:
            icon = "⚡" if status == "running" else "✓" if status == "done" else "✗"
            color = "yellow" if status == "running" else "green" if status == "done" else "red"
            lines.append(f"[{color}]{icon} {name}[/{color}]")
        self.update("\n".join(lines))


class CommandPalette(Static):
    def __init__(self, **kwargs):
        super().__init__("", **kwargs)
        self._visible = False
        self._commands = [
            ("/help", "Show help"),
            ("/quit", "Exit"),
            ("/new", "New session"),
            ("/continue", "Continue session"),
            ("/session", "List sessions"),
            ("/models", "Show models"),
            ("/files", "Toggle file tree"),
        ]

    def toggle(self) -> None:
        self._visible = not self._visible

    def compose(self) -> ComposeResult:
        if self._visible:
            table = Table(box=None, show_header=False, pad_edge=False)
            for cmd, desc in self._commands:
                table.add_row(f"[cyan]{cmd}[/]", f"[dim]{desc}[/]")
            yield Static(table, id="palette-content")


class ChatApp(App):
    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 1;
        grid-columns: 1fr 3fr;
        grid-rows: 1fr 3 1;
    }
    #sidebar {
        width: 20;
        height: 100%;
        background: $surface;
        border-right: solid $primary;
    }
    #main {
        layout: vertical;
    }
    #chat-container {
        height: 1fr;
    }
    #messages {
        height: 1fr;
        padding: 1;
    }
    #input-area {
        height: auto;
        border-top: solid $primary;
        padding: 1;
    }
    #input {
        width: 100%;
    }
    #status-bar {
        height: 1;
        padding: 0 1;
        background: $surface;
    }
    #tools {
        width: 100%;
        height: auto;
        padding: 0 1;
        background: $surface;
    }
    #file-tree {
        height: 100%;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit"),
        Binding("f1", "help", "Help"),
        Binding("n", "new_session", "New"),
        Binding("m", "models", "Models"),
        Binding("f", "toggle_files", "Files"),
        Binding("ctrl+k", "command_palette", "Cmd"),
    ]

    def __init__(self, mode: str = "agent", conv_id: int | None = None, model_override: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._mode = mode
        self._conv_id = conv_id
        self._model_override = model_override
        self._current_model = ""
        self._streaming = False
        self._files_visible = True

    def compose(self) -> ComposeResult:
        with Horizontal(id="sidebar"):
            with Vertical(id="file-tree"):
                yield FileTree("Files", id="file-tree")
        
        with Vertical(id="main"):
            with ScrollableContainer(id="chat-container"):
                yield RichLog(markup=True, highlight=True, id="messages")
            
            with Horizontal(id="tools"):
                yield ToolPanel(id="tools")
            
            with Container(id="input-area"):
                yield Input(placeholder="Message... (Ctrl+K for commands)", id="input")
            
            yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        self.query_one("#input", Input).focus()
        try:
            import server as srv
            self._current_model = srv.current_model
        except Exception:
            self._current_model = "?"
        
        self.query_one("#status-bar", StatusBar).update_status(
            model=self._current_model, mode=self._mode, session=self._conv_id
        )
        
        self._add_welcome()

    def _add_welcome(self) -> None:
        log = self.query_one("#messages", RichLog)
        welcome = """
[bold green]AI Dev[/bold green] - AI Coding Assistant

[dim]Features:[/dim]
• Edit files with AI assistance
• Semantic code search
• Git integration
• Multi-model support (Ollama)

[dim]Commands:[/dim]
• [cyan]/help[/cyan] - Show all commands
• [cyan]/new[/cyan] - Start new session
• [cyan]/continue[/cyan] - Continue last session
• [cyan]/files[/cyan] - Toggle file tree
• [cyan]/models[/cyan] - List available models
• [cyan]/quit[/cyan] - Exit
        """
        log.write(Panel(welcome.strip(), title="Welcome", border_style="green", width=80))

    def action_quit(self) -> None:
        self.exit()

    def action_help(self) -> None:
        self._show_help()

    def action_new_session(self) -> None:
        self._conv_id = None
        self.query_one("#status-bar", StatusBar).update_status(session=None)
        self._add_status("New session started")

    def action_models(self) -> None:
        self._show_models()

    def action_toggle_files(self) -> None:
        self._files_visible = not self._files_visible
        sidebar = self.query_one("#sidebar")
        sidebar.display = self._files_visible
        self._add_status("File tree " + ("shown" if self._files_visible else "hidden"))

    def action_command_palette(self) -> None:
        self._show_command_palette()

    def _show_help(self) -> None:
        log = self.query_one("#messages", RichLog)
        help_text = """
[bold]Commands[/bold]
  /help, /h     Show this help
  /quit, /q    Exit
  /new, /n     Start new session
  /continue,/c Continue last session
  /session,/s  List sessions
  /models,/m   List Ollama models
  /files,/f    Toggle file tree

[bold]Keyboard Shortcuts[/bold]
  Ctrl+K       Command palette
  Ctrl+C       Quit
  N            New session
  M            Models
  F            Toggle files
        """
        log.write(Panel(help_text.strip(), title="Help", border_style="blue"))

    def _show_command_palette(self) -> None:
        log = self.query_one("#messages", RichLog)
        table = Table(box="minimal", title="Commands")
        table.add_column("Command", style="cyan")
        table.add_column("Description")
        for cmd, desc in [
            ("/help", "Show help"),
            ("/new", "New session"),
            ("/continue", "Continue session"),
            ("/session", "List sessions"),
            ("/models", "Show models"),
            ("/quit", "Exit"),
        ]:
            table.add_row(cmd, desc)
        log.write(table)

    def _show_models(self) -> None:
        try:
            from server import get_available_models
            models = get_available_models()
            if not models:
                self._add_error("No models. Ensure Ollama is running.")
                return
            log = self.query_one("#messages", RichLog)
            table = Table(title="Available Models")
            table.add_column("Model", style="cyan")
            for m in models[:20]:
                table.add_row(m)
            if len(models) > 20:
                table.add_row(f"... and {len(models) - 20} more")
            log.write(table)
        except Exception as e:
            self._add_error(str(e))

    def _add_user_message(self, text: str) -> None:
        log = self.query_one("#messages", RichLog)
        log.write(Panel(text, title="👤 You", border_style="cyan"))

    def _add_status(self, text: str) -> None:
        log = self.query_one("#messages", RichLog)
        log.write(f"[dim]> {text}[/dim]")

    def _add_tool(self, name: str) -> None:
        tools = self.query_one("#tools", ToolPanel)
        tools.add_tool(name, "running")

    def _add_assistant_content(self, content: str) -> None:
        if content.strip():
            log = self.query_one("#messages", RichLog)
            log.write(Panel(content, title="🤖 Assistant", border_style="green"))

    def _add_error(self, text: str) -> None:
        log = self.query_one("#messages", RichLog)
        log.write(Panel(f"[red]{text}[/red]", title="Error", border_style="red"))

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        node = event.node
        if node.data:
            path = Path(node.data)
            if path.is_file():
                self._add_status(f"Selected: {path.name}")

    async def _run_agent(self, message: str) -> None:
        self._streaming = True
        self._add_user_message(message)
        
        tools = self.query_one("#tools", ToolPanel)
        
        try:
            from server import stream_agent_events_with_history, ensure_model_exists
            import server as srv
            
            if self._model_override:
                srv.current_model = self._model_override
            
            ensure_model_exists(srv.current_model)
            self._current_model = srv.current_model
            self.query_one("#status-bar", StatusBar).update_status(model=self._current_model)
            
            tokens = []
            async for chunk in stream_agent_events_with_history(
                message, self._conv_id, mode=self._mode
            ):
                if not chunk.strip():
                    continue
                try:
                    data = json.loads(chunk.strip())
                    t = data.get("type")
                    
                    if t == "token" and data.get("content"):
                        tokens.append(data["content"])
                    elif t == "status":
                        self._add_status(data.get("content", ""))
                    elif t == "tool_start":
                        tool_name = data.get("tool", "?")
                        self._add_tool(tool_name)
                    elif t == "tool_end":
                        tool_name = data.get("tool", "?")
                        tools.update_tool(tool_name, "done")
                    elif t == "error":
                        self._add_error(data.get("content", "Unknown error"))
                except json.JSONDecodeError:
                    pass
            
            if tokens:
                self._add_assistant_content("".join(tokens))
            
            from chat_db import list_conversations
            items, _ = list_conversations(limit=1, offset=0)
            if items:
                self._conv_id = items[0]["id"]
                self.query_one("#status-bar", StatusBar).update_status(session=self._conv_id)
                
        except Exception as e:
            self._add_error(str(e))
        finally:
            self._streaming = False
            self.query_one("#input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if not value:
            return
        
        if value.lower() in ("/quit", "/exit", "/q"):
            self.exit()
            return
        
        if value.startswith("/"):
            cmd = value.lower().split()[0] if value.split() else value.lower()
            
            if cmd in ("/continue", "/c"):
                from chat_db import list_conversations
                items, _ = list_conversations(limit=1, offset=0)
                if items:
                    self._conv_id = items[0]["id"]
                    self.query_one("#status-bar", StatusBar).update_status(session=self._conv_id)
                    self._add_status(f"Continuing session {self._conv_id}")
                else:
                    self._add_error("No session to continue")
            
            elif cmd in ("/session", "/s"):
                from chat_db import list_conversations
                items, _ = list_conversations(limit=10, offset=0)
                if items:
                    table = Table(title="Sessions")
                    table.add_column("ID", style="cyan")
                    table.add_column("Title", style="green")
                    for i in items:
                        table.add_row(str(i["id"]), (i["title"] or "")[:50])
                    self.query_one("#messages", RichLog).write(table)
                else:
                    self._add_status("No sessions")
            
            elif cmd in ("/models", "/m"):
                self._show_models()
            
            elif cmd in ("/help", "/h"):
                self._show_help()
            
            elif cmd in ("/new", "/n"):
                self._conv_id = None
                self.query_one("#status-bar", StatusBar).update_status(session=None)
                self._add_status("New session started")
            
            elif cmd in ("/files", "/f"):
                self.action_toggle_files()
            
            else:
                self._add_status("Unknown command. /help for list.")
            
            self.query_one("#input", Input).clear()
            return
        
        self.query_one("#input", Input).clear()
        self.run_worker(self._run_agent(value))


def run_chat_app(mode: str = "agent", conv_id: int | None = None, model_override: str | None = None):
    app = ChatApp(mode=mode, conv_id=conv_id, model_override=model_override)
    
    async def run() -> None:
        await app.run_async()
    
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(run())
    except RuntimeError:
        asyncio.run(run())