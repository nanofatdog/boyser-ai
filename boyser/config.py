"""
กำหนดค่าคงที่ เส้นทาง และฟังก์ชัน load/save config
แยกออกมาจาก agent.py เพื่อให้ import ได้สะอาด
"""

from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import threading

# ============================================================
# ค่าคงที่และเส้นทาง
# ============================================================

CLAUDE_MODELS = [
    ("claude-opus-4-8", "ฉลาดสุด ($5/$25 ต่อ 1M token)"),
    ("claude-sonnet-4-6", "สมดุลความเร็ว/ราคา ($3/$15)"),
    ("claude-haiku-4-5", "เร็ว ถูกสุด ($1/$5)"),
]
OLLAMA_URL = "http://localhost:11434/v1"
LLAMACPP_URL = "http://localhost:8080/v1"
# ผู้ให้บริการ cloud ที่ใช้ API แบบ OpenAI-compatible (ใส่ key แล้วใช้ผ่าน backend เดียวกับ local)
CLOUD_PROVIDERS = {
    "OpenRouter": "https://openrouter.ai/api/v1",
    "Groq": "https://api.groq.com/openai/v1",
    "DeepSeek": "https://api.deepseek.com/v1",
    "OpenAI": "https://api.openai.com/v1",
    "Together": "https://api.together.xyz/v1",
    "Gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
}

WORKDIR = os.getcwd()
CONFIG_DIR = os.path.expanduser("~/.config/boyser-ai")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
HISTORY_PATH = os.path.join(CONFIG_DIR, "history")
MEMORY_FILE = os.path.join(CONFIG_DIR, "memory.md")
PROJECT_FILES = ["BOYSER.md", "AGENTS.md", "CLAUDE.md"]  # auto-load ไฟล์แรกที่เจอใน cwd
# skill = โฟลเดอร์ที่มี SKILL.md (frontmatter: name/description) — project มาก่อน global
SKILLS_DIRS = [os.path.join(WORKDIR, ".boyser", "skills"), os.path.join(CONFIG_DIR, "skills")]
SKILLS: dict = {}  # name -> {path, dir, description}
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # โฟลเดอร์ repo root
UPDATE_AVAILABLE = threading.Event()  # ตั้งโดย background check → main loop โชว์เตือนครั้งเดียว
IS_WIN = os.name == "nt"


def _find_git_bash() -> str | None:
    """หา bash.exe ของ Git for Windows — จงใจไม่ใช้ which("bash") เพราะบน Windows
    มักได้ System32\\bash.exe (WSL) ซึ่งเป็นคนละ filesystem"""
    git = shutil.which("git")
    candidates = []
    if git:  # ปกติ git.exe อยู่ <root>\\cmd\\git.exe → bash อยู่ <root>\\bin\\bash.exe
        root = os.path.dirname(os.path.dirname(git))
        candidates.append(os.path.join(root, "bin", "bash.exe"))
    for env in ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData"):
        base = os.environ.get(env)
        if base:
            candidates.append(os.path.join(base, "Git", "bin", "bash.exe"))
            candidates.append(os.path.join(base, "Programs", "Git", "bin", "bash.exe"))
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


GIT_BASH = _find_git_bash() if IS_WIN else None


def _load_logo() -> str:
    try:
        import pyfiglet
        return pyfiglet.figlet_format("BOYSER AI", font="ansi_shadow").rstrip("\n")
    except Exception:
        return "✻ BOYSER AI"


LOGO = _load_logo()

# ---------- ธีมสี (เปลี่ยนได้ด้วย /theme) ----------
THEMES = {
    "ฟ้า": {"accent": "#22b8e6", "border": "#5fafff"},
    "เขียว": {"accent": "#56d364", "border": "#3fb950"},
    "ม่วง": {"accent": "#a371f7", "border": "#bc8cff"},
    "ส้ม": {"accent": "#ff9e3d", "border": "#ff8700"},
    "ชมพู": {"accent": "#ff79c6", "border": "#ff87d7"},
    "ขาวดำ": {"accent": "#dddddd", "border": "#888888"},
}
THEME = {"name": "ฟ้า", **THEMES["ฟ้า"]}
THINK_ON = False  # /think: ให้โมเดล local reason ก่อนตอบ (ช้าลงแต่ฉลาดขึ้น)
MAX_TOOL_ROUNDS = 25  # กันลูป agentic ไม่จบ (โมเดลเรียก tool ซ้ำไม่หยุด)
LONGDOC_CHARS = 150_000  # ~40-50k token — เกินนี้ถือเป็น request วิเคราะห์เอกสารยาว
VOTE_ON = True  # /vote: เอกสารยาวถามซ้ำ 3 รอบหา consensus (โมเดล local ตอบไม่นิ่งแม้ temp 0)
VOTE_ROUNDS = 3
YOLO = False
ALWAYS_ALLOW: set = set()

