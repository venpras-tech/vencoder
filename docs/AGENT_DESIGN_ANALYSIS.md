# Coding Agent Design Analysis & Improvement Plan

Analysis of the vencoder coding agent against current best practices and recommended optimizations.

---

## Current Architecture Summary

- **Pattern**: ReAct (Reason + Act) via LangGraph `create_react_agent`
- **LLM**: Ollama (ChatOllama), temperature 0.2
- **Tools**: 8 tools (read_file, write_file, edit_file, delete_file, shell_command, grep_search, glob_search, search_context)
- **State**: Stateless per request; conversation stored in SQLite but not passed to agent

---

## Critical Issues

### 1. Conversation History Not Passed to Agent
**Impact**: Agent has no context from prior messages. Follow-up questions like "fix the bug in that function" fail.

**Current**: `stream_agent_events_with_history` loads history into DB but only passes the current message to the agent.

**Fix**: Load `get_messages(conv_id)` and convert to LangChain message format. Pass last N messages (with token budget) as agent input.

---

### 2. `run()` Function Never Parses Stream Output
**Impact**: `/chat/run` returns empty content and tool_calls.

**Current**: `consume()` checks `line.startswith("data: ")` but `stream_events` yields plain JSON lines.

**Fix**: Parse JSON directly: `data = json.loads(line.strip())`.

---

### 3. Step Timeout Logic
**Impact**: Per-step timeout equals full agent timeout (600s). A single slow step can exhaust the entire budget.

**Current**: `_step_timeout_for_run()` returns `AGENT_TIMEOUT_SEC` for each step.

**Fix**: Add `STEP_TIMEOUT_SEC` (e.g. 60s) separate from `AGENT_TIMEOUT_SEC` (600s).

---

### 4. No Retry Logic
**Impact**: Transient failures (Ollama timeout, network blip, ChromaDB) cause immediate failure.

**Fix**: Add retries with exponential backoff for:
- LLM calls (via LangChain retry)
- Vector store queries in `search_context`
- Optional: tool-level retries for idempotent operations

---

### 5. No Loop / Duplicate Call Detection
**Impact**: Agent can repeatedly call the same tool with same args (e.g. read same file 10x), wasting tokens and time.

**Fix**: Track recent (tool, args_hash) and inject a warning into observation when duplicate detected, or cap consecutive identical calls.

---

## High-Priority Improvements

### 6. Prompt Enhancements
- Add tool-specific guidance (when to use search_context vs grep_search)
- Add few-shot example for the Plan→Action→Observe loop
- Add explicit "use search_context before editing unfamiliar codebases"

### 7. `edit_file` Multi-Occurrence
**Current**: Replaces only first occurrence.

**Fix**: Add optional `replace_all: bool = False` parameter.

### 8. Semantic Search Robustness
- Wrap `query_index` in try/except; return helpful message on failure
- Consider chunking large files instead of whole-file documents
- Add incremental indexing (optional, larger effort)

### 9. Structured Error Handling
- Define error types (ToolError, TimeoutError, etc.)
- Include path/context in error messages for debugging

---

## Design Pattern Considerations

### ReAct vs Plan-and-Execute
**Current**: Pure ReAct. Good for flexibility; can be myopic on complex multi-file tasks.

**Option**: Hybrid—add optional "plan first" mode where agent outputs a step list before executing. Useful for large refactors. Lower priority.

### Guardrails (Production Best Practices)
- **Max tool calls per run**: Already have `AGENT_MAX_STEPS`; ensure it's enforced (it is).
- **Cost control**: N/A for local Ollama.
- **Observability**: Add structured logging for tool calls (name, args summary, duration).

---

## Implementation Priority

| Priority | Item | Effort | Status |
|----------|------|--------|--------|
| P0 | Fix `run()` stream parsing | Small | Done |
| P0 | Pass conversation history to agent | Medium | Done |
| P0 | Separate step timeout from agent timeout | Small | Done |
| P1 | Add retry for LLM (LangChain) | Small | Done |
| P1 | Improve prompt (tool guidance) | Small | Done |
| P1 | `edit_file` replace_all option | Small | Done |
| P2 | Loop/duplicate call detection | Medium | Deferred |
| P2 | search_context error handling | Small | Done |
| P2 | Retry for search_context | Small | Deferred |

## Implemented Changes

- **config.py**: Added `STEP_TIMEOUT_SEC` (120s), `MAX_HISTORY_MESSAGES` (20)
- **agent_harness.py**: History support, step timeout fix, run() JSON parsing fix
- **agent.py**: LLM retry with `with_retry(stop_after_attempt=3)`
- **server.py**: Pass conversation history to agent for both `/chat` and `/chat/run`
- **prompts.py**: Tool selection guidance (when to use search_context vs grep vs glob)
- **file_tools.py**: `edit_file` now has `replace_all` parameter
- **context_tools.py**: Try/except around search_context with helpful error message
