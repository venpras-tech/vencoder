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
        description="AI Dev CLI - coding agent with Ollama (like OpenCode, Claude Code)",
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

    memory_p = sub.add_parser("memory", help="Memory management")
    memory_sub = memory_p.add_subparsers(dest="memory_cmd")
    memory_sub.add_parser("show", help="Show current memory context")
    memory_sub.add_parser("stats", help="Show memory statistics")
    memory_edit = memory_sub.add_parser("edit", help="Edit memory file")
    memory_edit.add_argument("section", nargs="?", help="Section to edit (e.g., 'Project Overview')")

    checkpoint_p = sub.add_parser("checkpoint", help="Checkpoint management")
    checkpoint_sub = checkpoint_p.add_subparsers(dest="checkpoint_cmd")
    checkpoint_sub.add_parser("list", help="List checkpoints")
    checkpoint_sub.add_parser("undo", help="Undo to last checkpoint")
    checkpoint_undo = checkpoint_sub.add_parser("undo-id", help="Undo to specific checkpoint")
    checkpoint_undo.add_argument("checkpoint_id", help="Checkpoint ID to restore")
    checkpoint_sub.add_parser("stats", help="Show checkpoint statistics")
    checkpoint_sub.add_parser("clear", help="Clear all checkpoints for current session")

    perm_p = sub.add_parser("permissions", help="Permission management")
    perm_sub = perm_p.add_subparsers(dest="perm_cmd")
    perm_sub.add_parser("show", help="Show current permission settings")
    perm_mode = perm_sub.add_parser("mode", help="Set permission mode")
    perm_mode.add_argument("mode", choices=["ask", "auto_edit", "plan", "auto"], help="Permission mode")
    perm_sub.add_parser("cycle", help="Cycle to next permission mode")
    perm_sub.add_parser("reset", help="Reset permissions to defaults")

    git_p = sub.add_parser("git", help="Git operations")
    git_sub = git_p.add_subparsers(dest="git_cmd")
    git_sub.add_parser("status", help="Show git status")
    git_sub.add_parser("branch", help="Show branches")
    git_sub.add_parser("log", help="Show commit log")
    git_stash = git_sub.add_parser("stash", help="Stash changes")
    git_stash.add_argument("--message", "-m", help="Stash message")
    git_sub.add_parser("stash-pop", help="Pop stash")

    # Code quality commands
    lint_p = sub.add_parser("lint", help="Run linter and auto-fix")
    lint_sub = lint_p.add_subparsers(dest="lint_cmd")
    lint_sub.add_parser("check", help="Run linter")
    lint_check = lint_sub.add_parser("fix", help="Auto-fix lint issues")
    lint_check.add_argument("file", nargs="?", help="File to fix (default: all)")
    lint_sub.add_parser("check-project", help="Lint entire project")
    lint_sub.add_parser("fix-project", help="Auto-fix entire project")

    type_p = sub.add_parser("typecheck", help="Run type checker")
    type_sub = type_p.add_subparsers(dest="type_cmd")
    type_check = type_sub.add_parser("check", help="Type check file or project")
    type_check.add_argument("file", nargs="?", help="File to check (default: project)")

    security_p = sub.add_parser("security", help="Security scanning")
    security_sub = security_p.add_subparsers(dest="security_cmd")
    security_scan = security_sub.add_parser("scan", help="Scan for security issues")
    security_scan.add_argument("file", nargs="?", help="File to scan (default: project)")

    review_p = sub.add_parser("review", help="Code review")
    review_sub = review_p.add_subparsers(dest="review_cmd")
    review_scan = review_sub.add_parser("scan", help="Review code quality")
    review_scan.add_argument("file", nargs="?", help="File to review (default: project)")

    checks_p = sub.add_parser("checks", help="Run all code quality checks")
    checks_sub = checks_p.add_subparsers(dest="checks_cmd")
    checks_all = checks_sub.add_parser("all", help="Run all checks")
    checks_all.add_argument("file", nargs="?", help="File to check (default: project)")

    # Skills commands
    skills_p = sub.add_parser("skills", help="Skills management")
    skills_sub = skills_p.add_subparsers(dest="skills_cmd")
    skills_sub.add_parser("list", help="List all skills")
    skills_exec = skills_sub.add_parser("run", help="Execute a skill")
    skills_exec.add_argument("name", help="Skill name to execute")
    skills_create = skills_sub.add_parser("create", help="Create a new skill")
    skills_create.add_argument("name", help="Skill name")
    skills_create.add_argument("command", help="Command to execute")
    skills_create.add_argument("--description", "-d", help="Skill description")
    skills_create.add_argument("--triggers", "-t", help="Comma-separated triggers")
    skills_sub.add_parser("delete", help="Delete a skill").add_argument("name", help="Skill name")
    skills_sub.add_parser("templates", help="Show skill templates")

    # Hooks commands
    hooks_p = sub.add_parser("hooks", help="Hooks management")
    hooks_sub = hooks_p.add_subparsers(dest="hooks_cmd")
    hooks_sub.add_parser("list", help="List all hooks")
    hooks_create = hooks_sub.add_parser("create", help="Create a new hook")
    hooks_create.add_argument("name", help="Hook name")
    hooks_create.add_argument("event", help="Event (e.g., before_commit, after_edit)")
    hooks_create.add_argument("command", help="Command to execute")
    hooks_create.add_argument("--description", "-d", help="Hook description")
    hooks_sub.add_parser("delete", help="Delete a hook").add_argument("name", help="Hook name")
    hooks_enable = hooks_sub.add_parser("enable", help="Enable a hook")
    hooks_enable.add_argument("name", help="Hook name")
    hooks_disable = hooks_sub.add_parser("disable", help="Disable a hook")
    hooks_disable.add_argument("name", help="Hook name")
    hooks_sub.add_parser("templates", help="Show hook templates")

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
                print("AI Dev - type your message and press Enter. Ctrl+C to exit, /quit to exit.")
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