# ---------- วันปัจจุบัน ----------
_THAI_DAYS = ["วันจันทร์", "วันอังคาร", "วันพุธ", "วันพฤหัสบดี", "วันศุกร์", "วันเสาร์", "วันอาทิตย์"]
_now = datetime.datetime.now()
TODAY = f"{_now.strftime('%A %Y-%m-%d')} ({_THAI_DAYS[_now.weekday()]})"

# ---------- system prompt ----------
if IS_WIN:
    _SHELL_NOTE = (
        "\nThis machine runs Windows. Shell commands execute under "
        + ("Git Bash — bash syntax (ls, grep, pipes) works." if GIT_BASH
           else "cmd.exe — write Windows commands (dir, type, set), NOT bash syntax.")
    )
else:
    _SHELL_NOTE = ""

SYSTEM = f"""You are BOYSER AI, a helpful coding agent running on the user's local machine.
Working directory: {WORKDIR}
Current date: {TODAY} (run `date` via bash if you need the exact time){_SHELL_NOTE}

Use your tools to complete tasks:
- bash: run shell commands (git, install, run scripts)
- read_file / write_file / edit_file: work with files; prefer edit_file for small changes
- glob / grep: explore the codebase before editing — find files by pattern, search content
- **patch**: smart find-and-replace (handles whitespace mismatches, multiple strategies)
- **vision**: analyze images (local multimodal model or URL)
- **search_files**: intelligent file search by content/regex or name/glob
- **web_search / web_fetch**: look up current information online. IMPORTANT: web_search returns only short snippets (often just page descriptions, not the actual data). If the snippets don't already contain the concrete answer (a price, a number, a date, a fact), you MUST web_fetch the most relevant result URL to read the real content BEFORE answering. Never answer a factual question with just a list of sources/links — fetch, then answer with the actual value and cite the source.
- **subagent**: spawn a child agent to work on a task in parallel while you continue the conversation. Use this for independent research, data processing, or any task that doesn't need your current context. The subagent has its own tools (bash, read_file, write_file, grep, glob).

Language rules (important):
- When the user writes in Thai, ALWAYS answer in Thai. Every sentence of explanation must be Thai.
- Keep technical terms in English as-is: code, shell commands, file paths, error messages, library/model names, programming keywords. Do not translate them.
- When the user writes in another language, answer in that language.
- NEVER output Chinese characters unless the user writes in Chinese. If you catch yourself writing Chinese, rewrite that sentence in Thai.

Working method (how to be effective):
- For any task with more than ~2 steps, FIRST call todo_write to lay out a short plan, then work through it — mark each item in_progress before starting it and done when finished. Keep exactly one item in_progress at a time.
- Explore before you edit: use glob / grep / read_file to understand the code first. Make surgical changes — touch only what the task needs, don't refactor unrelated code.
- ALWAYS verify before saying a task is done — this is mandatory, not optional:
  1. Run the code (and its tests) via bash. If there are no tests and the task is non-trivial, write a quick one.
  2. Test edge cases and TRY TO BREAK IT — don't just run the happy path.
  3. If it produces output, check the output is actually CORRECT, not just that it ran without error. When a ground truth exists (a known-good result, a reference implementation, a spec), compare against it.
  4. Fix whatever breaks, then re-verify. Only say "done" after it passes.
  (See the self-check skill for the full procedure on substantial work.)
- Use the remember tool to save durable facts the user will want next time (their preferences, project conventions, decisions made). Don't save trivia.
- ask_user is your PREFERRED way to ask anything with a few likely answers. BEFORE you guess/assume a choice, or ask a question in prose, STOP and call ask_user with the options. Trigger it when: the request is ambiguous (e.g. "ทำเว็บให้หน่อย" → which kind/framework/style?), there are 2+ ways to do it, you need a preference (color/format/scope), or you're about to do something big or irreversible (confirm first). Give 2-5 concrete options (add multiple:true if several can apply). Example: ask_user(question="เว็บแบบไหน?", options=["Landing page","ร้านค้า","Dashboard","Blog"]). Don't use it for trivial things you can just do.
- For a MULTI-FILE project, output each file as a line `FILE: <relative/path>` immediately followed by a fenced code block containing the file's full content (do this for every file). The user can then save them all at once with /save — no need to call write_file per file.

Be concise. Format answers in Markdown."""

