# VenCoder Build & Setup Guide

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.10-3.13 | Python 3.14 NOT supported (ChromaDB incompatibility) |
| Node.js | 18+ | For Electron UI |
| Git | Any | For version control |
| Ollama | Latest | For local LLM (or use cloud providers) |

---

## Quick Start (5 minutes)

### 1. Clone & Setup

```bash
cd vencoder

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install Python dependencies
pip install -r backend/requirements.txt
```

### 2. Install Ollama & Pull Model

```bash
# Install Ollama (https://ollama.com)
# Then pull a coding model:
ollama pull codellama:13b
# Or: ollama pull deepseek-coder:6.7b
# Or: ollama pull qwen2.5-coder:14b
```

### 3. Verify Setup

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Test CLI
python -m backend.cli models
```

### 4. Run Interactive Chat

```bash
python -m backend.cli chat
```

---

## Full Setup Steps

### Step 1: Environment Variables

Create `.env` file in `backend/` directory:

```bash
# LLM Settings
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=codellama:13b
EMBEDDING_MODEL=nomic-embed-text

# Paths
WORKSPACE_ROOT=.
```

Or export in your shell:
```bash
export OLLAMA_BASE_URL=http://localhost:11434
export LLM_MODEL=codellama:13b
```

### Step 2: Install Backend Dependencies

```bash
cd backend
pip install -r requirements.txt

# Optional: For built-in GGUF models
pip install -r requirements-builtin.txt
```

### Step 3: Start Ollama (if not running)

```bash
# Start Ollama service
ollama serve

# In another terminal, pull a model
ollama pull codellama:13b
```

### Step 4: Run the Application

**Option A: CLI Chat**
```bash
cd backend
python -m backend.cli chat
```

**Option B: Run Single Prompt**
```bash
python -m backend.cli run "Fix the login bug"
```

**Option C: API Server**
```bash
python -m backend.cli serve
# Server runs at http://127.0.0.1:8765
```

### Step 5: Run Electron UI (Optional)

```bash
cd electron
npm install
npm start
```

---

## Project Structure

```
vencoder/
├── backend/              # Python backend
│   ├── cli.py           # CLI interface
│   ├── agent.py         # LangGraph + Ollama agent
│   ├── server.py        # FastAPI server with SSE
│   ├── tools/           # Agent tools (git, file, shell)
│   ├── memory.py        # Persistent memory
│   ├── checkpoint.py    # Undo/snapshots
│   ├── permissions.py   # Safety controls
│   ├── skills.py        # Automation skills
│   ├── hooks.py         # Event hooks
│   └── requirements.txt
├── electron/            # Electron UI
│   ├── index.html
│   ├── renderer.js
│   └── styles.css
└── vscode-extension/   # VS Code extension
```

---

## Common Commands

| Task | Command |
|------|---------|
| Interactive chat | `python -m backend.cli chat` |
| Single prompt | `python -m backend.cli run "task"` |
| Start API server | `python -m backend.cli serve` |
| List models | `python -m backend.cli models` |
| Show memory | `python -m backend.cli memory show` |
| List checkpoints | `python -m backend.cli checkpoint list` |
| Check permissions | `python -m backend.cli permissions show` |
| Git status | `python -m backend.cli git status` |
| List skills | `python -m backend.cli skills list` |
| List hooks | `python -m backend.cli hooks list` |

---

## Troubleshooting

### "No models available"
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Pull a model
ollama pull codellama:13b
```

### "Module not found"
```bash
# Reinstall dependencies
pip install -r backend/requirements.txt
```

### Server won't start
```bash
# Check port is free
netstat -ano | findstr 8765

# Try different port
python -m backend.cli serve --port 8080
```

### Import errors
```bash
# Ensure you're in the correct directory and venv is active
cd backend
..\venv\Scripts\activate
```

---

## Advanced Configuration

### Multiple LLM Models

```bash
# Use different models for different tasks
export MODEL_CODER=codellama:13b
export MODEL_PLANNER=deepseek-coder:6.7b
export MODEL_VL=qwen2.5-coder:14b
```

### Permission Modes

```bash
# Mode options: ask, auto_edit, plan, auto
python -m backend.cli permissions mode auto_edit
```

### Enable Multi-Agent Planning

```bash
export MULTI_AGENT_ORCHESTRATOR_ENABLED=true
```