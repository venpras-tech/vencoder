# VenCoder - New Features Guide

## Phase 1 Features (Implemented)

This document describes the new features added to VenCoder based on competitive analysis with Claude Code, Aider, and other AI coding agents.

---

## Memory System

VenCoder now has a persistent memory system similar to Claude Code's CLAUDE.md.

### How It Works

Memory is stored in the `.vencoder/` directory:

- `.vencoder/memory.md` - User-defined project context
- `.vencoder/conventions.md` - Coding conventions and patterns
- `.vencoder/auto_memory.json` - Auto-learned information
- `.vencoder/settings.json` - Configuration settings

### Usage

**CLI Commands:**
```bash
# Show memory context
codec memory show

# Show memory statistics
codec memory stats

# Edit memory file
codec memory edit
```

**API Endpoints:**
```
GET /memory          - Get memory context and stats
GET /memory/content  - Get raw memory content
POST /memory         - Update memory
POST /memory/learn   - Add auto-learning entry
```

### Memory Files

#### `.vencoder/memory.md`
```markdown
# Memory

# Project Overview
[Describe your project here]

# Current Task Focus
[What you're currently working on]
```

#### `.vencoder/conventions.md`
```markdown
# Coding Conventions

# Project Structure

# API Patterns

# Testing Approach
```

---

## Checkpoint / Undo System

VenCoder now creates automatic checkpoints before file modifications, enabling safe undo functionality.

### How It Works

- Checkpoints are stored in `.vencoder/checkpoints/`
- Each checkpoint contains a snapshot of the file before modification
- Checkpoints are session-scoped (independent of git)
- Up to 50 checkpoints per session

### Usage

**CLI Commands:**
```bash
# List all checkpoints
codec checkpoint list

# Undo last modification
codec checkpoint undo

# Undo to specific checkpoint
codec checkpoint undo-id <checkpoint_id>

# Show checkpoint statistics
codec checkpoint stats

# Clear all checkpoints
codec checkpoint clear
```

**API Endpoints:**
```
POST /checkpoint              - Create checkpoint
POST /checkpoint/undo        - Undo to checkpoint
GET  /checkpoint             - List checkpoints
GET  /checkpoint/{id}        - Get checkpoint details
POST /checkpoint/session/{id} - Set session
DELETE /checkpoint/session    - Clear session
```

---

## Permission Modes

VenCoder now supports granular permission control for safety.

### Modes

| Mode | Description |
|------|-------------|
| `ask` | Ask before file edits and shell commands (default) |
| `auto_edit` | Auto-edit files, ask for commands |
| `plan` | Read-only mode, creates plans only |
| `auto` | Full autonomy with safety checks |

### Usage

**CLI Commands:**
```bash
# Show current permissions
codec permissions show

# Set permission mode
codec permissions mode ask
codec permissions mode auto_edit
codec permissions mode plan
codec permissions mode auto

# Cycle to next mode
codec permissions cycle

# Reset to defaults
codec permissions reset
```

**API Endpoints:**
```
GET  /permissions         - Get permission settings
POST /permissions/mode    - Set permission mode
POST /permissions/cycle  - Cycle mode
POST /permissions/reset  - Reset to defaults
POST /permissions/allow  - Allow a command
POST /permissions/deny   - Deny a command
```

### Safety Features

- **Dangerous command detection** - Warns about `rm -rf /`, fork bombs, etc.
- **Command allowlisting** - Allow specific commands like `npm test`
- **Path restrictions** - Prevent access to sensitive directories

---

## Enhanced Git Integration

VenCoder now has comprehensive git operations beyond basic status and diff.

### Usage

**CLI Commands:**
```bash
# Git operations
codec git status        # Show status
codec git branch        # Show branches
codec git log           # Show commit log
codec git stash         # Stash changes
codec git stash-pop     # Pop stash
```

**Agent Tools (available in agent mode):**

| Tool | Description |
|------|-------------|
| `git_status` | Show git status |
| `git_diff` | Show diff |
| `git_branch` | List branches |
| `git_log` | Show commit history |
| `git_show` | Show commit details |
| `git_stash` | Stash changes |
| `git_stash_pop` | Apply stash |
| `git_create_branch` | Create branch |
| `git_switch_branch` | Switch branch |
| `git_delete_branch` | Delete branch |
| `git_commit` | Commit staged changes |
| `git_commit_all` | Commit all changes |
| `git_add` | Stage files |
| `git_reset` | Unstage files |
| `git_revert` | Revert commit |
| `git_merge` | Merge branch |
| `git_rebase` | Rebase branch |
| `git_fetch` | Fetch from remote |
| `git_pull` | Pull from remote |
| `git_push` | Push to remote |
| `git_blame` | Show blame |
| `git_grep` | Search in git history |
| `git_diff_staged` | Show staged diff |
| `git_undo_last_commit` | Undo last commit |
| `git_clean` | Remove untracked files |
| `git_remote` | Show remotes |
| `git_current_branch` | Get current branch |
| `git_tag` | Create tag |
| `git_list_tags` | List tags |
| `git_short_status` | Compact status |
| `git_changed_files` | List changed files |