BASE_SYSTEM = SYSTEM  # เก็บ base ไว้ rebuild (เติม memory/skills/project) ได้ตอน /memory แก้


# ============================================================
# regex utilities (sanitize คำตอบโมเดล)
# ============================================================

# ลบ special token ที่บางโมเดล (เช่น gemma4 quant q4) ทำหลุดมาใน content
# จงใจเจาะจงเฉพาะ token พิเศษ ไม่แตะ <tag> ของ HTML/โค้ดที่โมเดลตั้งใจเขียน
# จับ token ที่ขึ้นต้น <| หรือ ลงท้าย |> (channel, tool_call, tool_response, im_start ฯลฯ)
# ปลอดภัยกับโค้ด: `a<b || c>d` ไม่โดน เพราะไม่ได้ขึ้นต้น <| หรือลงท้าย |>
_SPECIAL_TOK = re.compile(
    r"<\|[^<>]*>|<[^<>]*\|>|</?(?:start_of_turn|end_of_turn)>|<(?:eos|bos|pad|unused\d+)>"
)


def strip_special(text: str) -> str:
    return _SPECIAL_TOK.sub("", text)


# แยกไฟล์จากคำตอบที่มี marker `FILE: path` ตามด้วย code block (สำหรับ /save multi-file)
_FILE_BLOCK = re.compile(r"FILE:\s*([^\s\n]+)[^\n]*\n+```[a-zA-Z0-9]*\n(.*?)```", re.S)


def extract_files(text: str) -> list:
    return [(m.group(1).strip(), m.group(2)) for m in _FILE_BLOCK.finditer(text or "")]


def looks_toolish(text: str) -> bool:
    """เดาว่า content ที่ stream มากำลังจะเป็น tool call (ไว้กันไม่ให้ render เป็นข้อความ)"""
    s = text.lstrip()
    return (
        s.startswith("<tool_call>")
        or s.startswith("<function")
        or s.startswith("```json")
        or (s.startswith("{") and '"name"' in s)
    )


# ============================================================
# ฟังก์ชัน config
# ============================================================


def load_config() -> dict | None:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def save_config(cfg: dict) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.chmod(CONFIG_PATH, 0o600)  # มี api key อยู่ข้างใน


def longdoc_options(messages: list) -> dict:
    """กัน failure mode ของ context ยาว (เทสต์จริง @190k, 2026-06-06): เอกสารยาว
    ทำโมเดลวน loop ตอน generate ได้ — num_predict cap กันเสียหายไม่จำกัด.
    (เคยใส่ repeat_penalty 1.3 ด้วย แต่เทสซ้ำพบผลไม่นิ่ง: บาง doc ช่วย multi-hop
    บาง doc ไม่ช่วยแถมทำ recall รายการพัง 9/10→0/10 — ถอนออกจนกว่าจะมี data แน่นกว่า)"""
    chars = sum(len(str(m.get("content") or "")) for m in messages)
    if chars < LONGDOC_CHARS:
        return {}
    return {"num_predict": 4096}


