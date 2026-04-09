# VenCoder Backend Documentation

## Overview
VenCoder is an AI-powered coding assistant with a Python FastAPI backend and Electron frontend. The backend provides a REST API for an AI coding assistant that can explore codebases, edit files, run commands, and execute tasks using LLM agents.

---

## Directory Structure

```
backend/
├── server.py              # Main FastAPI server
├── agent.py              # Agent builder
├── orchestrator.py       # Multi-agent task orchestration
├── multi_agent.py        # Multi-model routing
├── agent_harness.py      # Agent execution harness
├── visual_agents.py      # Vision/image processing agents
├── config.py             # Configuration management
├── llm_builder.py        # LLM provider builder
├── prompts.py            # System prompts for agents
├── context_builders.py   # Context builders for prompts
├── semantic_index.py     # Vector store for semantic search
├── chat_db.py            # SQLite chat history database
├── settings_db.py        # SQLite settings database
├── file_tree.py          # File tree utilities
├── mcp_external_tools.py # MCP (Model Context Protocol) integration
├── builtin_models.py     # Built-in GGUF model management
├── transcribe.py         # Audio transcription (Whisper)
├── title_gen.py          # Chat title generation
├── visual_context.py     # Visual context building
├── project_templates.py  # Project template definitions
├── tui.py                # Rich TUI utilities
├── cli.py                # CLI entry point
├── logger.py             # Logging configuration
├── errors.py             # Custom exceptions
├── chat_app.py           # Textual TUI chat application
├── test_orchestrator.py  # Orchestrator tests
└── tools/                # Agent tools
    ├── __init__.py       # Tool exports
    ├── file_tools.py     # File operations
    ├── shell_tools.py    # Shell command execution
    ├── search_tools.py   # Web and file search
    ├── git_tools.py      # Git operations
    ├── context_tools.py  # Semantic search tool
    ├── path_utils.py     # Path utilities
    ├── agent_context.py  # Agent context tracking
    └── duplicate_wrapper.py  # Duplicate call detection
```

---

## Core Components

### 1. server.py - Main FastAPI Server
**Purpose:** Provides REST API for the AI coding assistant.

#### Pydantic Models:
| Model | Description |
|-------|-------------|
| `VisualInteraction` | Visual interaction data (click, coordinates, element, color) |
| `VisualContext` | Image and interactions context |
| `ContextConfig` | Configure various context sources (files, code, docs, git, web) |
| `ChatRequest` | Chat API requests |
| `ModelUpdate` | Model switching requests |
| `DeleteHistoryRequest` | Delete conversations |
| `WarmRequest` | Cache warming requests |
| `HfReposStatusRequest` | HuggingFace repo status requests |
| `BuiltinDownloadRequest` | Model download requests |
| `BuiltinDeleteRequest` | Model deletion requests |
| `ExternalMcpBody` | External MCP server configuration |
| `SettingsUpdateBody` | Settings updates |

#### Key Functions:
| Function | Description |
|----------|-------------|
| `get_ollama_models()` | Fetches list of models from Ollama API |
| `get_lmstudio_models()` | Fetches list of models from LM Studio API |
| `get_provider()` | Returns the current LLM provider name |
| `get_provider_display_name()` | Returns human-readable provider name |
| `get_available_models()` | Returns list of available models based on provider |
| `_ensure_current_model_valid()` | Validates and falls back to built-in if needed |
| `_run_initialization()` | Runs async initialization in background thread |
| `get_agent(mode, model)` | Gets or builds a cached agent instance |
| `model_exists(name)` | Checks if a model exists |
| `ensure_model_exists(model)` | Raises HTTPException if model not found |
| `_build_message_with_context()` | Builds the complete prompt with all context sources |
| `stream_agent_events_with_history()` | Main streaming function for chat responses |
| `_provider_param_to_internal(provider)` | Converts provider display name to internal name |
| `_provider_internal_to_display(p)` | Converts internal provider name to display name |
| `_get_models_for_provider(p)` | Gets model list for a specific provider |
| `_export_to_markdown(conversations)` | Exports conversations to markdown format |