**API Endpoints:**
```
GET  /git/branch         - Get current branch
GET  /git/log            - Get commit log
POST /git/commit         - Commit changes
POST /git/commit-all     - Commit all
POST /git/create-branch  - Create branch
POST /git/switch-branch  - Switch branch
POST /git/stash          - Stash changes
POST /git/stash-pop      - Pop stash
POST /git/undo-commit    - Undo last commit
POST /git/push           - Push to remote
POST /git/pull           - Pull from remote
GET  /git/short-status   - Compact status
GET  /git/changed-files  - List changed files
```

---

## Phase 3: Workflow Automation

### Skills System

Skills are custom automation tasks that can be triggered by natural language.

#### How It Works

Skills are defined in YAML files in the `.vencoder/skills/` directory:
- `builtin_skills.json` - Pre-built skills installed by default
- `.vencoder/skills/*.yaml` - Custom user skills

#### Pre-built Skills

| Skill | Description | Triggers |
|-------|-------------|----------|
| `lint-fix` | Run linter and auto-fix | "lint and fix", "fix lint issues" |
| `commit` | Smart commit with conventional format | "commit changes", "commit my work" |
| `security-scan` | Run security analysis | "security scan", "check for vulnerabilities" |
| `typecheck` | Run type checker | "type check", "check types" |
| `test-all` | Run full test suite | "run all tests", "test everything" |
| `git-status` | Show git status | "git status", "show changes" |
| `git-log` | Show commit history | "show log", "recent commits" |
| `create-branch` | Create new branch | "create branch", "new branch" |
| `deploy-staging` | Deploy to staging | "deploy to staging", "push to staging" |
| `changelog` | Generate changelog | "generate changelog", "what changed" |
| `review-pr` | Review pull request | "review PR", "review pull request" |
| `backup` | Backup project | "backup project", "create backup" |
| `cleanup` | Clean up artifacts | "cleanup", "clean up artifacts" |
| `analyze-complexity` | Analyze code complexity | "analyze complexity", "code complexity" |

#### Usage

**CLI Commands:**
```bash
# List all skills
codec skills list

# List available skills (includes builtins)
codec skills available

# Show skill details
codec skills show lint-fix

# Create custom skill
codec skills create

# Edit a skill
codec skills edit lint-fix

# Delete custom skill
codec skills delete my-skill

# Run a skill directly
codec skills run lint-fix
```

**API Endpoints:**
```
GET  /skills           - List all skills
GET  /skills/available - List available skills
GET  /skills/{name}    - Get skill details
POST /skills           - Create skill
PUT  /skills/{name}    - Update skill
DELETE /skills/{name}  - Delete skill
POST /skills/{name}/run - Execute skill
```

#### Custom Skill Example

```yaml
# .vencoder/skills/deploy-production.yaml
name: "deploy-production"
description: "Deploy application to production environment"
triggers:
  - "deploy to production"
  - "deploy production"
  - "push to prod"
command: "./scripts/deploy.sh production"
working_dir: "{{project_root}}"
environment:
  DEPLOY_ENV: "production"
```

#### Variable Substitution

Skills support template variables:
- `{{project_root}}` - Project root directory
- `{{file}}` - Currently selected file
- `{{files}}` - Selected files (space-separated)
- `{{branch}}` - Current git branch

---

### Hooks System

Hooks run automatically before or after certain events.

#### How It Works

Hooks are defined in `.vencoder/hooks/`:
- `builtin_hooks.json` - Pre-built hook templates
- `.vencoder/hooks/*.yaml` - Custom hooks

#### Pre-built Hook Templates

| Hook | Event | Description |
|------|-------|-------------|
| `pre-commit-lint` | before:git-commit | Run linter before commits |
| `pre-commit-typecheck` | before:git-commit | Type check before commits |
| `pre-push-test` | before:git-push | Run tests before push |
| `post-edit-format` | after:file-edit | Auto-format after edits |
| `pre-command-confirm` | before:shell-command | Confirm destructive commands |