def _cmd_memory(args):
    _ensure_workspace()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    
    from memory import MemoryManager
    
    if not hasattr(args, "memory_cmd"):
        args.memory_cmd = "show"
    
    mm = MemoryManager(Path.cwd())
    
    if args.memory_cmd == "show":
        context = mm.get_session_context()
        if context:
            print("=== Memory Context ===")
            print(context)
        else:
            print("No memory context found.")
            print("Create .vencoder/memory.md or .vencoder/conventions.md to add context.")
        return
    
    if args.memory_cmd == "stats":
        stats = mm.get_memory_stats()
        print("=== Memory Statistics ===")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        return
    
    if args.memory_cmd == "edit":
        import subprocess
        memory_file = mm.memory_file
        subprocess.run([os.environ.get("EDITOR", "nano"), str(memory_file)])
        return


def _cmd_checkpoint(args):
    _ensure_workspace()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    
    from checkpoint import CheckpointManager
    
    if not hasattr(args, "checkpoint_cmd"):
        args.checkpoint_cmd = "list"
    
    cm = CheckpointManager(Path.cwd())
    
    if args.checkpoint_cmd == "list":
        checkpoints = cm.list_checkpoints()
        if not checkpoints:
            print("No checkpoints found.")
            return
        print("=== Checkpoints ===")
        for cp in checkpoints:
            status = "[RESTORED]" if cp.restored else ""
            print(f"  {cp.id} | {cp.file_path} | {cp.action} | {cp.created_at[:19]} {status}")
        return
    
    if args.checkpoint_cmd == "undo":
        success = cm.undo_last()
        print("Undo successful." if success else "No checkpoint to undo.")
        return
    
    if args.checkpoint_cmd == "undo-id":
        success = cm.undo_to_checkpoint(args.checkpoint_id)
        print("Undo successful." if success else f"Checkpoint '{args.checkpoint_id}' not found.")
        return
    
    if args.checkpoint_cmd == "stats":
        stats = cm.get_stats()
        print("=== Checkpoint Statistics ===")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        return
    
    if args.checkpoint_cmd == "clear":
        cm.clear_session_checkpoints()
        print("Checkpoints cleared.")