#### API Endpoints:
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/probe/available` | Probe Ollama and LM Studio availability |
| GET | `/health` | Health check endpoint |
| GET | `/logs` | Get server logs |
| POST | `/warm` | Warm the model cache |
| POST | `/cancel-shell` | Cancel running shell command |
| POST | `/cancel-chat` | Cancel running chat |
| GET | `/history` | List conversations |
| GET | `/history/export` | Export conversations |
| DELETE | `/history` | Delete conversations |
| GET | `/history/{id}` | Get conversation messages |
| POST | `/chat` | Main chat endpoint (streaming) |
| POST | `/chat/run` | Non-streaming chat execution |
| GET | `/models` | List available models |
| GET | `/model` | Get current model |
| PATCH | `/model` | Set current model |
| GET | `/builtin/system-info` | Get system info for model suggestions |
| GET | `/builtin/suggested-models` | Get suggested GGUF models |
| GET | `/builtin/huggingface-base` | Get HuggingFace base URL |
| GET | `/builtin/hf-search` | Search HuggingFace models |
| GET | `/builtin/hf-latest` | Get latest GGUF models |
| POST | `/builtin/hf-repos-status` | Check install status of repos |
| GET | `/builtin/hf-model-files` | Get GGUF files in a repo |
| POST | `/builtin/download` | Download a model |
| GET | `/builtin/download-status` | Get download progress |
| POST | `/builtin/download-stream` | Stream download progress |
| POST | `/builtin/download-cancel` | Cancel a download |
| POST | `/builtin/delete` | Delete a downloaded model |
| GET | `/builtin/models-dir` | Get models directory path |
| GET | `/files/tree` | Get workspace file tree |
| GET | `/files/content` | Get file content |
| POST | `/index` | Index workspace for semantic search |
| POST | `/transcribe` | Transcribe audio |
| GET | `/project/templates` | List project templates |
| POST | `/project/template` | Create project template file |
| GET | `/settings` | Get all settings |
| POST | `/settings` | Update settings |
| GET | `/settings/{key}` | Get a specific setting |
| PUT | `/settings/{key}` | Set a specific setting |
| DELETE | `/settings/{key}` | Delete a setting |
| GET | `/settings/llm` | Get LLM settings |
| GET | `/mcp/status` | Get MCP server status |
| GET | `/mcp/client-config` | Get MCP client config |
| GET | `/mcp/external` | Get external MCP servers |
| POST | `/mcp/external` | Configure external MCP servers |
| POST | `/shutdown` | Shutdown the server |

---

### 2. agent.py - Agent Builder
**Purpose:** Builds LangChain agents with appropriate tools and prompts for different modes.

#### Tool Sets:
| Variable | Description |
|----------|-------------|
| `AGENT_TOOLS` | Full set of tools for agent mode (read, write, edit, delete files, shell, tests, search, web, git) |
| `ASK_TOOLS` | Read-only tools for ask mode |
| `PLAN_TOOLS` | Read-only tools plus save_plan for plan mode |

#### Functions:
| Function | Description |
|----------|-------------|
| `build_agent(model, mode)` | Creates a LangChain agent with retry logic for specified model and mode (agent/ask/plan) |

---

### 3. orchestrator.py - Multi-Agent Orchestration
**Purpose:** Multi-agent orchestration for complex tasks, breaking them into subtasks and executing in parallel.

#### Classes:
| Class | Description |
|-------|-------------|
| `Subtask` | Dataclass representing a task subtask with id, task, files, parallel_group, result, error |

#### Functions:
| Function | Description |
|----------|-------------|
| `_parse_plan(text)` | Parses JSON plan response into Subtask objects |
| `_plan_subtasks(message, project_context, planner_model, fallback_models)` | Generates subtasks using planner model |
| `_group_by_parallel(subtasks)` | Groups subtasks by parallel_group |
| `_run_subtask(subtask, message, project_context, coder_model, history, get_agent_fn)` | Executes a single subtask |
| `_run_subtask_stream(subtask, ...)` | Executes subtask with streaming |
| `run_orchestrated(message, project_context, planner_model, coder_model, available_models, history, get_agent_fn)` | Main orchestration function that plans and executes subtasks |

---

### 4. multi_agent.py - Multi-Model Routing
**Purpose:** Multi-model routing and request classification.

#### Constants:
| Constant | Description |
|----------|-------------|
| `ROUTER_PROMPT` | Prompt for classifying request intent |
| `INTENT_HINTS` | Dictionary mapping intents to hints |
| `PLAN_PREP_PROMPT` | Prompt for generating execution plans |

#### Functions:
| Function | Description |
|----------|-------------|
| `_parse_router_response(text)` | Parses intent from router response |
| `classify_request(message, mode, available_models)` | Classifies request and selects appropriate model |
| `select_model_for_request(message, mode, available_models)` | Selects model for a request |
| `build_execution_plan(message, planner_model, available_models)` | Creates execution plan for complex tasks |

---

### 5. agent_harness.py - Agent Execution Harness
**Purpose:** Execution harness for running agents with streaming, cancellation, and event handling.

#### Functions:
| Function | Description |
|----------|-------------|
| `_register_cancel_event(e)` | Register cancellation event |
| `_unregister_cancel_event(e)` | Unregister cancellation event |
| `shutdown_llm_threads()` | Cancel all running LLM threads |
| `_response_meta_json(...)` | Creates JSON with response metadata |
| `_emit_log(level, message, model, extra)` | Creates log event JSON |
| `_init_agent_run()` | Initialize agent run context |
| `_step_timeout_for_run(timeout_sec)` | Calculate step timeout |
| `_to_langchain_messages(history)` | Convert history to LangChain messages |
| `stream_events(agent, message, config, timeout_sec, max_steps, history, model_name)` | Stream agent events asynchronously |
| `_run_stream_in_thread(...)` | Run streaming in background thread |
| `stream_events_maybe_threaded(...)` | Run streaming possibly in thread based on config |
| `run(agent, message, config, timeout_sec, max_steps, history)` | Non-streaming agent execution |

---

### 6. visual_agents.py - Vision/Image Processing Agents
**Purpose:** Vision/image processing agents for analyzing screenshots and UI elements.

#### Functions:
| Function | Description |
|----------|-------------|
| `_extract_text(response)` | Extract text from LLM response |
| `_get_agent_prompt(task)` | Get agent prompt for task type |
| `_parse_orchestrator_response(text)` | Parse orchestrator JSON response |
| `route_visual_task(message, image_b64, interactions, available_models)` | Route task to appropriate vision model |
| `run_visual_subagent(task, message, image_b64, interactions, model)` | Run a visual subagent |
| `process_visual_request(message, image_b64, interactions, available_models, parallel)` | Process visual request with orchestration |

---

### 7. llm_builder.py - LLM Factory
**Purpose:** Factory for building LLM instances for different providers.

#### Functions:
| Function | Description |
|----------|-------------|
| `_get_provider()` | Get current provider from server |
| `get_builtin_models()` | List GGUF models in models directory |
| `resolve_builtin_model_path(model)` | Resolve full path to GGUF model |
| `build_llm(model, temperature, num_predict, num_ctx, **kwargs)` | Build LLM for the current provider (supports: builtin, ollama, lmstudio, openai, anthropic, google) |

---

### 8. config.py - Configuration
**Purpose:** Configuration management via environment variables.

#### Configuration Variables:
| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `LM_STUDIO_BASE_URL` | `http://localhost:1234` | LM Studio API URL |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI API URL |
| `OPENAI_API_KEY` | (empty) | OpenAI API key |
| `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` | Anthropic API URL |
| `ANTHROPIC_API_KEY` | (empty) | Anthropic API key |
| `GOOGLE_BASE_URL` | `https://generativelanguage.googleapis.com` | Google API URL |
| `GOOGLE_API_KEY` | (empty) | Google API key |
| `HUGGINGFACE_BASE_URL` | `https://huggingface.co` | HuggingFace base URL |
| `LLM_PROVIDER` | `ollama` | Default LLM provider |
| `LLM_MODEL` | (empty) | Default LLM model |
| `BUILTIN_MODELS_DIR` | Platform-specific | Directory for GGUF models |
| `PREFERRED_MODELS` | codellama, deepseek-coder, etc. | Preferred model names |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model |
| `CHROMA_PERSIST_DIR` | `./chroma_data` | ChromaDB persistence directory |
| `FAISS_PERSIST_DIR` | `./faiss_data` | FAISS persistence directory |
| `WORKSPACE_ROOT` | `.` | Workspace root directory |
| `AGENT_TIMEOUT_SEC` | `1800` | Agent timeout in seconds |
| `AGENT_MAX_STEPS` | `0` (unlimited) | Max agent steps |
| `STEP_TIMEOUT_SEC` | `1200` | Step timeout in seconds |
| `MAX_HISTORY_MESSAGES` | `20` | Max messages in history |
| `MAX_PROMPT_CHARS` | (calculated) | Max prompt characters |
| `NUM_CTX` | `8192` | Context window size |
| `NUM_PREDICT` | `0` | Max tokens to predict |
| `TEMPERATURE` | `0.1` | LLM temperature |
| `REPEAT_PENALTY` | `1.1` | Repeat penalty |
| `OLLAMA_KEEP_ALIVE` | `10m` | Model keep alive time |
| `CACHE_DIR` | Platform-specific | Cache directory |
| `VECTOR_CACHE_TTL` | `300` | Vector cache TTL |
| `KV_WARM_ENABLED` | `true` | Enable KV cache warming |
| `MULTI_MODEL_ENABLED` | `true` | Enable multi-model routing |
| `MULTI_AGENT_ORCHESTRATOR_ENABLED` | `true` | Enable orchestrator |
| `RUN_LLM_IN_THREAD` | Provider-dependent | Run LLM in thread |
| `MODEL_CODER` | (from LLM_MODEL) | Model for coding |
| `MODEL_PLANNER` | (from MODEL_CODER) | Model for planning |
| `MODEL_VL` | `qwen3-vl:8b` | Vision-language model |

