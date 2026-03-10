# Run Instructions

## Quick start

1. **Backend**
   ```powershell
   cd backend
   pip install -r requirements.txt
   $env:PYTHONPATH = (Get-Location).Path
   python -m uvicorn server:app --host 127.0.0.1 --port 8765
   ```

2. **UI** (new terminal)
   ```bash
   npm install
   npx electron .
   ```

3. **First chat** – With Ollama: ensure a model is pulled (`ollama pull gpt-oss:20b`). With Built-in: add GGUF files to the models folder.

## No paid APIs

This app uses **only open-source models**:

- **Ollama**: Local models via Ollama. No API key.
- **Built-in**: Local GGUF models via llama.cpp. No API key. Add `.gguf` files to the models folder.
- **Embeddings**: Local (Ollama). No API key.
- **Web search**: DuckDuckGo (free, no API key).

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `ollama` | `ollama` or `builtin` |
| `LLM_MODEL` | `gpt-oss:20b` | Ollama model name or Built-in GGUF filename (stem) |
| `BUILTIN_MODELS_DIR` | `%APPDATA%\ai-codec\models` (Win) | Folder for GGUF files when using Built-in |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API (when using Ollama) |

## Switch to Built-in

1. Create the models folder (e.g. `%APPDATA%\ai-codec\models` on Windows).
2. Download a GGUF model and place it in that folder.
3. Set `LLM_PROVIDER=builtin` and `LLM_MODEL=<filename-without-.gguf>`.
4. Or use the app UI: click the model name → Provider: Built-in → select your model → Save.
