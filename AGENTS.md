# BOYSER AI — CLI Coding Agent

CLI coding agent in the style of Claude Code, running on your machine.
This file is auto-loaded into context when BOYSER AI runs in this directory
(matches `AGENTS.md` in the `PROJECT_FILES` list in `boyser/config.py`).

---

## Project Overview

**BOYSER AI** is a Python CLI agent that provides a Claude Code-like experience
with support for multiple backends (Anthropic Claude, OpenAI-compatible cloud
APIs, Ollama local models, llama.cpp). It features 16 tools, 42 progressive-disclosure
skills, MCP (Model Context Protocol) integration, and subagent delegation.

Repo: https://github.com/nanofatdog/boyser-ai
Forked from: apgamerinfo/boyser-ai
License: MIT

---

## Architecture — 8-Module `boyser/` Package

```
boyser/                          # Core package (8 modules)
├── __init__.py                  # Package marker with docstring
├── __main__.py                  # `python3 -m boyser` entry point → calls agent.main()
├── config.py                    # Constants, paths, TOOLS schema (16 tools), config I/O
├── interrupt.py                 # ESC-based interrupt system (terminal cbreak reader)
├── repl.py                      # prompt_toolkit REPL, slash commands, @ file mentions
├── tools.py                     # 16 tool implementations + TOOL_FUNCS dispatch dict
├── backend.py                   # ClaudeBackend + LocalBackend (Ollama/Cloud/llama.cpp)
├── agent.py                     # build_system, setup wizard, main loop, slash commands
├── mcp.py                       # MCP client (Model Context Protocol) — NEW
└── subagent.py                  # SubAgent delegation (parallel child agents) — NEW

agent.py                         # Thin wrapper (20 lines) — only sets sys.path + calls main()
```

### Module Responsibilities

| Module | Lines | Responsibility |
|--------|-------|---------------|
| `agent.py` | ~20 | Thin entry point — imports `boyser.agent.main()` |
| `boyser/agent.py` | ~695 | `build_system()`, setup wizard, main agentic loop, slash command handlers |
| `boyser/backend.py` | ~488 | `ClaudeBackend` (Anthropic SDK), `LocalBackend` (OpenAI-compatible / Ollama native), `make_backend()` factory, streaming, thinking display, tool dispatch loop |
| `boyser/tools.py` | ~1043 | All 16 tool implementations (bash, read_file, write_file, edit_file, patch, search_files, glob, grep, web_search, web_fetch, vision, todo_write, remember, use_skill, ask_user, subagent), `TOOL_FUNCS` dispatch dict, `confirm()` |
| `boyser/config.py` | ~516 | Paths, constants, `TOOLS` list (tool schemas for both Claude + OpenAI), `CLOUD_PROVIDERS` presets, config load/save, skill discovery, utility functions |
| `boyser/repl.py` | ~425 | `prompt_toolkit` REPL, `make_prompt()`, slash commands, `@file` mentions, `usage_line()`, display utilities |
| `boyser/interrupt.py` | ~152 | `Interrupt` class (ESC key listener in background thread), `hard_close()`, `esc_watch()` |
| `boyser/mcp.py` | ~420 | MCP JSON-RPC client — initialize, list tools, call tools via stdio subprocesses |
| `boyser/subagent.py` | ~684 | `SubAgentClient` — spawn parallel child agents as subprocesses, each with its own toolset |

---

## Key Design Decisions

### 1. Single Thin Entry Point (`agent.py`)
- `agent.py` at repo root is ~20 lines — just sets `sys.path` and imports `boyser.agent.main()`
- All logic lives in the `boyser/` package modules
- Also runnable via `python3 -m boyser` (`boyser/__main__.py`)

### 2. Multi-Backend Architecture
- **Claude API**: Uses Anthropic Python SDK (`anthropic`). Default `claude-opus-4-8`.
  Auth via API key or `ANTHROPIC_AUTH_TOKEN`. Streamed with `MessageStream`.
- **Ollama**: Local models via Ollama's OpenAI-compatible `/v1` endpoint + native `/api/chat`
  for `num_ctx` control. Probed via `/api/version`.
- **Cloud API**: OpenAI-compatible APIs (OpenRouter, Groq, DeepSeek, OpenAI, Together, Gemini).
  Uses `CLOUD_PROVIDERS` presets in `config.py`.
- **llama.cpp**: OpenAI-compatible server at `localhost:8080/v1`.
- `make_backend(cfg)` in `backend.py` returns `ClaudeBackend` or `LocalBackend`.

### 3. 16 Tools Total
The original 12 tools + 4 new ones added in this fork:

| # | Tool | Module | Description |
|---|------|--------|-------------|
| 1 | `bash` | tools.py | Run shell command (120s timeout, ESC kills via SIGKILL/killpg) |
| 2 | `read_file` | tools.py | Read file with line numbers |
| 3 | `write_file` | tools.py | Create/overwrite file (shows diff, requires confirm) |
| 4 | `edit_file` | tools.py | Surgical string replacement (exact match, shows diff) |
| 5 | `glob` | tools.py | Find files by glob pattern (sorted by mtime) |
| 6 | `grep` | tools.py | Recursive regex file search (skips .git/.venv/node_modules) |
| 7 | `web_search` | tools.py | DuckDuckGo search (auto-fetches top result content) |
| 8 | `web_fetch` | tools.py | Fetch URL content (HTML stripped) |
| 9 | `todo_write` | tools.py | Multi-step task planning |
| 10 | `remember` | tools.py | Cross-session memory |
| 11 | `use_skill` | tools.py | Load skill instructions |
| 12 | `ask_user` | tools.py | Ask user with options |
| 13 | `vision` | **NEW** | Analyze images via local multimodal model |
| 14 | `patch` | **NEW** | Smart find-and-replace with 5 fuzzy matching strategies |
| 15 | `search_files` | **NEW** | Regex content search + glob file search |
| 16 | `subagent` | **NEW** | Spawn parallel child agents |