---

### 9. prompts.py - System Prompts
**Purpose:** System prompts for different agent modes.

#### Prompt Variables:
| Variable | Description |
|----------|-------------|
| `CODING_AGENT_SYSTEM_PROMPT` | Full system prompt for coding agent mode |
| `CHAT_TITLE_PROMPT` | Prompt for generating chat titles |
| `ASK_MODE_PROMPT` | System prompt for ask (read-only) mode |
| `PLAN_MODE_PROMPT` | System prompt for plan (planning-only) mode |

---

### 10. context_builders.py - Context Builders
**Purpose:** Builds various context sections for agent prompts.

#### Functions:
| Function | Description |
|----------|-------------|
| `build_project_file_context()` | Build context from `.ai-dev/project.md` files |
| `build_file_structure_context()` | Build file structure summary |
| `build_project_context()` | Build full project context |
| `build_files_context(paths)` | Build context from specific files |
| `build_code_context(segments)` | Build context from code segments |
| `build_codebase_context(query, k)` | Semantic search in codebase |
| `build_docs_context(urls)` | Fetch and extract text from URLs |
| `_extract_text_from_html(html)` | Extract text from HTML |
| `build_git_context(ref, diff, n)` | Build git log or diff context |
| `build_web_context(query, max_results)` | Search web and return results |
| `build_past_chats_context(conversation_id, include_other_ids)` | Include past conversation history |

