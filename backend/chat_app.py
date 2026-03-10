import json
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Input, RichLog, Static
from rich.panel import Panel
from rich.table import Table

from config import WORKSPACE_ROOT


class StatusBar(Static):
    def __init__(self, model: str = "", mode: str = "agent", session: int | None = None, **kwargs):
        super().__init__("", **kwargs)
        self._model = model or "?"
        self._mode = mode or "agent"
        self._session = session

    def update_status(self, model: str = None, mode: str = None, session: int | None = None):
        if model is not None:
            self._model = model
        if mode is not None:
            self._mode = mode
        if session is not None:
            self._session = session
        cwd = Path(WORKSPACE_ROOT).name or "."
        parts = [f"[cyan]{self._model}[/]", f"[green]{self._mode}[/]"]
        if self._session:
            parts.append(f"[dim]session {self._session}[/]")
        parts.append(f"[dim]{cwd}[/]")
        self.update(" | ".join(parts))


class ChatApp(App):
    CSS = """
    Screen {
        layout: vertical;
    }
    #chat {
        height: 1fr;
        padding: 1 2;
    }
    #chat.dense {
        padding: 0 1;
    }
    #input {
        padding: 1 2;
        border-top: solid $primary;
    }
    #input.dense {
        padding: 0 1;
    }
    #status-bar {
        height: 1;
        padding: 0 2;
        color: $text-muted;
    }
    #status-bar.dense {
        padding: 0 1;
    }
    #footer-row {
        height: 1;
        dock: bottom;
    }
    #footer-row Footer {
        min-width: 30;
    }
    #status-bar {
        width: 1fr;
        text-align: right;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit"),
        Binding("f1", "help", "Help"),
        Binding("n", "new_session", "New"),
        Binding("m", "models", "Models"),
    ]

    def __init__(self, mode: str = "agent", conv_id: int | None = None, model_override: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._mode = mode
        self._conv_id = conv_id
        self._model_override = model_override
        self._current_model = ""
        self._streaming = False
        self._dense = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RichLog(markup=True, highlight=True, id="chat")
        yield Input(placeholder="Message... (Enter to send, /help for commands)", id="input")
        with Horizontal(id="footer-row"):
            yield Footer()
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
        self.query_one("#chat", RichLog).write(
            Panel(
                "[bold]AI Codec[/bold] - coding agent (Ollama)\n\n"
                "[dim]Type a message or /help for commands[/dim]",
                border_style="green",
            )
        )

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

    def _show_help(self) -> None:
        log = self.query_one("#chat", RichLog)
        help_text = """
[bold]Commands[/bold]
  /help, /h     Show this help
  /quit, /q     Exit
  /new, /n      Start new session
  /continue,/c  Continue last session
  /session,/s   List sessions
  /models,/m    List Ollama models
  /layout,/l    Toggle dense layout

[bold]Keys[/bold]
  F1            Help
  N             New session
  M             Models
  Q             Quit
"""
        log.write(Panel(help_text.strip(), title="Help", border_style="blue"))

    def _show_models(self) -> None:
        try:
            from server import get_available_models
            models = get_available_models()
            if not models:
                self._add_error("No models. Ensure Ollama is running or add GGUF files to the models folder.")
                return
            log = self.query_one("#chat", RichLog)
            table = Table(title="Models")
            table.add_column("Model", style="cyan")
            for m in models[:20]:
                table.add_row(m)
            if len(models) > 20:
                table.add_row(f"... and {len(models) - 20} more")
            log.write(table)
        except Exception as e:
            self._add_error(str(e))

    def _add_user_message(self, text: str) -> None:
        log = self.query_one("#chat", RichLog)
        log.write(Panel(text, title="[cyan]You[/cyan]", border_style="cyan"))

    def _add_status(self, text: str) -> None:
        log = self.query_one("#chat", RichLog)
        log.write(f"[dim]> {text}[/dim]")

    def _add_tool(self, name: str) -> None:
        log = self.query_one("#chat", RichLog)
        log.write(f"  [yellow]{name}[/yellow]")

    def _add_assistant_content(self, content: str) -> None:
        if content.strip():
            log = self.query_one("#chat", RichLog)
            log.write(Panel(content, title="[green]Assistant[/green]", border_style="green"))

    def _add_error(self, text: str) -> None:
        log = self.query_one("#chat", RichLog)
        log.write(Panel(f"[red]{text}[/red]", title="Error", border_style="red"))

    def _toggle_dense(self) -> None:
        self._dense = not self._dense
        chat = self.query_one("#chat", RichLog)
        inp = self.query_one("#input", Input)
        bar = self.query_one("#status-bar", StatusBar)
        for w in (chat, inp, bar):
            w.set_class(self._dense, "dense")
        self._add_status("Dense layout" if self._dense else "Default layout")

    async def _run_agent(self, message: str) -> None:
        self._streaming = True
        self._add_user_message(message)
        try:
            from server import stream_agent_events_with_history, ensure_model_exists, current_model
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
                        self._add_tool(data.get("tool", "?"))
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
                        table.add_row(str(i["id"]), (i["title"] or "")[:40])
                    self.query_one("#chat", RichLog).write(table)
                else:
                    self._add_status("No sessions")
            elif cmd in ("/models", "/m"):
                self._show_models()
            elif cmd in ("/help", "/h"):
                self._show_help()
            elif cmd in ("/new", "/n"):
                self._conv_id = None
                self.query_one("#status-bar", StatusBar).update_status(session=None)
                self._add_status("New session")
            elif cmd in ("/layout", "/l"):
                self._toggle_dense()
            else:
                self._add_status("Unknown command. /help for list.")
            self.query_one("#input", Input).clear()
            return
        self.query_one("#input", Input).clear()
        self.run_worker(self._run_agent(value))


def run_chat_app(mode: str = "agent", conv_id: int | None = None, model_override: str | None = None):
    app = ChatApp(mode=mode, conv_id=conv_id, model_override=model_override)
    app.run()