def _cmd_permissions(args):
    _ensure_workspace()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    
    from permissions import PermissionManager, PermissionMode
    
    if not hasattr(args, "perm_cmd"):
        args.perm_cmd = "show"
    
    pm = PermissionManager(Path.cwd() / ".vencoder" / "permissions.json")
    
    if args.perm_cmd == "show":
        summary = pm.get_permission_summary()
        print("=== Permission Settings ===")
        for key, value in summary.items():
            print(f"  {key}: {value}")
        return
    
    if args.perm_cmd == "mode":
        try:
            mode = PermissionMode(args.mode)
            pm.set_mode(mode)
            print(f"Permission mode set to: {mode.value}")
        except ValueError:
            print(f"Invalid mode: {args.mode}")
            print("Valid modes: ask, auto_edit, plan, auto")
        return
    
    if args.perm_cmd == "cycle":
        new_mode = pm.cycle_mode()
        print(f"Permission mode cycled to: {new_mode.value}")
        return
    
    if args.perm_cmd == "reset":
        pm.reset_to_defaults()
        print("Permissions reset to defaults.")


def _cmd_git(args):
    _ensure_workspace()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    
    from tools.git_tools import (
        git_status, git_branch, git_log, git_stash, git_stash_pop,
        git_current_branch, git_short_status, git_remote
    )
    
    if not hasattr(args, "git_cmd"):
        args.git_cmd = "status"
    
    if args.git_cmd == "status":
        print("=== Git Status ===")
        print(git_short_status())
        print()
        print(git_status())
        return
    
    if args.git_cmd == "branch":
        print("=== Git Branches ===")
        current = git_current_branch()
        branches = git_branch()
        print(f"Current: {current}")
        print(branches)
        return
    
    if args.git_cmd == "log":
        print("=== Git Log ===")
        print(git_log(n=10))
        return
    
    if args.git_cmd == "stash":
        msg = getattr(args, "message", None)
        print(git_stash(message=msg))
        return
    
    if args.git_cmd == "stash-pop":
        print(git_stash_pop())
        return


def _cmd_lint(args):
    _ensure_workspace()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    
    from lint_fixer import LintFixer
    
    fixer = LintFixer(Path.cwd())
    
    if not hasattr(args, "lint_cmd"):
        args.lint_cmd = "check"
    
    if args.lint_cmd == "check":
        if getattr(args, "file", None):
            result = fixer.lint_file(args.file)
            print(fixer.format_issues(result))
        else:
            print("=== Lint Check ===")
            print("Specify a file to lint or use 'lint check-project'")
        return
    
    if args.lint_cmd == "fix":
        if getattr(args, "file", None):
            fixed, output = fixer.fix_file(args.file)
            print(fixer.format_fix_result(fixed, output))
        else:
            print("=== Auto-fix Project ===")
            results = fixer.lint_project()
            for r in results:
                print(fixer.format_issues(r))
        return
    
    if args.lint_cmd == "check-project":
        print("=== Lint Project ===")
        results = fixer.lint_project()
        for r in results:
            print(fixer.format_issues(r))
        return
    
    if args.lint_cmd == "fix-project":
        print("=== Auto-fix Project ===")
        from pathlib import Path
        fixed_count = 0
        for ext in [".py", ".js", ".ts", ".jsx", ".tsx"]:
            for file_path in Path.cwd().rglob(f"*{ext}"):
                if any(skip in str(file_path) for skip in ["node_modules", ".venv", "__pycache__"]):
                    continue
                fixed, output = fixer.fix_file(str(file_path))
                if fixed:
                    print(f"Fixed: {file_path}")
                    fixed_count += 1
        print(f"\nTotal files fixed: {fixed_count}")
        return


def _cmd_typecheck(args):
    _ensure_workspace()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    
    from type_checker import TypeChecker
    
    checker = TypeChecker(Path.cwd())
    
    if not hasattr(args, "type_cmd"):
        args.type_cmd = "check"
    
    if args.type_cmd == "check":
        if getattr(args, "file", None):
            result = checker.check_file(args.file)
            print(checker.format_errors(result))
        else:
            print("=== Type Check Project ===")
            results = checker.check_project()
            if not results:
                print("No type checkers configured or no source files found.")
                return
            for r in results:
                print(checker.format_errors(r))
        return


def _cmd_security(args):
    _ensure_workspace()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    
    from security_scanner import SecurityScanner
    
    scanner = SecurityScanner(Path.cwd())
    
    if not hasattr(args, "security_cmd"):
        args.security_cmd = "scan"
    
    if args.security_cmd == "scan":
        if getattr(args, "file", None):
            issues = scanner.scan_file(args.file)
            result = type('ScanResult', (), {
                'passed': len(issues) == 0,
                'issues': issues,
                'files_scanned': 1,
                'scan_time': 0
            })()
            print(scanner.format_issues(result))
        else:
            print("=== Security Scan ===")
            result = scanner.scan_project()
            print(scanner.format_issues(result))
        return