---

### 11. chat_db.py - Chat History Database
**Purpose:** SQLite database for chat history persistence.

#### Functions:
| Function | Description |
|----------|-------------|
| `_db_path()` | Get database file path |
| `_get_conn()` | Get database connection |
| `_ensure_schema(conn)` | Create tables if not exist |
| `ensure_db()` | Ensure database is initialized |
| `create_conversation(title)` | Create new conversation, return ID |
| `set_conversation_title(conversation_id, title)` | Update conversation title |
| `add_message(conversation_id, role, content)` | Add message to conversation |
| `list_conversations(limit, offset)` | List conversations with pagination |
| `get_messages(conversation_id)` | Get all messages in conversation |
| `delete_conversations(ids)` | Delete conversations |

#### Database Schema:
```sql
CREATE TABLE conversation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT 'New chat',
    created_at TEXT NOT NULL
);

CREATE TABLE message (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversation(id)
);

CREATE INDEX idx_message_conversation ON message(conversation_id);
```

---

### 12. settings_db.py - Settings Database
**Purpose:** SQLite database for application settings persistence.

#### Functions:
| Function | Description |
|----------|-------------|
| `_get_settings_path()` | Get settings database path |
| `_get_conn()` | Get database connection |
| `_ensure_schema(conn)` | Create tables if not exist |
| `init_settings_db()` | Initialize settings database |
| `is_initialized()` | Check if database is initialized |
| `get_setting(key, default)` | Get a setting value |
| `set_setting(key, value)` | Set a setting value |
| `get_all_settings()` | Get all settings as dictionary |
| `delete_setting(key)` | Delete a setting |
| `get_mcp_settings()` | Get MCP server settings |
| `set_mcp_setting(key, value)` | Set MCP server setting |

