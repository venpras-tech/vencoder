#!/usr/bin/env python3
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path


def _get_tui(args):
    if getattr(args, "no_tui", False):
        return None
    try:
        from tui import (
            is_available,
            print_user,
            print_assistant_stream_chunk,
            print_assistant_stream_end,
            print_status,
            print_tool,
            print_error,
            print_welcome,
            print_rule,
            print_session_list,
            prompt_input,
        )
        if is_available():
            return type("TUI", (), {
                "print_user": staticmethod(print_user),
                "stream_chunk": staticmethod(print_assistant_stream_chunk),
                "stream_end": staticmethod(print_assistant_stream_end),
                "status": staticmethod(print_status),
                "tool": staticmethod(print_tool),
                "error": staticmethod(print_error),
                "welcome": staticmethod(print_welcome),
                "rule": staticmethod(print_rule),
                "session_list": staticmethod(print_session_list),
                "prompt": staticmethod(prompt_input),
            })()
    except ImportError:
        pass
    return None


def _ensure_workspace():
    root = Path.cwd().resolve()
    os.environ.setdefault("WORKSPACE_ROOT", str(root))
    return root


def _parse_args():
    parser = argparse.ArgumentParser(
        prog="codec",
        description="AI Codec CLI - coding agent with Ollama (like OpenCode, Claude Code)",
    )
    parser.add_argument("--version", "-v", action="version", version="1.0.0")
    parser.add_argument("prompt_args", nargs="*", help=argparse.SUPPRESS)
    parser.add_argument("--dir", "-d", type=str, default=".", help="Working directory (default: cwd)")
    parser.add_argument("--model", "-m", type=str, help="Ollama model to use")
    parser.add_argument("--mode", type=str, choices=["agent", "ask", "plan"], default="agent", help="Mode: agent (edit), ask (read-only), plan")
    sub = parser.add_subparsers(dest="command", help="Commands")

    run_p = sub.add_parser("run", help="Run a single prompt and exit")
    run_p.add_argument("prompt", nargs="*", help="Prompt (joined if multiple)", default=[])
    run_p.add_argument("--continue", "-c", dest="continue_", action="store_true", help="Continue last session")
    run_p.add_argument("--session", "-s", type=int, help="Session ID to continue")
    run_p.add_argument("--format", choices=["default", "json"], default="default", help="Output format")
    run_p.add_argument("--no-tui", action="store_true", help="Disable rich TUI (plain text)")

    chat_p = sub.add_parser("chat", help="Interactive chat (default if no command)")
    chat_p.add_argument("--continue", "-c", dest="continue_", action="store_true", help="Continue last session")
    chat_p.add_argument("--session", "-s", type=int, help="Session ID to continue")
    chat_p.add_argument("--no-tui", action="store_true", help="Disable TUI (plain text)")
    chat_p.add_argument("prompt", nargs="*", help="Initial prompt (optional)", default=[])

    serve_p = sub.add_parser("serve", help="Start API server")
    serve_p.add_argument("--port", "-p", type=int, default=8765, help="Port")
    serve_p.add_argument("--host", type=str, default="127.0.0.1", help="Host")

    sub.add_parser("models", help="List available Ollama models")
    sub.add_parser("index", help="Index workspace for semantic search")

    session_p = sub.add_parser("session", help="Session management")
    session_sub = session_p.add_subparsers(dest="session_cmd")
    session_sub.add_parser("list", help="List conversations")

    return parser.parse_args()


def _get_last_conversation_id():
    from chat_db import list_conversations
    items, _ = list_conversations(limit=1, offset=0)
    return items[0]["id"] if items else None