### 4. ESC-Based Interrupt System
- `boyser/interrupt.py` implements a cbreak terminal reader in a background thread
- Pressing ESC mid-response stops the model turn immediately:
  - During streaming: breaks the generation loop
  - During bash execution: sends SIGKILL to process group
  - Between tool rounds: marks remaining tools as stopped
- Works on Windows via `msvcrt`, on Linux/macOS via `termios` + `tty`

### 5. Progressive Disclosure Skills (42)
- Skills are directories containing `SKILL.md` with YAML frontmatter (`name`, `description`)
- Located in `~/.config/boyser-ai/skills/<name>/` (global) or `.boyser/skills/<name>/` (project)
- `discover_skills()` loads only names + descriptions into system prompt
- The `use_skill` tool loads the full body on demand — saves context window
- 42 skills bundled: code review, debug, diagnose, refactor, web research, sql, dockerfile,
  adb-android, tdd, and many more

---

## File Map

| Path | Description |
|------|-------------|
| `/agent.py` | Thin entry point (20 lines) |
| `/boyser/__init__.py` | Package marker |
| `/boyser/__main__.py` | `python3 -m boyser` entry |
| `/boyser/agent.py` | Main agent orchestration, wizard, REPL loop |
| `/boyser/backend.py` | Backend implementations (Claude + Local) |
| `/boyser/tools.py` | All 16 tool implementations + dispatch |
| `/boyser/config.py` | Constants, paths, TOOLS schemas, config I/O |
| `/boyser/repl.py` | prompt_toolkit REPL, display utilities |
| `/boyser/interrupt.py` | ESC interrupt system |
| `/boyser/mcp.py` | MCP client (Model Context Protocol) |
| `/boyser/subagent.py` | SubAgent parallel delegation |
| `/README.md` | User-facing documentation (Thai + English) |
| `/BOYSER.md` | Legacy project context file (pre-fork single-file era) |
| `/AGENTS.md` | **This file** — AI agent context |
| `/CHANGELOG.md` | Release changelog |
| `/requirements.txt` | Python dependencies |
| `/install.sh` | Linux/macOS installer |
| `/install.ps1` | Windows PowerShell installer |
| `/install.bat` | Windows batch installer |
| `/skills/` | 42 skill directories (each containing SKILL.md) |
| `/assets/screenshot.png` | Screenshot for README |

---

## Development Guidelines

### Code Architecture Rules

1. **All code in `boyser/` package modules** — `agent.py` at the repo root must remain a thin wrapper
   (only `sys.path` setup + `from boyser.agent import main`).

2. **Don't put logic in `agent.py`** — it's a 20-line launcher. New features go into existing modules
   or new modules in the `boyser/` package.

3. **Adding a new tool requires 3 steps:**
   a. **Function**: Add your tool implementation function in `boyser/tools.py`
   b. **Dispatch**: Add an entry in `TOOL_FUNCS` dict (at bottom of `tools.py`)
      - Pattern: `"tool_name": lambda i: my_tool_func(i["param1"], i.get("param2", default))`
   c. **Schema**: Add a tool schema dict in `TOOLS` list in `boyser/config.py`
      - Pattern: `{"name": "...", "description": "...", "input_schema": {"type": "object", "properties": {...}, "required": [...]}}`

4. **Adding a new backend requires:**
   a. **Subclass**: Add a new backend class in `boyser/backend.py` (following `ClaudeBackend` or `LocalBackend` pattern)
   b. **Factory**: Add an entry in `make_backend()` function

5. **Skills follow the SKILL.md convention:**
   - YAML frontmatter with `name` and `description`
   - Body contains the full instructions loaded by `use_skill`
   - Place in `skills/<name>/SKILL.md` for bundled, or `~/.config/boyser-ai/skills/<name>/SKILL.md`

6. **All imports from `boyser.config`** — use the constants module for paths, tool schemas,
   lookups. Don't hardcode paths.

### Testing

```bash
# Syntax check
python3 -m py_compile agent.py
python3 -m py_compile boyser/config.py
python3 -m py_compile boyser/tools.py
python3 -m py_compile boyser/backend.py
python3 -m py_compile boyser/agent.py
python3 -m py_compile boyser/interrupt.py
python3 -m py_compile boyser/repl.py
python3 -m py_compile boyser/mcp.py
python3 -m py_compile boyser/subagent.py

# Import test
python3 -c "import boyser; print('OK')"

# Non-interactive functional test
printf 'Hello\na\nexit\n' | python3 agent.py --local --model qwen3-coder
```

### Key Conventions

- Respond in Thai when user types Thai (technical terms in English)
- Code comments and UI strings are bilingual (Thai/English)
- Make surgical changes — touch only what's needed, don't refactor unrelated code
- All tool execution goes through `execute_tool(name, args)` in `tools.py`
- The `TOOLS` list schema is shared by both backends (Claude SDK + OpenAI function calls)