---

### 13. file_tree.py - File Tree Utilities
**Purpose:** File tree and project context utilities.

#### Functions:
| Function | Description |
|----------|-------------|
| `_should_show(rel)` | Check if path should be shown in tree |
| `_build_tree(p, rel_prefix)` | Recursively build tree structure |
| `get_file_tree()` | Get full file tree for workspace |
| `_tree_to_text(items, prefix, depth, max_depth, max_children)` | Convert tree to text format |
| `get_file_structure_summary()` | Get human-readable file structure |
| `_detect_project_types(root)` | Detect project type from indicators |
| `get_project_context()` | Get full project context |
| `read_file_content(rel_path)` | Read file content with safety checks |

---

### 14. semantic_index.py - Vector Store
**Purpose:** Vector store for semantic code search using embeddings.

#### Functions:
| Function | Description |
|----------|-------------|
| `_lru_cache_get(cache, key, ttl, now)` | Get from LRU cache with TTL |
| `_lru_cache_set(cache, key, val, max_size, now)` | Set LRU cache entry |
| `_check_chroma()` | Check if ChromaDB is available |
| `_should_index(path, rel)` | Check if file should be indexed |
| `get_embeddings()` | Get Ollama embeddings instance |
| `get_vector_store(collection_name, clear)` | Get or create vector store |
| `index_workspace_files(vector_store, max_file_size, batch_size)` | Index all workspace files |
| `is_index_empty(vector_store)` | Check if index is empty |
| `ensure_indexed(vector_store)` | Ensure workspace is indexed |
| `query_index(vector_store, query, k)` | Query semantic index |

---

### 15. builtin_models.py - Built-in Model Management
**Purpose:** Built-in GGUF model management and HuggingFace integration.

#### Constants:
| Constant | Description |
|----------|-------------|
| `SUGGESTED_MODELS` | List of suggested GGUF models with metadata |

#### Functions:
| Function | Description |
|----------|-------------|
| `_llama_cpp_available()` | Check if llama-cpp-python is installed |
| `ensure_llama_cpp_python()` | Install llama-cpp-python if needed |
| `get_system_ram_gb()` | Get system RAM in GB |
| `get_system_tier()` | Get system tier (low/medium/high) |
| `get_installed_models()` | List installed GGUF models |
| `model_is_installed(filename)` | Check if model is installed |
| `get_suggested_for_system()` | Get suggested models for system |
| `hf_file_url(repo_id, filename)` | Get HuggingFace file download URL |
| `bytes_likely_too_large(file_size)` | Check if file likely too large |
| `_is_gguf_model_card(m)` | Check if model card is GGUF |
| `_prune_cache(cache, max_entries)` | Prune LRU cache |
| `hf_search_models(query, limit)` | Search HuggingFace for GGUF models |
| `hf_latest_gguf_models(limit)` | Get latest GGUF models |
| `fetch_model_card(repo_id)` | Fetch model card from HuggingFace |
| `_quant_preference(filename)` | Score quantization preference |
| `hf_model_gguf_files(repo_id)` | Get GGUF files in repo |
| `hf_repo_card_summary(repo_id)` | Get repo card summary |
| `hf_repos_install_status(repo_ids)` | Check install status of repos |
| `download_model(repo_id, filename)` | Download GGUF model |
| `download_model_with_progress(repo_id, filename, should_cancel)` | Download with progress streaming |