async def _run_chat(args, model_override=None):
    root = Path(args.dir).resolve()
    if not root.is_dir():
        print(f"Error: not a directory: {args.dir}", file=sys.stderr)
        sys.exit(1)
    os.environ["WORKSPACE_ROOT"] = str(root)

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    if model_override:
        os.environ["LLM_MODEL"] = model_override

    import server as srv
    from server import stream_agent_events_with_history, ensure_model_exists, current_model
    if model_override:
        srv.current_model = model_override
    from chat_db import create_conversation, add_message, get_messages, list_conversations, set_conversation_title

    conv_id = None
    if getattr(args, "continue_", False) or (hasattr(args, "session") and args.session):
        conv_id = args.session if hasattr(args, "session") and args.session else _get_last_conversation_id()
        if not conv_id:
            print("No previous session to continue.", file=sys.stderr)
            sys.exit(1)
        print(f"Continuing session {conv_id}")

    prompt_parts = getattr(args, "prompt", []) or getattr(args, "prompt_args", []) or []
    initial_prompt = " ".join(prompt_parts).strip() if prompt_parts else None

    tui = _get_tui(args)
    if not getattr(args, "no_tui", False):
        try:
            from chat_app import run_chat_app
            run_chat_app(mode=args.mode, conv_id=conv_id, model_override=model_override)
            return
        except ImportError:
            pass

    async def _stream_display(stream, use_json=False):
        tokens = []
        async for chunk in stream:
            if not chunk.strip():
                continue
            try:
                data = json.loads(chunk.strip())
                if data.get("type") == "token" and data.get("content"):
                    tokens.append(data["content"])
                    if not use_json:
                        if tui:
                            tui.stream_chunk(data["content"])
                        else:
                            print(data["content"], end="", flush=True)
                elif data.get("type") == "status" and tui:
                    tui.status(data.get("content", ""))
                elif data.get("type") == "tool_start" and tui:
                    tui.tool(data.get("tool", "?"))
                elif data.get("type") == "error":
                    err = data.get("content", "Unknown error")
                    if tui:
                        tui.error(err)
                    else:
                        print(f"\nError: {err}", file=sys.stderr)
            except json.JSONDecodeError:
                pass
        if not use_json:
            if tui:
                tui.stream_end()
            else:
                print()
        return "".join(tokens)

    if args.command == "run" and initial_prompt:
        ensure_model_exists(srv.current_model)
        content = await _stream_display(
            stream_agent_events_with_history(initial_prompt, conv_id, mode=args.mode),
            use_json=(args.format == "json"),
        )
        if args.format == "json":
            print(json.dumps({"content": content}))
        return

    if args.command == "chat" or (args.command is None and initial_prompt):
        if initial_prompt:
            if tui:
                tui.print_user(initial_prompt)
            ensure_model_exists(srv.current_model)
            await _stream_display(
                stream_agent_events_with_history(initial_prompt, conv_id, mode=args.mode),
            )
            conv_id = _get_last_conversation_id()
        else:
            if tui:
                tui.welcome(args.mode)
            else:
                print("AI Codec - type your message and press Enter. Ctrl+C to exit, /quit to exit.")
                print()

        while True:
            try:
                user_input = tui.prompt() if tui else input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not user_input:
                continue
            if user_input.lower() in ("/quit", "/exit", "/q"):
                break
            if user_input.startswith("/"):
                if user_input == "/continue" or user_input == "/c":
                    conv_id = _get_last_conversation_id()
                    print(f"Continue session {conv_id}" if conv_id else "No session")
                elif user_input == "/session" or user_input == "/s":
                    from chat_db import list_conversations
                    items, _ = list_conversations(limit=10, offset=0)
                    if tui:
                        tui.session_list(items)
                    else:
                        for i in items:
                            print(f"  {i['id']}: {i['title']}")
                elif user_input == "/help" or user_input == "/h":
                    print("Commands: /quit, /continue, /session, /help")
                else:
                    print("Commands: /quit, /continue, /session, /help")
                continue

            if tui:
                tui.print_user(user_input)
            ensure_model_exists(srv.current_model)
            await _stream_display(
                stream_agent_events_with_history(user_input, conv_id, mode=args.mode),
            )
            conv_id = _get_last_conversation_id()
        return


def _cmd_models():
    _ensure_workspace()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from server import get_available_models
    models = get_available_models()
    if not models:
        print("No models found. Ensure Ollama is running or add GGUF files to the models folder.")
        return
    for m in models:
        print(m)


def _cmd_index():
    _ensure_workspace()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from semantic_index import get_vector_store, index_workspace_files
    store = get_vector_store(clear=True)
    count = index_workspace_files(store)
    print(f"Indexed {count} files.")


def _cmd_session_list():
    _ensure_workspace()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from chat_db import list_conversations
    items, total = list_conversations(limit=50, offset=0)
    print(f"Sessions ({total}):")
    for i in items:
        print(f"  {i['id']}: {i['title']}")


def _cmd_serve(args):
    root = Path(args.dir).resolve()
    os.environ["WORKSPACE_ROOT"] = str(root)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    if args.model:
        os.environ["LLM_MODEL"] = args.model
    from server import run_server
    run_server(host=args.host, port=args.port)


def main():
    args = _parse_args()
    root = Path(args.dir).resolve()
    if not root.is_dir():
        print(f"Error: not a directory: {args.dir}", file=sys.stderr)
        sys.exit(1)
    os.environ["WORKSPACE_ROOT"] = str(root)

    if args.command == "models":
        _cmd_models()
        return
    if args.command == "index":
        _cmd_index()
        return
    if args.command == "serve":
        _cmd_serve(args)
        return
    if args.command == "session" and getattr(args, "session_cmd", None) == "list":
        _cmd_session_list()
        return

    prompt_list = getattr(args, "prompt", None) or getattr(args, "prompt_args", []) or []
    if not hasattr(args, "prompt"):
        args.prompt = prompt_list
    if args.command is None:
        args.command = "run" if prompt_list else "chat"

    if args.command in ("run", "chat"):
        asyncio.run(_run_chat(args, model_override=args.model))
    else:
        print("Usage: codec run <prompt> | codec chat | codec serve | codec models | codec index")
        print("  codec run 'fix the bug'   - one-off prompt")
        print("  codec chat               - interactive mode")
        print("  codec chat -c            - continue last session")
        print("  codec serve              - start API server")


if __name__ == "__main__":
    main()
