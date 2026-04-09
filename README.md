# VenCoder (formerly AI Codec)

An AI-powered coding agent with memory, checkpoint/undo, permissions, comprehensive git workflow, code intelligence, skills/hooks, and real-time collaboration.

## Quick Links

- [User Guide](USER_GUIDE.md) - Complete usage documentation
- [Features](FEATURES.md) - New features documentation
- [Backend Documentation](BACKEND_DOCUMENTATION.md) - Technical reference
- [Improvement Proposal](IMPROVEMENT_PROPOSAL.md) - Implementation roadmap

## Structure

- `backend/` – Python: config, tools, agent (LangGraph + Ollama), semantic_index (ChromaDB + Ollama embeddings), FastAPI server with SSE.
- `electron/` – Electron main process, preload, renderer (chat UI, diff/shell blocks), styles.
- `vscode-extension/` – VS Code extension with chat and collaboration views.

## Requirements

- **Python 3.10–3.13** (Python 3.14 is not supported; ChromaDB has compatibility issues)
- Node.js for Electron
- Ollama for the LLM

## Quick Start

```bash
# Navigate to project
cd my-project

# Interactive chat
python -m backend.cli chat

# One-off task
python -m backend.cli run "Fix the login bug"

# Start API server
python -m backend.cli serve
```

## CLI Commands

```bash
# Chat modes
python -m backend.cli chat                    # Interactive chat
python -m backend.cli chat --continue        # Continue session
python -m backend.cli run "prompt"           # One-off task

# Memory & Checkpoints
python -m backend.cli memory show           # Show memory context
python -m backend.cli memory edit           # Edit memory file
python -m backend.cli checkpoint list       # List checkpoints
python -m backend.cli checkpoint undo        # Undo last change

# Permissions
python -m backend.cli permissions show       # Show permissions
python -m backend.cli permissions mode auto  # Set permission mode

# Git workflow (30+ commands)
python -m backend.cli git status            # Show status
python -m backend.cli git branch            # Show branches
python -m backend.cli git commit "message"  # Commit changes
python -m backend.cli git stash             # Stash changes
python -m backend.cli git push             # Push to remote

# Code quality
python -m backend.cli lint check src/       # Check lint issues
python -m backend.cli lint fix src/        # Auto-fix lint
python -m backend.cli typecheck src/       # Type check
python -m backend.cli security scan src/    # Security scan
python -m backend.cli review scan src/      # Code review
python -m backend.cli checks all           # Run all checks

# Skills & Hooks
python -m backend.cli skills list          # List skills
python -m backend.cli skills run lint-fix  # Run skill
python -m backend.cli hooks list           # List hooks
python -m backend.cli hooks enable pre-commit-lint  # Enable hook

# Sessions
python -m backend.cli session list          # List sessions
python -m backend.cli session fork <id>     # Fork session
python -m backend.cli session export <id>   # Export session
python -m backend.cli session search "query"  # Search sessions

# Collaboration
python -m backend.cli collab serve          # Start collab server
python -m backend.cli collab create "Room"  # Create room
python -m backend.cli collab join <room>   # Join room

# Plugins
python -m backend.cli plugin list          # List plugins
python -m backend.cli plugin create <name>  # Create plugin

# Standard
python -m backend.cli serve                 # API server
python -m backend.cli models                 # List models
python -m backend.cli index                  # Index workspace
```

## Features (v2.0)

### Phase 1: Memory & Safety
- **Memory System** - Persistent context via `.vencoder/memory.md`, project conventions, auto-learned info
- **Checkpoint/Undo** - Automatic file snapshots, session-scoped undo (up to 50 per session)
- **Permission Modes** - `ask`, `auto_edit`, `plan`, `auto` modes for safety control
- **Enhanced Git** - 30+ git operations (branch, commit, stash, push, pull, merge, rebase, etc.)

### Phase 2: Code Intelligence
- **Type Checking** - mypy, tsc, cargo check, go vet integration
- **Auto Lint Fix** - ruff, eslint, clippy, golangci-lint with auto-fix
- **Security Scanner** - Detect credentials, injection, XSS, SSRF, path traversal
- **Code Review** - Error handling, performance, best practices analysis

### Phase 3: Workflow Automation
- **Skills System** - 14 pre-built skills, custom skill creation, natural language triggers
- **Hooks System** - Event-based automation (pre-commit, post-edit, etc.)

### Phase 4: UX Enhancements
- **Enhanced TUI** - Diff view, error formatting, progress indicators, tables, trees
- **Session Management** - Fork, export, import, tagging, search, statistics

### Phase 5: Extensibility
- **Plugin System** - Full plugin architecture with 12+ hook types
- **External API** - REST API with auth, rate limiting, API keys
- **VS Code Extension** - Chat panel, inline actions, collaboration
- **Real-time Collaboration** - WebSocket server, cursor sharing, chat, room management

## Run (development)

1. **Backend**:
   ```bash
   cd backend
   pip install -r requirements.txt
   python -m uvicorn server:app --host 127.0.0.1 --port 8765
   ```

2. **Electron**:
   ```bash
   npm install
   npx electron .
   ```

3. **VS Code Extension**:
   ```bash
   cd vscode-extension
   npm install
   npm run compile
   ```

## Environment (backend)

- `OLLAMA_BASE_URL` – Ollama API (default `http://localhost:11434`).
- `LLM_MODEL` – Chat model (default `gpt-oss:20b`).
- `EMBEDDING_MODEL` – Embeddings (default `nomic-embed-text`).
- `WORKSPACE_ROOT` – Workspace for file tools and chat DB.
- `AGENT_TIMEOUT_SEC`, `AGENT_MAX_STEPS` – Optional limits.
- `NUM_PREDICT` – Max tokens per response (0 = unlimited).
- `NUM_CTX` – Ollama context window size (default 8192).
- `TEMPERATURE` – Sampling temperature (default 0.1).
- `REPEAT_PENALTY` – Reduces repetition (default 1.1).
- `OLLAMA_KEEP_ALIVE` – Model keep alive (default 10m).

**Best models:** `codellama`, `deepseek-coder`, `qwen2.5-coder`, `mistral`, `llama3.2`

- `MULTI_AGENT_ORCHESTRATOR_ENABLED` (default true) – Multi-task planning.
- `MODEL_CODER` – Model for coding tasks.
- `MODEL_PLANNER` – Model for planning.
- `MODEL_VL` – Vision model (default `qwen3-vl:8b`).

## All Features

- Chat with history; titles generated from first message.
- Agent tools: read_file, write_file, edit_file, delete_file, shell_command, run_tests, grep_search, glob_search, web_search, search_context, git operations (30+ commands).
- Inline diff and shell output in the UI.
- Index workspace for semantic search.
- Memory system for persistent context.
- Checkpoint/undo for safe experimentation.
- Permission modes for safety control.
- Type checking with mypy/tsc/cargo/go vet.
- Auto lint fix with ruff/eslint/clippy.
- Security vulnerability scanning.
- Code review with error handling and performance analysis.
- Skills system for custom automation.
- Hooks system for event-based automation.
- Enhanced TUI with diff view and progress indicators.
- Session management with fork, export, import, tags.
- Plugin system for extensibility.
- External REST API for integrations.
- VS Code extension with chat and collaboration.
- Real-time collaboration server.