---

## Tools (`tools/`)

### file_tools.py
**Purpose:** File operation tools for the agent.

| Function | Description |
|----------|-------------|
| `_invalidate_read_cache(path)` | Invalidate read cache for path |
| `list_directory(path)` | List directory contents |
| `read_file(path)` | Read file content with caching |
| `write_file(path, content)` | Create or overwrite file |
| `edit_file(path, old_string, new_string, replace_all)` | Replace text in file |
| `delete_file(path)` | Delete a file |
| `save_plan(content, title)` | Save markdown plan to `.ai-dev/plans/` |

---

### shell_tools.py
**Purpose:** Shell command execution tools.

| Function | Description |
|----------|-------------|
| `request_shell_cancel()` | Request cancellation of shell command |
| `_validate_shell_command(cmd)` | Check for dangerous commands |
| `_read_pipe(pipe, buf)` | Read subprocess pipe |
| `shell_command(command, timeout_seconds)` | Execute shell command |
| `run_tests(command, timeout_seconds)` | Run test suite (default: pytest) |

---

### search_tools.py
**Purpose:** Web and file search tools.

| Function | Description |
|----------|-------------|
| `_extract_text_from_html(html)` | Extract text from HTML |
| `scrape_url(url, max_chars)` | Fetch webpage and extract text |
| `web_search(query, max_results)` | Search the web using DuckDuckGo |
| `grep_search(pattern, path, recursive)` | Regex search in files |
| `glob_search(pattern, path)` | Find files by glob pattern |

---

### git_tools.py
**Purpose:** Git operation tools.

| Function | Description |
|----------|-------------|
| `_run_git(args, timeout)` | Run git command |
| `git_status()` | Show git status (short) |
| `git_diff(ref)` | Show git diff |

---

### context_tools.py
**Purpose:** Semantic search tool using vector index.

| Function | Description |
|----------|-------------|
| `search_context(query, k)` | Search semantic index for relevant code |

---

### path_utils.py
**Purpose:** Path utilities for workspace safety.

| Function | Description |
|----------|-------------|
| `resolve_workspace_path(path)` | Resolve path within workspace, raising PermissionError if outside |

---

### agent_context.py
**Purpose:** Agent context tracking for duplicate detection.

| Variable | Description |
|----------|-------------|
| `_agent_run_calls` | ContextVar for tracking tool calls |
| `READ_ONLY_TOOLS` | Frozenset of read-only tool names |

| Function | Description |
|----------|-------------|
| `init_agent_run()` | Initialize agent run context |
| `check_duplicate_tool_call(tool_name, args)` | Check for duplicate tool calls |

---

### duplicate_wrapper.py
**Purpose:** Wraps tools to detect duplicate calls.

| Function | Description |
|----------|-------------|
| `_wrap_tool(tool)` | Wrap a single tool with duplicate check |
| `wrap_tools_with_duplicate_check(tools)` | Wrap all tools with duplicate check |

---

### tools/__init__.py
**Purpose:** Exports all agent tools.

#### Exported Tools:
- `read_file`, `write_file`, `edit_file`, `delete_file`, `save_plan`
- `list_directory`, `shell_command`, `run_tests`
- `grep_search`, `glob_search`, `web_search`, `scrape_url`
- `search_context`, `git_status`, `git_diff`

---

## Additional Components

### mcp_external_tools.py
**Purpose:** Integration with Model Context Protocol (MCP) external servers.

| Function | Description |
|----------|-------------|
| `get_servers_config()` | Get configured MCP servers |
| `set_mcp_settings(servers)` | Save MCP server configuration |
| `_sanitize_name(s)` | Sanitize MCP tool names for Python |
| `_schema_to_model(schema, model_name)` | Convert JSON schema to Pydantic model |
| `_result_to_text(result)` | Convert MCP result to text |
| `_list_tools_stdio(cfg)` | List tools from MCP server |
| `_call_stdio_tool(cfg, tool_name, arguments)` | Call tool on MCP server |
| `_run_async_in_thread(coro)` | Run async function in thread |
| `discover_external_servers_async()` | Discover MCP servers (async) |
| `discover_external_servers_sync()` | Discover MCP servers (sync) |
| `_build_tools_async()` | Build LangChain tools from MCP |
| `_cache_key()` | Get cache key for MCP config |
| `get_external_mcp_tools_sync(mode)` | Get cached MCP tools |
| `invalidate_external_mcp_cache()` | Invalidate MCP tools cache |