#### Usage

**CLI Commands:**
```bash
# List all hooks
codec hooks list

# List available hooks
codec hooks available

# Show hook details
codec hooks show pre-commit-lint

# Create custom hook
codec hooks create

# Edit a hook
codec hooks edit pre-commit-lint

# Delete hook
codec hooks delete my-hook

# Enable/disable hook
codec hooks enable pre-commit-lint
codec hooks disable pre-commit-lint
```

**API Endpoints:**
```
GET  /hooks              - List all hooks
GET  /hooks/available    - List available hooks
GET  /hooks/{name}       - Get hook details
POST /hooks              - Create hook
PUT  /hooks/{name}       - Update hook
DELETE /hooks/{name}     - Delete hook
POST /hooks/{name}/enable  - Enable hook
POST /hooks/{name}/disable - Disable hook
```

#### Custom Hook Example

```yaml
# .vencoder/hooks/pre-push-tests.yaml
name: "pre-push-tests"
description: "Run tests before git push"
command: "npm test"
on:
  - before: "git push"
condition:
  files_matched: "*.ts"
continue_on_error: false
```

#### Hook Events

| Event | Description |
|-------|-------------|
| `before:git-commit` | Before git commit |
| `after:git-commit` | After git commit |
| `before:git-push` | Before git push |
| `after:git-push` | After git push |
| `before:file-edit` | Before file edit |
| `after:file-edit` | After file edit |
| `before:shell-command` | Before shell command |
| `after:shell-command` | After shell command |
| `on:session-start` | On session start |
| `on:session-end` | On session end |

---

## Phase 2: Code Intelligence

### Type Checking

Run type checkers to catch errors before runtime.

**Supported Languages:**
- Python (mypy)
- TypeScript/JavaScript (tsc, eslint)
- Rust (cargo check)
- Go (go vet)
- Java (javac)

**CLI:**
```bash
# Type check a file
python -m backend.cli typecheck src/main.py

# Type check project
python -m backend.cli typecheck
```

**In Chat:**
```
> Run type check on auth.py
> Type check the entire project
```

---

### Auto Lint Fix

Automatically fix code style issues.

**Supported:**
- Python (ruff, flake8, pylint)
- JavaScript/TypeScript (eslint, prettier)
- Rust (clippy, rustfmt)
- Go (gofmt, golangci-lint)
- CSS (stylelint)

**CLI:**
```bash
# Check lint issues
python -m backend.cli lint check src/main.py

# Auto-fix issues
python -m backend.cli lint fix src/main.py

# Fix entire project
python -m backend.cli lint fix-project
```

**In Chat:**
```
> Run linter on this file
> Auto-fix the lint issues
```

---

### Security Scanner

Scan for security vulnerabilities.

**Detects:**
- Hardcoded credentials (passwords, API keys, tokens)
- SQL injection
- Command injection
- XSS vulnerabilities
- Path traversal
- Insecure cryptography (MD5, SHA1)
- Unsafe deserialization (pickle, yaml)
- SSRF
- XXE

**CLI:**
```bash
# Scan a file
python -m backend.cli security scan src/auth.py

# Scan entire project
python -m backend.cli security scan
```

**In Chat:**
```
> Scan for security issues in this file
> Run a security scan on the project
```

---

### Code Review

Automated code quality review.

**Checks:**
- Error handling
- Code quality
- Performance
- Security
- Maintainability
- Testing
- Documentation
- Design patterns

**CLI:**
```bash
# Review a file
python -m backend.cli review scan src/main.py

# Review entire project
python -m backend.cli review scan
```

**In Chat:**
```
> Review this code for quality issues
> Code review the entire project
```

---

### Run All Checks

Comprehensive code quality analysis.

```bash
# Run all checks on project
python -m backend.cli checks all

# Run all checks on file
python -m backend.cli checks all src/main.py
```

**In Chat:**
```
> Run all quality checks
> Check this file for type errors, lint issues, and security problems
```

---

## Configuration Files

### `.vencoder/permissions.json`
```json
{
  "permission_mode": "ask",
  "allowed_commands": ["npm test", "pytest"],
  "denied_commands": [],
  "allowed_paths": [],
  "denied_paths": [],
  "auto_memory_enabled": true
}
```

---

## Example Workflows

### Memory-Assisted Development

1. Create project context:
   ```bash
   codec memory edit
   ```
   Add project overview and conventions.

2. Start coding:
   ```bash
   codec chat
   > Implement user authentication
   ```

3. VenCoder remembers your project structure and conventions.

