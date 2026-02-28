# AI Codec

Electron desktop app with an AI coding agent (LangGraph + Ollama), semantic code search (ChromaDB + Ollama embeddings), and file/shell tools.

## Structure

- `backend/` – Python: config, tools, agent (LangGraph + Ollama), semantic_index (ChromaDB + Ollama embeddings), FastAPI server with SSE.
- `electron/` – Electron main process, preload, renderer (chat UI, diff/shell blocks), styles.

## Requirements

- **Python 3.10–3.13** (Python 3.14 is not supported; ChromaDB has compatibility issues)
- Node.js for Electron
- Ollama for the LLM

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

## Features

- Chat with history; titles generated from first message.
- Agent tools: read_file, write_file, edit_file, delete_file, shell_command, grep_search, glob_search, search_context (semantic).
- Inline diff and shell output in the UI.
- Index workspace for semantic search; switch Ollama model from the UI.