---

### transcribe.py
**Purpose:** Audio transcription using Faster Whisper.

| Function | Description |
|----------|-------------|
| `_get_model()` | Get or load Whisper model |
| `transcribe_audio(audio_bytes, language)` | Transcribe audio bytes to text |

---

### title_gen.py
**Purpose:** Generate chat conversation titles.

| Function | Description |
|----------|-------------|
| `generate_chat_title(first_message, model)` | Generate title from first message |

---

### visual_context.py
**Purpose:** Build visual context for vision-language models.

| Function | Description |
|----------|-------------|
| `build_visual_instruction(user_prompt, image_b64, interactions)` | Build instruction text with interactions |
| `build_visual_message_content(user_prompt, image_b64, interactions)` | Build message content for LLM |

---

### project_templates.py
**Purpose:** Project template definitions.

| Constant | Description |
|----------|-------------|
| `PROJECT_TEMPLATES` | Dictionary of project templates by type |

| Function | Description |
|----------|-------------|
| `get_template(name)` | Get template by name |
| `list_templates()` | List all available templates |

---

### tui.py
**Purpose:** Rich TUI utilities for CLI.

| Function | Description |
|----------|-------------|
| `_try_import()` | Try importing Rich library |
| `_get_prompt_session()` | Get prompt_toolkit session |
| `is_available()` | Check if TUI is available |
| `print_user(msg)` | Print user message |
| `print_assistant(msg, use_markdown)` | Print assistant message |
| `print_assistant_stream_start()` | Start streaming output |
| `print_assistant_stream_chunk(chunk)` | Print streaming chunk |
| `print_assistant_stream_end()` | End streaming output |
| `print_status(msg)` | Print status message |
| `print_tool(name)` | Print tool name |
| `print_error(msg)` | Print error message |
| `print_rule()` | Print horizontal rule |
| `print_welcome(mode)` | Print welcome message |
| `prompt_input()` | Get user input |
| `print_session_list(items)` | Print session list table |

---

### cli.py
**Purpose:** CLI entry point for the application.

| Function | Description |
|----------|-------------|
| `_get_tui(args)` | Get TUI instance |
| `_ensure_workspace()` | Ensure workspace is set |
| `_parse_args()` | Parse command-line arguments |
| `_get_last_conversation_id()` | Get last conversation ID |
| `_run_chat(args, model_override)` | Run chat mode |
| `_stream_display(stream, use_json)` | Display streaming response |
| `_cmd_models()` | List models command |
| `_cmd_index()` | Index workspace command |
| `_cmd_session_list()` | List sessions command |
| `_cmd_serve(args)` | Start server command |
| `main()` | Main CLI entry point |

#### CLI Commands:
| Command | Description |
|---------|-------------|
| `run <prompt>` | Run single prompt and exit |
| `chat` | Interactive chat mode |
| `serve` | Start API server |
| `models` | List available models |
| `index` | Index workspace |
| `session list` | List conversations |

---

### chat_app.py
**Purpose:** Textual-based Terminal UI for interactive chat.

#### Classes:
| Class | Description |
|-------|-------------|
| `StatusBar` | Widget displaying current model, mode, session ID |
| `ChatApp` | Main Textual application for chat interface |

#### StatusBar Methods:
| Method | Description |
|--------|-------------|
| `__init__(model, mode, session)` | Initialize status bar |
| `update_status(model, mode, session)` | Update displayed status |

#### ChatApp Methods:
| Method | Description |
|--------|-------------|
| `compose()` | Compose the TUI layout |
| `on_mount()` | Handle app mount event |
| `action_quit()` | Quit the application |
| `action_help()` | Show help |
| `action_new_session()` | Start new session |
| `action_models()` | Show available models |
| `_show_help()` | Display help panel |
| `_show_models()` | Display models table |
| `_add_user_message(text)` | Display user message |
| `_add_status(text)` | Display status message |
| `_add_tool(name)` | Display tool being executed |
| `_add_assistant_content(content)` | Display assistant response |
| `_add_error(text)` | Display error message |
| `_toggle_dense()` | Toggle dense layout mode |
| `_run_agent(message)` | Run agent with message (async) |
| `on_input_submitted(event)` | Handle input submission |