### Safe Experimentation

1. Make changes:
   ```
   > Refactor the auth module
   ```

2. If something goes wrong:
   ```bash
   codec checkpoint undo
   ```

3. File restored to previous state.

### Git Workflow

1. Create feature branch:
   ```
   > Create a new branch called feature/oauth
   ```

2. Make changes and commit:
   ```
   > Commit these changes with a good message
   ```

3. Push when ready:
   ```
   > Push to origin
   ```

---

## Phase 4: UX Enhancements

### Enhanced TUI

Rich terminal UI with advanced features.

**Diff View:**
```python
from backend.enhanced_tui import compute_diff, print_diff

diff = compute_diff(old_code, new_code)
print_diff(diff)
```

**Error Formatting:**
```python
from backend.enhanced_tui import FormattedError, print_formatted_error

error = FormattedError(
    category=ErrorCategory.SECURITY,
    message="Hardcoded password detected",
    file_path="auth.py",
    line_number=42,
    suggestion="Use environment variables instead"
)
print_formatted_error(error)
```

**Progress Indicators:**
```python
from backend.enhanced_tui import ProgressTracker

tracker = ProgressTracker(total=100)
task = tracker.add_task("my-task", "Processing files")
task.advance(50)
task.complete()
```

---

### Session Management

Enhanced session handling with fork, export, import, and tagging.

**CLI Commands:**
```bash
# Fork a session
python -m backend.cli session fork <session_id>

# Export session
python -m backend.cli session export <session_id> --format markdown

# Import session
python -m backend.cli session import session.md

# Tag a session
python -m backend.cli session tag <session_id> <tag>

# Search sessions
python -m backend.cli session search "query"
```

---

## Phase 5: Extensibility

### Plugin System

Extend VenCoder with custom plugins.

**CLI Commands:**
```bash
# List plugins
python -m backend.cli plugin list

# Enable/disable plugin
python -m backend.cli plugin enable my-plugin
python -m backend.cli plugin disable my-plugin

# Create new plugin
python -m backend.cli plugin create my-plugin
```

**Plugin Example:**
```python
from vencoder.plugins import Plugin, PluginHook, HookResult

class MyPlugin(Plugin):
    name = "my_plugin"
    hooks = [PluginHook.ON_MESSAGE, PluginHook.ON_TOOL_CALL]
    
    async def on_message(self, message: str) -> HookResult:
        # Process message
        return HookResult()
```

---

### External API

REST API for external integrations.

**Endpoints:**
```
GET  /api/health          - Health check
GET  /api/tools          - List external tools
POST /api/execute        - Execute command
POST /api/query          - Query agent
```

**Authentication:**
```bash
# Create API key
curl -X POST http://localhost:8765/api/keys \
  -d '{"name": "my-app"}'

# Use API key
curl -H "Authorization: Bearer <key>" \
  http://localhost:8765/api/execute
```

---

### VS Code Extension

Full VS Code integration with chat panel and collaboration.

**Features:**
- `/explain`, `/refactor`, `/fix`, `/test` commands
- Inline code actions
- Real-time collaboration
- Streaming responses
- Diff viewer

**Keybindings:**
- `Ctrl+Shift+V` - Open VenCoder chat
- `Ctrl+Shift+E` - Explain code
- `Ctrl+Shift+R` - Refactor code
- `Ctrl+Shift+F` - Fix code

---

### Real-time Collaboration

Work together with your team in real-time.

**Features:**
- Share cursor positions
- See selections
- Chat alongside code
- File edit sync
- Room management

**CLI Commands:**
```bash
# Start collaboration server
python -m backend.cli collab serve

# Create room
python -m backend.cli collab create "My Room"

# Join room
python -m backend.cli collab join <room_id>
```

---

## All Implemented Features

| Category | Feature | Status |
|----------|---------|--------|
| Memory | Persistent memory | ✅ |
| Safety | Checkpoints/undo | ✅ |
| Safety | Permission modes | ✅ |
| Git | Enhanced git workflow | ✅ |
| Intelligence | Type checking | ✅ |
| Intelligence | Auto lint fix | ✅ |
| Intelligence | Security scanner | ✅ |
| Intelligence | Code review | ✅ |
| Workflow | Skills system | ✅ |
| Workflow | Hooks system | ✅ |
| UX | Enhanced TUI | ✅ |
| UX | Session management | ✅ |
| Extensibility | Plugin system | ✅ |
| Extensibility | External API | ✅ |
| Extensibility | VS Code extension | ✅ |
| Collaboration | Real-time collab | ✅ |