def _cmd_review(args):
    _ensure_workspace()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    
    from code_review import CodeReviewer
    
    reviewer = CodeReviewer(Path.cwd())
    
    if not hasattr(args, "review_cmd"):
        args.review_cmd = "scan"
    
    if args.review_cmd == "scan":
        if getattr(args, "file", None):
            result = reviewer.review_file(args.file)
            print(reviewer.format_result(result))
        else:
            print("=== Code Review (Project) ===")
            summary = reviewer.review_project()
            print(reviewer.format_summary(summary))
        return


def _cmd_checks(args):
    _ensure_workspace()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    
    from type_checker import TypeChecker
    from lint_fixer import LintFixer
    from security_scanner import SecurityScanner
    from code_review import CodeReviewer
    
    file_path = getattr(args, "file", None)
    
    print("=" * 60)
    print("CODE QUALITY CHECKS")
    print("=" * 60)
    
    print("\n### TYPE CHECKING ###")
    checker = TypeChecker(Path.cwd())
    if file_path:
        r = checker.check_file(file_path)
        print(checker.format_errors(r))
    else:
        results = checker.check_project()
        for r in results:
            print(checker.format_errors(r))
    
    print("\n### LINTING ###")
    fixer = LintFixer(Path.cwd())
    if file_path:
        r = fixer.lint_file(file_path)
        print(fixer.format_issues(r))
    else:
        results = fixer.lint_project()
        for r in results:
            print(fixer.format_issues(r))
    
    print("\n### SECURITY SCAN ###")
    scanner = SecurityScanner(Path.cwd())
    if file_path:
        issues = scanner.scan_file(file_path)
        r = type('ScanResult', (), {
            'passed': len(issues) == 0,
            'issues': issues,
            'files_scanned': 1,
            'scan_time': 0
        })()
        print(scanner.format_issues(r))
    else:
        r = scanner.scan_project()
        print(scanner.format_issues(r))
    
    print("\n### CODE REVIEW ###")
    reviewer = CodeReviewer(Path.cwd())
    if file_path:
        r = reviewer.review_file(file_path)
        print(reviewer.format_result(r))
    else:
        s = reviewer.review_project()
        print(reviewer.format_summary(s))


def _cmd_skills(args):
    _ensure_workspace()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    
    from skills import SkillManager, Skill
    
    manager = SkillManager(Path.cwd())
    
    if not hasattr(args, "skills_cmd"):
        args.skills_cmd = "list"
    
    if args.skills_cmd == "list":
        print("=== Available Skills ===")
        skills = manager.list_skills()
        if not skills:
            print("No skills found.")
            return
        for skill in skills:
            icon = skill.get("icon", "⚡")
            status = "✅" if skill.get("enabled") else "❌"
            print(f"{icon} {status} {skill['name']}: {skill['description']}")
            print(f"   Triggers: {', '.join(skill.get('triggers', [])[:5])}")
            print()
        return
    
    if args.skills_cmd == "run":
        print(f"=== Running Skill: {args.name} ===")
        result = manager.execute_skill(args.name)
        if result.success:
            print(f"✅ Success:")
            print(result.output)
        else:
            print(f"❌ Failed: {result.error}")
        return
    
    if args.skills_cmd == "create":
        triggers = getattr(args, "triggers", "") or ""
        trigger_list = [t.strip() for t in triggers.split(",") if t.strip()]
        desc = getattr(args, "description", "") or f"Custom skill: {args.name}"
        
        skill = Skill(
            name=args.name,
            description=desc,
            command=args.command,
            triggers=trigger_list,
        )
        if manager.save_skill(skill):
            print(f"✅ Skill '{args.name}' created successfully.")
        else:
            print(f"❌ Failed to create skill '{args.name}'.")
        return
    
    if args.skills_cmd == "delete":
        if manager.delete_skill(args.name):
            print(f"✅ Skill '{args.name}' deleted.")
        else:
            print(f"❌ Skill '{args.name}' not found.")
        return
    
    if args.skills_cmd == "templates":
        print("=== Skill Templates ===")
        print("Create custom skills with: codec skills create <name> <command>")
        print()
        print("Example: codec skills create mytest 'pytest {file}' --triggers 'run tests,test file'")