#### Entry Point:
| Function | Description |
|----------|-------------|
| `run_chat_app(mode, conv_id, model_override)` | Launch the TUI chat application |

---

### logger.py
**Purpose:** Logging configuration with file rotation.

| Function | Description |
|----------|-------------|
| `get_logger(name, level)` | Get or create logger with file and console handlers |

---

### errors.py
**Purpose:** Custom exception classes.

| Class | Description |
|-------|-------------|
| `ToolError` | Base exception for tool errors with path and tool info |
| `TimeoutError` | Timeout-specific tool error |
| `IndexError` | Index-specific tool error |

---

### test_orchestrator.py
**Purpose:** Test suite for orchestrator functionality.

| Function | Description |
|----------|-------------|
| `_ollama_reachable()` | Check if Ollama is reachable |
| `test_parse()` | Test plan parsing |
| `test_plan_with_ollama()` | Test planning with Ollama |
| `test_run_orchestrated()` | Test orchestrated execution |

---

## Model Utilities (`model/`)

### finetune.py
**Purpose:** Model fine-tuning using Unsloth.

| Function | Description |
|----------|-------------|
| `load_local_dataset(path)` | Load dataset from JSON/JSONL file |

#### Main Parameters:
| Parameter | Default | Description |
|-----------|---------|-------------|
| `--dataset` | (required) | Path to training data |
| `--max-steps` | `60` | Maximum training steps |
| `--max-seq-length` | `4096` | Maximum sequence length |
| `--output-dir` | `outputs` | Output directory |
| `--batch-size` | `4` | Training batch size |
| `--grad-accum` | `4` | Gradient accumulation steps |

---

### export_ollama.py
**Purpose:** Export fine-tuned models to Ollama GGUF format.

| Function | Description |
|----------|-------------|
| `main()` | Export and create Ollama model |

#### Main Parameters:
| Parameter | Default | Description |
|-----------|---------|-------------|
| `--model-dir` | `outputs` | Path to fine-tuned model |
| `--gguf-dir` | `gguf` | Output directory |
| `--quantization` | `Q8_0` | Quantization method |
| `--ollama-name` | `vencoder-gpt-oss:20b` | Ollama model name |

---

## Summary of Functionality

### 1. LLM Provider Support
- **Ollama** - Local models
- **LM Studio** - Local models
- **OpenAI** - GPT models
- **Anthropic** - Claude models
- **Google** - Gemini models
- **Built-in GGUF** - Local quantized models

### 2. Agent Modes
| Mode | Description |
|------|-------------|
| **agent** | Full coding agent with file operations, shell commands, tests |
| **ask** | Read-only mode for questions and explanations |
| **plan** | Planning mode that creates execution plans |

### 3. Tool Suite
- **File operations:** read, write, edit, delete
- **Directory listing**
- **Shell command execution** with safety validation
- **Test execution** (pytest, npm test, etc.)
- **Grep and glob search**
- **Web search and URL scraping**
- **Git operations:** status, diff
- **Semantic code search**
- **Save execution plans**
- **MCP external tool integration**

### 4. Context Building
- Project file context
- File structure summary
- Code segments
- Semantic codebase search
- Documentation fetching
- Git log and diff
- Web search results
- Past conversation history
- Vision/image analysis

### 5. Multi-Agent Orchestration
- Request classification
- Model routing
- Task decomposition
- Parallel subtask execution
- Vision-language task handling

### 6. Data Persistence
- SQLite chat history
- SQLite settings storage
- Vector store (ChromaDB/FAISS) for semantic search

### 7. API Endpoints
- Full REST API for all functionality
- Streaming responses via SSE
- Health checks and probing
- Model management
- HuggingFace model download
- Audio transcription

### 8. User Interfaces
- FastAPI server
- Textual TUI
- CLI application