def vote_consensus(backend, messages, first: str, intr=None) -> str | None:
    """เอกสารยาว + โมเดล local = คำตอบไม่นิ่งแม้ temp 0 (เทสต์ 2026-06-06: เงื่อนไขเดิมเป๊ะ
    รันซ้ำได้คนละคำตอบ/บางทีติด loop) → ถามซ้ำให้ครบ VOTE_ROUNDS รอบ — รอบ 2+ แทบฟรี
    เพราะ Ollama reuse KV cache ของ prefix เดิม. ตรงกันหมด = ผ่าน; ไม่ตรง = ส่ง 3 คำตอบ
    (prompt สั้น ไม่แนบ doc) ให้โมเดลตัดสินเสียงข้างมาก. คืนคำตอบใหม่ หรือ None = คงคำตอบแรก"""
    import httpx
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel

    console = Console()
    base = messages[:-1]  # ตัด assistant คำตอบแรกออก ให้ถามซ้ำจาก state เดิม
    opts = longdoc_options(base)
    if backend.num_ctx:
        opts["num_ctx"] = backend.num_ctx  # ต้องเท่าเดิม ไม่งั้น Ollama reload โมเดล
    answers = [first]
    for i in range(2, VOTE_ROUNDS + 1):
        if intr and intr.stopped():
            return None
        console.print(f"[dim]🗳 เช็คความนิ่ง รอบ {i}/{VOTE_ROUNDS}...[/]")
        try:
            r = httpx.post(
                f"{backend.api_base}/api/chat",
                json={
                    "model": backend.model,
                    "messages": base,
                    "stream": False,
                    "options": opts,
                },
                timeout=None,
                headers=getattr(backend, "headers", {}),
            )
            ans = strip_special(r.json().get("message", {}).get("content", ""))
            # รอบซ้ำอาจขอเรียก tool แทนการตอบ (history มี tool round) → ข้าม ไม่นับเป็นคำตอบ
            if ans.strip() and not looks_toolish(ans):
                answers.append(ans)
        except Exception:
            return None  # vote ล่ม → ใช้คำตอบแรกตามเดิม
    if len(answers) < 2:
        return None
    norm = {" ".join(a.split()) for a in answers}
    if len(norm) == 1:
        console.print(f"[dim]🗳 {len(answers)}/{VOTE_ROUNDS} รอบตอบตรงกัน[/]")
        return None
    q = next(
        (str(m.get("content") or "") for m in reversed(base) if m.get("role") == "user"),
        "",
    )[-1500:]
    arb = (
        "ส่วนท้ายของคำถาม:\n" + q + "\n\nคำตอบจากการถามคำถามเดียวกัน "
        + f"{len(answers)} รอบ (โมเดลเดียวกัน คำตอบไม่ตรงกัน):\n"
        + "\n\n".join(
            f"--- คำตอบที่ {i+1} ---\n{a}" for i, a in enumerate(answers)
        )
        + "\n\nจงเลือกคำตอบสุดท้ายที่น่าเชื่อถือที่สุด: ยึดเสียงข้างมาก "
        "ถ้าไม่มีเสียงข้างมากให้ยึดตัวที่เหตุผลภายในสอดคล้องที่สุด "
        "ตอบเป็นคำตอบสุดท้ายอย่างเดียว ไม่ต้องอธิบายการเลือก"
    )
    try:
        r = httpx.post(
            f"{backend.api_base}/api/chat",
            json={
                "model": backend.model,
                "messages": [{"role": "user", "content": arb}],
                "stream": False,
                "options": opts,
            },
            timeout=None,
            headers=getattr(backend, "headers", {}),
        )
        final = strip_special(r.json().get("message", {}).get("content", ""))
    except Exception:
        return None
    if not final.strip():
        return None
    console.print(
        Panel(
            Markdown(final),
            title=f"🗳 consensus จาก {len(answers)} รอบ",
            border_style=THEME["border"],
            title_align="left",
        )
    )
    return final


def apply_theme(name: str) -> None:
    if name in THEMES:
        THEME.update(name=name, **THEMES[name])