def _cmd_hooks(args):
    _ensure_workspace()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    
    from hooks import HookManager, Hook, HookEvent
    
    manager = HookManager(Path.cwd())
    
    if not hasattr(args, "hooks_cmd"):
        args.hooks_cmd = "list"
    
    if args.hooks_cmd == "list":
        print("=== Available Hooks ===")
        hooks = manager.list_hooks()
        if not hooks:
            print("No hooks found.")
            return
        for hook in hooks:
            status = "✅" if hook.get("enabled") else "❌"
            print(f"{status} {hook['name']} ({hook['event']}): {hook['description']}")
            print(f"   Command: {hook.get('command', 'N/A')[:60]}")
            print()
        return
    
    if args.hooks_cmd == "create":
        desc = getattr(args, "description", "") or f"Custom hook: {args.name}"
        
        hook = Hook(
            name=args.name,
            event=args.event,
            command=args.command,
            description=desc,
        )
        if manager.register_hook(hook):
            print(f"✅ Hook '{args.name}' created for event '{args.event}'.")
        else:
            print(f"❌ Failed to create hook '{args.name}'.")
        return
    
    if args.hooks_cmd == "delete":
        if manager.unregister_hook(args.name):
            print(f"✅ Hook '{args.name}' deleted.")
        else:
            print(f"❌ Hook '{args.name}' not found.")
        return
    
    if args.hooks_cmd == "enable":
        if manager.enable_hook(args.name):
            print(f"✅ Hook '{args.name}' enabled.")
        else:
            print(f"❌ Hook '{args.name}' not found.")
        return
    
    if args.hooks_cmd == "disable":
        if manager.disable_hook(args.name):
            print(f"✅ Hook '{args.name}' disabled.")
        else:
            print(f"❌ Hook '{args.name}' not found.")
        return
    
    if args.hooks_cmd == "templates":
        print("=== Hook Templates ===")
        templates = manager.get_available_templates()
        for template in templates:
            print(f"  - {template}")
        print()
        print("Create: codec hooks create <name> <event> <command>")


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
    if args.command == "memory":
        _cmd_memory(args)
        return
    if args.command == "checkpoint":
        _cmd_checkpoint(args)
        return
    if args.command == "permissions":
        _cmd_permissions(args)
        return
    if args.command == "git":
        _cmd_git(args)
        return
    if args.command == "lint":
        _cmd_lint(args)
        return
    if args.command == "typecheck":
        _cmd_typecheck(args)
        return
    if args.command == "security":
        _cmd_security(args)
        return
    if args.command == "review":
        _cmd_review(args)
        return
    if args.command == "checks":
        _cmd_checks(args)
        return
    if args.command == "skills":
        _cmd_skills(args)
        return
    if args.command == "hooks":
        _cmd_hooks(args)
        return

    prompt_list = getattr(args, "prompt", None) or getattr(args, "prompt_args", []) or []
    if not hasattr(args, "prompt"):
        args.prompt = prompt_list
    if args.command is None:
        args.command = "run" if prompt_list else "chat"

    if args.command in ("run", "chat"):
        asyncio.run(_run_chat(args, model_override=args.model))
    else:
        print("Usage: codec run <prompt> | codec chat | codec serve | codec models")
        print("  codec run 'fix the bug'    - one-off prompt")
        print("  codec chat               - interactive mode")
        print("  codec chat -c            - continue last session")
        print("  codec serve              - start API server")
        print()
        print("  codec memory show        - show memory context")
        print("  codec checkpoint list    - list checkpoints")
        print("  codec permissions show   - show permission settings")
        print("  codec git status        - show git status")
        print()
        print("  codec lint check        - lint file")
        print("  codec lint fix          - auto-fix lint issues")
        print("  codec typecheck         - type check project")
        print("  codec security scan     - security scan")
        print("  codec review scan       - code review")
        print("  codec checks all        - run all checks")
        print()
        print("  codec skills list       - list skills")
        print("  codec skills run <name> - execute skill")
        print("  codec hooks list        - list hooks")
        print("  codec hooks create      - create hook")


if __name__ == "__main__":
    main()
