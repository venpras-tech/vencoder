# VenCoder User Guide

A complete guide to running and using VenCoder, an AI-powered coding agent.

---

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [CLI Commands](#cli-commands)
4. [API Server](#api-server)
5. [Configuration](#configuration)
6. [Agent Modes](#agent-modes)
7. [Tools Reference](#tools-reference)
8. [Examples](#examples)

---

## Installation

### Prerequisites

- Python 3.10+
- Git
- (Optional) Ollama, LM Studio, or other LLM provider

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd vencoder

# Install dependencies
pip install -r requirements.txt

# For built-in models (GGUF support)
pip install -r requirements-builtin.txt
```

### LLM Provider Setup

**Option 1: Ollama (Recommended)**
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull codellama:13b
ollama pull deepseek-coder:6.7b
```

**Option 2: LM Studio**
- Download from https://lmstudio.ai
- Load a model

**Option 3: OpenAI/Anthropic**
```bash
export OPENAI_API_KEY=your-key-here
export ANTHROPIC_API_KEY=your-key-here
```

**Option 4: Built-in GGUF Models**
```bash
# Download models via API
curl -X POST http://localhost:8765/builtin/download \
  -H "Content-Type: application/json" \
  -d '{"repo_id": "TheBloke/Mistral-7B-v0.1-GGUF", "filename": "mistral-7b-v0.1.Q4_K_M.gguf"}'
```

---

## Quick Start

### Start Interactive Chat

```bash
# Navigate to your project
cd /path/to/your/project

# Start chat mode
python -m backend.cli chat

# Or use the shorthand
cd backend
python cli.py chat
```

### Run a Single Prompt

```bash
# One-off task
python -m backend.cli run "Fix the login bug in auth.py"

# With specific model
python -m backend.cli run "Write tests for user.py" --model codellama:13b
```

### Start API Server

```bash
# Start server on default port (8765)
python -m backend.cli serve

# Custom host and port
python -m backend.cli serve --host 0.0.0.0 --port 8080
```

---

## CLI Commands

### Command Structure

```bash
python -m backend.cli [global-options] <command> [command-options]
```

### Global Options

| Option | Description |
|--------|-------------|
| `--dir, -d` | Working directory (default: current directory) |
| `--model, -m` | Specify LLM model to use |
| `--mode` | Agent mode: `agent`, `ask`, or `plan` |

### Chat Mode

```bash
# Interactive chat (default)
python -m backend.cli chat

# Continue previous session
python -m backend.cli chat --continue
python -m backend.cli chat -c

# Continue specific session
python -m backend.cli chat --session 42

# With initial prompt
python -m backend.cli chat "Hello, help me with auth.py"

# Disable TUI (plain text)
python -m backend.cli chat --no-tui
```

### Run Mode (Single Prompt)

```bash
# One-off prompt
python -m backend.cli run "Fix the bug"

# Continue session
python -m backend.cli run --continue

# JSON output
python -m backend.cli run "Summarize this file" --format json

# Disable TUI
python -m backend.cli run "Refactor user.py" --no-tui
```

### Serve Mode (API Server)

```bash
# Default (127.0.0.1:8765)
python -m backend.cli serve

# Custom port
python -m backend.cli serve --port 8080

# Custom host
python -m backend.cli serve --host 0.0.0.0
```

### Models Command

```bash
# List available models
python -m backend.cli models
```

### Index Command

```bash
# Index workspace for semantic search
python -m backend.cli index
```

### Session Commands

```bash
# List all sessions
python -m backend.cli session list
```

### Memory Commands

```bash
# Show memory context
python -m backend.cli memory show

# Show memory statistics
python -m backend.cli memory stats

# Edit memory file
python -m backend.cli memory edit
```

### Checkpoint Commands

```bash
# List checkpoints
python -m backend.cli checkpoint list

# Undo last change
python -m backend.cli checkpoint undo

# Undo specific checkpoint
python -m backend.cli checkpoint undo-id abc123

# Show checkpoint stats
python -m backend.cli checkpoint stats

# Clear all checkpoints
python -m backend.cli checkpoint clear
```

### Permission Commands

```bash
# Show current permissions
python -m backend.cli permissions show

# Set permission mode
python -m backend.cli permissions mode ask
python -m backend.cli permissions mode auto_edit
python -m backend.cli permissions mode plan
python -m backend.cli permissions mode auto

# Cycle to next mode
python -m backend.cli permissions cycle

# Reset to defaults
python -m backend.cli permissions reset
```

### Git Commands

```bash
# Show status
python -m backend.cli git status

# Show branches
python -m backend.cli git branch

# Show commit log
python -m backend.cli git log

# Stash changes
python -m backend.cli git stash
python -m backend.cli git stash --message "WIP"

# Pop stash
python -m backend.cli git stash-pop
```

### Code Quality Commands

```bash
# Lint a file
python -m backend.cli lint check src/main.py

# Auto-fix lint issues
python -m backend.cli lint fix src/main.py

# Type check
python -m backend.cli typecheck src/main.py

# Security scan
python -m backend.cli security scan src/main.py

# Code review
python -m backend.cli review scan src/main.py

# Run all checks
python -m backend.cli checks all
python -m backend.cli checks all src/main.py
```

### Skills Commands

```bash
# List all skills
python -m backend.cli skills list

# List available skills (includes builtins)
python -m backend.cli skills available

# Show skill details
python -m backend.cli skills show lint-fix

# Create custom skill
python -m backend.cli skills create

# Edit a skill
python -m backend.cli skills edit lint-fix

# Delete custom skill
python -m backend.cli skills delete my-skill

# Run a skill directly
python -m backend.cli skills run lint-fix
```

### Hooks Commands

```bash
# List all hooks
python -m backend.cli hooks list

# List available hooks
python -m backend.cli hooks available

# Show hook details
python -m backend.cli hooks show pre-commit-lint

# Create custom hook
python -m backend.cli hooks create

# Edit a hook
python -m backend.cli hooks edit pre-commit-lint

# Delete hook
python -m backend.cli hooks delete my-hook

# Enable/disable hook
python -m backend.cli hooks enable pre-commit-lint
python -m backend.cli hooks disable pre-commit-lint
```

### Code Quality Tools (in Chat)

The agent also has code quality tools available:

| Tool | Description |
|------|-------------|
| `type_check_file` | Run type checker on a file |
| `type_check_project` | Type check entire project |
| `lint_file` | Run linter on a file |
| `lint_and_fix_file` | Auto-fix lint issues |
| `security_scan_file` | Scan file for security issues |
| `security_scan_project` | Scan project for security issues |
| `code_review_file` | Review file for code quality |
| `code_review_project` | Review entire project |
| `run_all_checks` | Run all quality checks |

---

## API Server

### Start Server

```bash
python -m backend.cli serve
```

Server runs at `http://127.0.0.1:8765`

### Health Check

```bash
curl http://localhost:8765/health
```

### Chat Endpoints

#### POST /chat
Stream chat responses.

```bash
curl -X POST http://localhost:8765/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Fix the login bug",
    "mode": "agent"
  }'
```

#### POST /chat/run
Non-streaming chat.

```bash
curl -X POST http://localhost:8765/chat/run \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Explain this code",
    "mode": "ask"
  }'
```

### Model Endpoints

```bash
# List models
curl http://localhost:8765/models

# Get current model
curl http://localhost:8765/model

# Set model
curl -X PATCH http://localhost:8765/model \
  -H "Content-Type: application/json" \
  -d '{"model": "codellama:13b"}'
```

### History Endpoints

```bash
# List conversations
curl http://localhost:8765/history

# Get conversation messages
curl http://localhost:8765/history/1

# Export conversation
curl "http://localhost:8765/history/export?ids=1&format=markdown"

# Delete conversations
curl -X DELETE http://localhost:8765/history \
  -H "Content-Type: application/json" \
  -d '{"ids": [1, 2]}'
```

### Memory Endpoints

```bash
# Get memory context
curl http://localhost:8765/memory

# Get raw memory content
curl http://localhost:8765/memory/content

# Update memory
curl -X POST http://localhost:8765/memory \
  -H "Content-Type: application/json" \
  -d '{"memory": "# Project Overview\n\nMy project..."}'

# Add auto-learning
curl -X POST "http://localhost:8765/memory/learn?category=structure&content=React app"
```

### Checkpoint Endpoints

```bash
# Create checkpoint
curl -X POST http://localhost:8765/checkpoint \
  -H "Content-Type: application/json" \
  -d '{"file_path": "src/main.py", "action": "edit"}'

# List checkpoints
curl http://localhost:8765/checkpoint

# Undo to checkpoint
curl -X POST "http://localhost:8765/checkpoint/undo?checkpoint_id=abc123"

# Undo last
curl -X POST http://localhost:8765/checkpoint/undo
```

### Permission Endpoints

```bash
# Get permissions
curl http://localhost:8765/permissions

# Set mode
curl -X POST http://localhost:8765/permissions/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "auto_edit"}'

# Cycle mode
curl -X POST http://localhost:8765/permissions/cycle

# Allow command
curl -X POST http://localhost:8765/permissions/allow \
  -H "Content-Type: application/json" \
  -d '{"command": "npm test"}'

# Validate command
curl "http://localhost:8765/permissions/validate/command?command=rm%20-rf"
```

### Git Endpoints

```bash
# Get branch info
curl http://localhost:8765/git/branch

# Get commit log
curl "http://localhost:8765/git/log?n=10"

# Commit
curl -X POST "http://localhost:8765/git/commit?message=Add%20feature"

# Create branch
curl -X POST "http://localhost:8765/git/create-branch?branch_name=feature/auth"

# Stash
curl -X POST http://localhost:8765/git/stash

# Push
curl -X POST http://localhost:8765/git/push

# Pull
curl -X POST http://localhost:8765/git/pull
```

### Skills Endpoints

```bash
# List all skills
curl http://localhost:8765/skills

# List available skills
curl http://localhost:8765/skills/available

# Get skill details
curl http://localhost:8765/skills/lint-fix

# Create skill
curl -X POST http://localhost:8765/skills \
  -H "Content-Type: application/json" \
  -d '{"name": "my-skill", "description": "My custom skill", "command": "echo hello"}'

# Update skill
curl -X PUT http://localhost:8765/skills/my-skill \
  -H "Content-Type: application/json" \
  -d '{"command": "echo hello world"}'

# Delete skill
curl -X DELETE http://localhost:8765/skills/my-skill

# Run skill
curl -X POST http://localhost:8765/skills/lint-fix/run
```

### Hooks Endpoints

```bash
# List all hooks
curl http://localhost:8765/hooks

# List available hooks
curl http://localhost:8765/hooks/available

# Get hook details
curl http://localhost:8765/hooks/pre-commit-lint

# Create hook
curl -X POST http://localhost:8765/hooks \
  -H "Content-Type: application/json" \
  -d '{"name": "my-hook", "description": "My hook", "command": "echo hello"}'

# Update hook
curl -X PUT http://localhost:8765/hooks/my-hook \
  -H "Content-Type: application/json" \
  -d '{"command": "echo hello world"}'

# Delete hook
curl -X DELETE http://localhost:8765/hooks/my-hook

# Enable hook
curl -X POST http://localhost:8765/hooks/my-hook/enable

# Disable hook
curl -X POST http://localhost:8765/hooks/my-hook/disable
```

### File Endpoints

```bash
# Get file tree
curl http://localhost:8765/files/tree

# Get file content
curl "http://localhost:8765/files/content?path=README.md"

# Index workspace
curl -X POST http://localhost:8765/index
```

### Settings Endpoints

```bash
# Get all settings
curl http://localhost:8765/settings

# Update settings
curl -X POST http://localhost:8765/settings \
  -H "Content-Type: application/json" \
  -d '{"settings": {"theme": "dark"}}'

# Get LLM settings
curl http://localhost:8765/settings/llm
```

### Other Endpoints

```bash
# Check Ollama/LM Studio status
curl http://localhost:8765/probe/available

# Cancel shell command
curl -X POST http://localhost:8765/cancel-shell

# Cancel chat
curl -X POST http://localhost:8765/cancel-chat

# Warm cache
curl -X POST http://localhost:8765/warm

# Get logs
curl http://localhost:8765/logs

# Shutdown server
curl -X POST http://localhost:8765/shutdown
```

---

## Configuration

### Environment Variables

```bash
# LLM Provider
LLM_PROVIDER=ollama          # ollama, lmstudio, builtin, openai, anthropic, google
LLM_MODEL=codellama:13b

# Provider URLs
OLLAMA_BASE_URL=http://localhost:11434
LM_STUDIO_BASE_URL=http://localhost:1234
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=your-key
ANTHROPIC_API_KEY=your-key

# Paths
WORKSPACE_ROOT=.             # Project directory
BUILTIN_MODELS_DIR=./models # GGUF models directory

# Model Settings
NUM_CTX=8192                 # Context window size
TEMPERATURE=0.1
REPEAT_PENALTY=1.1
OLLAMA_KEEP_ALIVE=10m

# Embeddings
EMBEDDING_MODEL=nomic-embed-text
CHROMA_PERSIST_DIR=./chroma_data

# Agent Settings
AGENT_TIMEOUT_SEC=1800
AGENT_MAX_STEPS=0            # 0 = unlimited
STEP_TIMEOUT_SEC=1200
MAX_HISTORY_MESSAGES=20
```

### Permission Configuration

File: `.vencoder/permissions.json`

```json
{
  "permission_mode": "ask",
  "allowed_commands": ["npm test", "pytest", "make test"],
  "denied_commands": [],
  "allowed_paths": [],
  "denied_paths": [],
  "auto_memory_enabled": true
}
```

---

## Agent Modes

### Agent Mode (Default)

Full coding capabilities with all tools.

```
python -m backend.cli chat --mode agent
python -m backend.cli run "Refactor the entire auth module" --mode agent
```

**Available tools:**
- File operations (read, write, edit, delete)
- Shell command execution
- Test running
- Git operations
- Web search
- Semantic search

### Ask Mode (Read-only)

For questions and explanations without modifications.

```
python -m backend.cli chat --mode ask
python -m backend.cli run "Explain how this function works" --mode ask
```

**Available tools:**
- File reading
- Search tools
- Git status/diff (read-only)
- Web search

### Plan Mode

Creates execution plans without executing.

```
python -m backend.cli chat --mode plan
python -m backend.cli run "Plan a refactor of the codebase" --mode plan
```

**Available tools:**
- File reading
- Search tools
- Git status/diff (read-only)
- Save plans

---

## Tools Reference

### File Tools

| Tool | Description |
|------|-------------|
| `read_file(path)` | Read file content |
| `write_file(path, content)` | Write file |
| `edit_file(path, old_string, new_string)` | Edit file |
| `delete_file(path)` | Delete file |
| `save_plan(content, title)` | Save markdown plan |
| `list_directory(path)` | List directory |

### Shell Tools

| Tool | Description |
|------|-------------|
| `shell_command(command, timeout_seconds)` | Execute shell command |
| `run_tests(command, timeout_seconds)` | Run tests |

### Search Tools

| Tool | Description |
|------|-------------|
| `grep_search(pattern, path, recursive)` | Regex search in files |
| `glob_search(pattern, path)` | Find files by pattern |
| `web_search(query, max_results)` | Search web |
| `scrape_url(url, max_chars)` | Fetch webpage |
| `search_context(query, k)` | Semantic search |

### Git Tools

| Tool | Description |
|------|-------------|
| `git_status()` | Show status |
| `git_diff(ref)` | Show diff |
| `git_branch()` | List branches |
| `git_log(n, file_path)` | Show commits |
| `git_show(commit_ref)` | Show commit |
| `git_stash(message)` | Stash changes |
| `git_stash_pop()` | Pop stash |
| `git_create_branch(branch, base)` | Create branch |
| `git_switch_branch(branch)` | Switch branch |
| `git_commit(message, amend)` | Commit |
| `git_commit_all(message, amend)` | Commit all |
| `git_add(files)` | Stage files |
| `git_reset(file, soft)` | Reset |
| `git_revert(commit)` | Revert |
| `git_merge(branch)` | Merge |
| `git_rebase(branch)` | Rebase |
| `git_fetch(all)` | Fetch |
| `git_pull(rebase)` | Pull |
| `git_push(force, upstream)` | Push |
| `git_blame(file, n)` | Blame |
| `git_grep(pattern)` | Search history |
| `git_diff_staged(ref)` | Staged diff |
| `git_undo_last_commit(keep)` | Undo commit |
| `git_clean(dry_run, dirs)` | Clean |
| `git_remote()` | Remotes |
| `git_current_branch()` | Current branch |
| `git_tag(name, msg)` | Create tag |
| `git_list_tags(pattern)` | List tags |
| `git_short_status()` | Compact status |
| `git_changed_files(ref1, ref2)` | Changed files |

---

## Examples

### Example 1: Fix a Bug

```bash
cd my-project
python -m backend.cli chat

# In chat:
> There's a bug in user.py line 42 where it crashes on empty input
```

### Example 2: Add New Feature

```bash
python -m backend.cli run "Add OAuth2 login support to the auth module"
```

### Example 3: Refactor Code

```bash
# Create checkpoint first
python -m backend.cli checkpoint list

# Ask for refactor
python -m backend.cli run "Refactor the database layer to use async"

# If unhappy, restore
python -m backend.cli checkpoint undo
```

### Example 4: Run Tests

```bash
python -m backend.cli run "Run the test suite and fix any failures"
```

### Example 5: Code Review

```bash
python -m backend.cli chat --mode ask

> Review src/auth.py for security issues
```

### Example 6: Plan Feature

```bash
python -m backend.cli chat --mode plan

> Create a plan to add user roles and permissions
```

### Example 7: Git Workflow

```bash
# Create feature branch
python -m backend.cli run "Create a new branch called feature/payments"

# Make changes
python -m backend.cli run "Add payment processing logic"

# Commit
python -m backend.cli run "Commit these changes"

# Push
python -m backend.cli run "Push to origin"
```

### Example 8: Search Codebase

```bash
python -m backend.cli run "Find all places where we connect to the database"
```

### Example 9: Add Project Context

```bash
# Edit memory
python -m backend.cli memory edit

# Add content:
# # Project Overview
# This is a Python Flask REST API
# We use SQLAlchemy for ORM
# Testing with pytest
```

### Example 10: Set Permissions

```bash
# Allow test commands
python -m backend.cli permissions mode auto_edit

# Now agent can edit files but asks for shell commands
```

---

## Troubleshooting

### No Models Available

```bash
# Check Ollama status
curl http://localhost:11434/api/tags

# Pull a model
ollama pull codellama:13b

# Or use built-in GGUF
python -m backend.cli models
```

### Chat Hangs

```bash
# Cancel current chat
curl -X POST http://localhost:8765/cancel-chat

# Check logs
curl http://localhost:8765/logs
```

### Permission Denied

```bash
# Check current permissions
python -m backend.cli permissions show

# Reset if needed
python -m backend.cli permissions reset
```

### Clear All Checkpoints

```bash
python -m backend.cli checkpoint clear
```

---

## Keyboard Shortcuts (TUI)

| Shortcut | Action |
|----------|--------|
| `Ctrl+C` | Cancel current operation |
| `Ctrl+D` | Exit chat |
| `/quit` | Exit chat |
| `/help` | Show help |
| `/continue` | Continue session |
| `/session` | List sessions |

---

## Getting Help

```bash
# Show all commands
python -m backend.cli --help

# Show command help
python -m backend.cli chat --help
python -m backend.cli serve --help
python -m backend.cli memory --help
```