# ---------- TOOLS (schema สำหรับ Claude SDK + OpenAI function calls) ----------
TOOLS = [
    {
        "name": "bash",
        "description": "Run a bash command on the user's machine and return stdout/stderr. Call this for anything that needs the shell: git, installing packages, running scripts, system info.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The bash command to run"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read a text file and return its contents with line numbers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative file path"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a file with the given content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace an exact string in a file with a new string. old_string must appear exactly once in the file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_string": {"type": "string"},
                "new_string": {"type": "string"},
            },
            "required": ["path", "old_string", "new_string"],
        },
    },
    {
        "name": "glob",
        "description": "Find files matching a glob pattern, sorted by modification time (newest first). Call this to locate files before reading or editing them. Example patterns: '**/*.py', 'src/**/*.ts'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern, ** matches directories recursively"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "grep",
        "description": "Search file contents with a regex pattern (recursive, skips .git/.venv/node_modules). Returns matching lines as path:line:text. Call this to find where something is defined or used.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for"},
                "path": {"type": "string", "description": "Directory or file to search in (default: current directory)"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "web_search",
        "description": "Search the web (DuckDuckGo) and return result titles, URLs and SHORT snippets. The snippets are usually page descriptions, NOT the actual data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "web_fetch",
        "description": "Fetch a URL and return its text content (HTML stripped). Call this to read a specific page, often after web_search.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "todo_write",
        "description": "Create or update the task list (your plan). Pass the FULL list every time. Use it to plan multi-step work and track progress; keep exactly one task in_progress.",
        "input_schema": {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "task": {"type": "string"},
                            "status": {"type": "string", "enum": ["pending", "in_progress", "done"]},
                        },
                        "required": ["task", "status"],
                    },
                },
            },
            "required": ["todos"],
        },
    },
    {
        "name": "remember",
        "description": "Save one durable fact to persistent memory so it is available in future sessions. One concise fact per call.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fact": {"type": "string"},
            },
            "required": ["fact"],
        },
    },
    {
        "name": "use_skill",
        "description": "Load the full step-by-step instructions for a named skill. Call this BEFORE starting a task that matches a skill's description.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Skill name exactly as listed"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "ask_user",
        "description": "Ask the user a question and let them PICK from options. CALL THIS when the request is ambiguous or has 2+ reasonable options. Returns the user's choice.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "options": {"type": "array", "items": {"type": "string"}, "description": "2-5 options"},
                "multiple": {"type": "boolean", "description": "true = checkbox, false = radio"},
            },
            "required": ["question", "options"],
        },
    },
    {
        "name": "vision",
        "description": "Analyze an image file or URL and return a description/answer. Pass either a local file path or an image URL. If a question is provided, answer that question about the image.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path_or_url": {"type": "string", "description": "Local file path or URL of the image"},
                "question": {"type": "string", "description": "Optional: specific question about the image"},
            },
            "required": ["path_or_url"],
        },
    },
    {
        "name": "patch",
        "description": "Smart find-and-replace edit. Like edit_file but more flexible: tries multiple matching strategies (exact, whitespace-normalized, case-insensitive, partial). Use this when edit_file fails due to whitespace differences. Shows diff and asks for confirmation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to edit"},
                "old_string": {"type": "string", "description": "Text to find and replace"},
                "new_string": {"type": "string", "description": "Replacement text"},
                "replace_all": {"type": "boolean", "description": "Replace all occurrences (default: only first)"},
            },
            "required": ["path", "old_string", "new_string"],
        },
    },
    {
        "name": "search_files",
        "description": "Intelligent file search. Search file contents by regex (target='content') or find files by name/glob (target='files'). Faster than grep for large codebases. Use file_glob to filter by extension (e.g. '*.py').",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern (content search) or glob pattern (file search)"},
                "target": {"type": "string", "enum": ["content", "files"], "description": "Search inside files (content) or find files by name (files)"},
                "path": {"type": "string", "description": "Directory to search in (default: current)"},
                "file_glob": {"type": "string", "description": "Filter by file pattern e.g. '*.py' for content search"},
                "limit": {"type": "number", "description": "Max results (default: 50)"},
                "output_mode": {"type": "string", "enum": ["content", "files_only", "count"], "description": "Output format"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "subagent",
        "description": "Spawn a child agent to work on a task in the background while you continue the main conversation. Use this for tasks that can be done independently: research, file processing, data analysis, parallel coding. The subagent has tools: bash, read_file, write_file, grep, glob. Returns when complete.",
        "input_schema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "What the subagent should accomplish (be specific)"},
                "context": {"type": "string", "description": "Background info, file paths, constraints"},
            },
            "required": ["goal"],
        },
    },
]
