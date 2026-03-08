# AI Codec

Electron desktop app with an AI coding agent (LangGraph + Ollama), semantic code search (ChromaDB + Ollama embeddings), and file/shell tools.

## Structure

- `backend/` – Python: config, tools, agent (LangGraph + Ollama), semantic_index (ChromaDB + Ollama embeddings), FastAPI server with SSE.
- `electron/` – Electron main process, preload, renderer (chat UI, diff/shell blocks), styles.

## Requirements

- **Python 3.10–3.13** (Python 3.14 is not supported; ChromaDB has compatibility issues)
- Node.js for Electron
- Ollama for the LLM

## CLI (like OpenCode, Claude Code)

From project root, use the `codec` command:

```bash
npm run codec -- run "fix the bug in main.py"   # one-off prompt
npm run codec -- chat                            # interactive mode
npm run codec -- chat -c                         # continue last session
npm run codec -- serve                           # start API server
npm run codec -- models                          # list Ollama models
npm run codec -- index                           # index workspace for semantic search
npm run codec -- session list                    # list conversations
```

Or install globally: `npm link` then run `codec` from any directory.

**TUI**: Chat uses full-screen interactive TUI by default (OpenCode/Claude Code style). Use `--no-tui` for plain text:
- Status bar: model, mode, session, working directory
- Slash commands: /help, /models, /new, /continue, /session, /layout
- Keybinds: F1 (help), N (new), M (models), Q (quit)
- Dense layout: /layout for compact mode

## Run (development)

1. **Backend**: From project root, set `PYTHONPATH` to the backend folder and run uvicorn:
   ```bash
   cd backend
   pip install -r requirements.txt
   set PYTHONPATH=%cd%  # Windows
   python -m uvicorn server:app --host 127.0.0.1 --port 8765
   ```
2. **Electron**: From project root:
   ```bash
   npm install
   npx electron .
   ```
   The app starts the backend automatically when not packaged; workspace root defaults to the project directory.

## Build (bundle Electron + embedded Python)

The built app ships the backend in `resources/backend` and can bundle an embedded Python runtime in `resources/python`. When present, the app uses it to start the backend on launch (no system Python required).

**Windows – one-shot build with embedded Python:** Run `npm install` then `npm run build:full`. This runs `prepare-python` (downloads embeddable Python, enables site-packages, installs pip and backend deps) then `build`; the app in `dist/` will start the backend using the embedded runtime.

**Without embedded Python:** Run `npm run build`; an empty `python-runtime/` is created so the build succeeds and the packaged app will look for system Python (or use Choose Python on the splash).

## Environment (backend)

- `OLLAMA_BASE_URL` – Ollama API (default `http://localhost:11434`).
- `LLM_MODEL` – Chat model (default `gpt-oss:20b`).
- `EMBEDDING_MODEL` – Embeddings (default `nomic-embed-text`).
- `WORKSPACE_ROOT` – Workspace for file tools and chat DB (set by Electron when it spawns the backend).
- `AGENT_TIMEOUT_SEC`, `AGENT_MAX_STEPS` – Optional limits.
- `NUM_PREDICT` – Max tokens per response (0 = unlimited). Set e.g. 512 for faster replies.
- `NUM_CTX` – Ollama context window size in tokens (default 8192). Increase for longer conversations and more context.
- `TEMPERATURE` – Sampling temperature (default 0.1). Lower = more deterministic and accurate.
- `REPEAT_PENALTY` – Reduces repetition (default 1.1). Higher = less repetition, faster completion.
- `OLLAMA_KEEP_ALIVE` – How long to keep model loaded (default 10m). Reduces cold-start latency.

**Best models for coding:** Use a capable coding model in Ollama for best results, e.g. `codellama`, `deepseek-coder`, `qwen2.5-coder`, `llama3.2` (general), or `mistral`. MoE models (e.g. `qwen2.5-moe`, `mixtral`) decode faster for similar quality.

**Responsiveness:** For faster agent replies, use a MoE model. The agent uses file read caching, tuned prompts for fewer redundant steps, and streams Think→Action→Observe feedback.

- `MULTI_AGENT_ORCHESTRATOR_ENABLED` (default true) – For complex tasks, uses a planner to break work into subtasks and runs them (in parallel when independent). Disable to always use a single agent.
- `MODEL_CODER` – Model for coding tasks (default: `LLM_MODEL`). Used by multi-agent routing.
- `MODEL_PLANNER` – Model for complex/planning tasks (default: same as `MODEL_CODER`).
- `MODEL_VL` – Vision model for image/UI tasks (default: `qwen3-vl:8b`).

**Caching & performance:**
- `KV_WARM_ENABLED` (default true) – Warms Ollama's model as you type; when you press Enter, the model is preloaded.
- `VECTOR_CACHE_TTL` (default 300) – Seconds to cache semantic search results.
- `CACHE_DIR` – Override cache location (default: `%APPDATA%/ai-codec/cache` on Windows). Use an SSD or RAM disk for speed.
- `OLLAMA_DRAFT_MODEL` – For speculative decoding when Ollama adds support; reserve for future use.

## Features

- Chat with history; titles generated from first message.
- Agent tools: read_file, write_file, edit_file, delete_file, list_directory, shell_command, run_tests, grep_search, glob_search, web_search, search_context (semantic), git_status, git_diff.
- Inline diff and shell output in the UI.
- Index workspace for semantic search; switch Ollama model from the UI.
- **Project instructions**: Add `.codec-agent/project.md` or `.codec-agent/project.txt` in your workspace to provide persistent conventions, tech stack notes, and instructions the agent follows every session.
