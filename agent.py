#!/usr/bin/env python3
"""BOYSER AI — agent ส่วนตัวแบบ Claude Code รันบนเครื่อง local.

รันครั้งแรกจะมีเมนูตั้งค่า (เลือก Claude API / Ollama / llama.cpp)
ตั้งค่าเก็บที่ ~/.config/boyser-ai/config.json

ใน REPL: พิมพ์ / เพื่อดูเมนูคำสั่ง · exit ออก
Tools: bash, read_file, write_file, edit_file, glob, grep, web_search, web_fetch
"""

import argparse
import difflib
import glob as globlib
import html as htmllib
import json
import os
import re
import subprocess
import sys
import time

import threading

import httpx
from rich.align import Align
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.live import Live
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

console = Console()

# ---------- shimmer "กำลังคิด" แบบสีวิ่งผ่านคำ (จับ combining marks ไทยไว้กับพยัญชนะ) ----------
_GRAPHEME = re.compile(r".[ัิ-ฺ็-๎]*")
_SHIMMER = ["grey35", "grey50", "grey66", "grey82", "white", "grey82", "grey66", "grey50", "grey35"]


def _shimmer_word(word: str, frame: int) -> Text:
    cells = _GRAPHEME.findall(word)
    center = frame % (len(cells) + 8)
    t = Text()
    for i, g in enumerate(cells):
        d = abs(i - center)
        t.append(g, style=_SHIMMER[d] if d < len(_SHIMMER) else "grey35")
    return t


class Thinking:
    """spinner 'กำลังคิด' แบบ shimmer สีวิ่ง + เวลา ขณะรอโมเดล (ไม่โชว์เนื้อหา thinking)"""

    LABEL = "กำลังคิด"

    def __init__(self):
        self.start = time.monotonic()
        self._frame = 0
        self._stop = threading.Event()
        self._animated = console.is_terminal
        self._thread = None
        if self._animated:
            self._live = Live(console=console, auto_refresh=False, transient=True)
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def _render(self) -> Text:
        elapsed = time.monotonic() - self.start
        head = Text("✻ ", style=THEME["accent"])
        head.append_text(_shimmer_word(self.LABEL, self._frame))
        head.append(f"  {elapsed:.0f}s", style="dim")
        return head

    def _run(self) -> None:
        with self._live:
            while not self._stop.is_set():
                self._frame += 1
                self._live.update(self._render(), refresh=True)
                time.sleep(0.08)

    def stop(self) -> None:
        if self._animated:
            self._stop.set()
            self._thread.join()

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


def apply_theme(name: str) -> None:
    if name in THEMES:
        THEME.update(name=name, **THEMES[name])

YOLO = False
ALWAYS_ALLOW: set = set()

import datetime

_THAI_DAYS = ["วันจันทร์", "วันอังคาร", "วันพุธ", "วันพฤหัสบดี", "วันศุกร์", "วันเสาร์", "วันอาทิตย์"]
_now = datetime.datetime.now()
TODAY = f"{_now.strftime('%A %Y-%m-%d')} ({_THAI_DAYS[_now.weekday()]})"

SYSTEM = f"""You are BOYSER AI, a helpful coding agent running on the user's local machine.
Working directory: {WORKDIR}
Current date: {TODAY} (run `date` via bash if you need the exact time)

Use your tools to complete tasks:
- bash: run shell commands (git, install, run scripts)
- read_file / write_file / edit_file: work with files; prefer edit_file for small changes
- glob / grep: explore the codebase before editing — find files by pattern, search content
- web_search / web_fetch: look up current information online. IMPORTANT: web_search returns only short snippets (often just page descriptions, not the actual data). If the snippets don't already contain the concrete answer (a price, a number, a date, a fact), you MUST web_fetch the most relevant result URL to read the real content BEFORE answering. Never answer a factual question with just a list of sources/links — fetch, then answer with the actual value and cite the source.

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
        "description": "Search the web (DuckDuckGo) and return result titles, URLs and SHORT snippets. The snippets are usually page descriptions, NOT the actual data — they rarely contain the concrete answer (e.g. a live price). Use this to find which pages to read, then call web_fetch on the best URL to get the real content. Do not answer a factual question from snippets alone.",
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
        "description": "Save one durable fact to persistent memory so it is available in future sessions (user preferences, project conventions, important decisions). One concise fact per call. Don't save trivia.",
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
        "description": "Load the full step-by-step instructions for a named skill (listed under 'Skills' in the system prompt). Call this BEFORE starting a task that matches a skill's description, then follow the loaded instructions.",
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
        "description": "Ask the user a question and let them PICK from options instead of plain text. CALL THIS whenever the request is ambiguous or has 2+ reasonable options/approaches, when you need a preference (which framework/color/format/scope), or to confirm before a big or irreversible action — INSTEAD of guessing or asking in prose. Example: ask_user(question='ใช้ framework ไหน?', options=['React','Vue','Vanilla JS']). Returns the user's choice.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "options": {"type": "array", "items": {"type": "string"}, "description": "2-5 ตัวเลือกให้ผู้ใช้กดเลือก"},
                "multiple": {"type": "boolean", "description": "true = เลือกได้หลายข้อ (checkbox); false = เลือกข้อเดียว"},
            },
            "required": ["question", "options"],
        },
    },
]


# ---------- config ----------

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


def _parse_frontmatter(path: str) -> tuple[dict, str]:
    """อ่าน frontmatter (--- key: value ---) → (meta, body)"""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return {}, ""
    meta = {}
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            for line in text[3:end].splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            body = text[end + 4:].lstrip()
    return meta, body


def discover_skills() -> dict:
    skills = {}
    for base in SKILLS_DIRS:
        if not os.path.isdir(base):
            continue
        for entry in sorted(os.listdir(base)):
            md = os.path.join(base, entry, "SKILL.md")
            if os.path.isfile(md):
                meta, _ = _parse_frontmatter(md)
                name = meta.get("name", entry)
                if name not in skills:  # project (ลิสต์ก่อน) ทับ global
                    skills[name] = {"path": md, "dir": os.path.dirname(md), "description": meta.get("description", "")}
    return skills


def use_skill(name: str) -> str:
    sk = SKILLS.get(name)
    if not sk:
        return f"Error: ไม่พบ skill '{name}'. ที่มี: {', '.join(SKILLS) or '(ไม่มี)'}"
    _, body = _parse_frontmatter(sk["path"])
    files = [fn for fn in sorted(os.listdir(sk["dir"])) if fn != "SKILL.md"]
    extra = f"\n\n[ไฟล์ประกอบใน {sk['dir']}: {', '.join(files)}]" if files else ""
    return body + extra


def build_system(base: str) -> tuple[str, list[str]]:
    """ประกอบ system prompt + โหลด memory, project context, รายการ skills"""
    global SKILLS
    SKILLS = discover_skills()
    parts = [base]
    loaded = []
    if SKILLS:
        lines = "\n".join(f"- {n}: {s['description']}" for n, s in SKILLS.items())
        parts.append(
            "\n# Skills (ความเชี่ยวชาญเฉพาะทาง)\n"
            "เมื่อ task ตรงกับ skill ด้านล่าง เรียก tool `use_skill` ด้วยชื่อนั้นเพื่อโหลดวิธีทำแบบเต็มก่อนลงมือ:\n"
            f"{lines}"
        )
        loaded.append(f"skills ({len(SKILLS)})")
    try:
        with open(MEMORY_FILE, encoding="utf-8") as f:
            mem = f.read().strip()
        if mem:
            parts.append(f"\n# Persistent memory (จำไว้ข้าม session)\n{mem}")
            loaded.append(f"memory ({mem.count(chr(10)) + 1} บรรทัด)")
    except OSError:
        pass
    for name in PROJECT_FILES:
        p = os.path.join(WORKDIR, name)
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as f:
                    parts.append(f"\n# Project context — {name}\n{f.read().strip()[:8000]}")
                loaded.append(name)
            except OSError:
                pass
            break
    return "\n".join(parts), loaded


def list_ollama_models(base_url: str) -> list[str]:
    try:
        r = httpx.get(base_url.replace("/v1", "/api/tags"), timeout=3)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def menu_select(title: str, choices: list[tuple[str, str]]) -> str:
    """เมนูเลือกด้วยลูกศร (questionary) — ถ้าไม่มี TTY ใช้พิมพ์เลขแทน"""
    if sys.stdin.isatty():
        import questionary

        q_choices = [
            questionary.Choice(title=f"{label}  {desc}" if desc else label, value=label)
            for label, desc in choices
        ]
        ans = questionary.select(title, choices=q_choices).ask()
        if ans is None:
            sys.exit(0)
        return ans
    console.print(f"\n[bold]{title}[/]")
    for i, (label, desc) in enumerate(choices, 1):
        console.print(f"  {i}. {label}  [dim]{desc}[/]")
    while True:
        ans = console.input("เลือกหมายเลข: ").strip()
        if ans.isdigit() and 1 <= int(ans) <= len(choices):
            return choices[int(ans) - 1][0]


def ask_text(title: str, default: str = "", password: bool = False) -> str:
    if sys.stdin.isatty():
        import questionary

        fn = questionary.password if password else questionary.text
        kwargs = {} if password else {"default": default}
        ans = fn(title, **kwargs).ask()
        if ans is None:
            sys.exit(0)
        return ans.strip() or default
    return console.input(f"{title} ").strip() or default


def ask_ctx(default: int = 16384) -> int:
    val = ask_text(
        "context window num_ctx (token · มากขึ้น = จำได้เยอะแต่กิน VRAM/ช้าลง):",
        default=str(default),
    )
    try:
        n = int(val.replace(",", "").strip())
        return n if n >= 512 else default
    except ValueError:
        return default


def ant_oauth_login() -> None:
    """ตรวจ ant CLI + login ถ้ายังไม่ได้ login (ครั้งเดียว — ant จำ profile บนดิสก์ให้เอง)"""
    import shutil

    if not shutil.which("ant"):
        console.print("[yellow]ยังไม่มี Anthropic CLI (`ant`) — ต้องติดตั้งก่อนใช้ OAuth:[/]")
        console.print("[dim]  mac:   brew install anthropics/tap/ant[/]")
        console.print("[dim]  go:    go install github.com/anthropics/anthropic-cli/cmd/ant@latest[/]")
        console.print("[dim]ติดตั้งแล้วพิมพ์  ! ant auth login  ในเซสชัน หรือเลือก OAuth ใหม่[/]")
        return
    try:  # logged in จริง = print-credentials ได้ token sk-ant-... (status คืน 0 เสมอ เชื่อไม่ได้)
        cred = subprocess.run(
            ["ant", "auth", "print-credentials", "--access-token"],
            capture_output=True, text=True, timeout=10,
        )
        if cred.stdout.strip().startswith("sk-ant"):
            console.print("[green]✓ login อยู่แล้ว (ant จำไว้ให้) — ใช้ได้เลย[/]")
            return
    except Exception:
        pass
    console.print("[cyan]จะเปิดเบราว์เซอร์ให้ login ครั้งเดียว (หลังจากนี้ ant จะจำไว้)…[/]")
    try:
        subprocess.run(["ant", "auth", "login"], timeout=300)
    except Exception as e:
        console.print(f"[red]login ไม่สำเร็จ: {e} — ลอง `! ant auth login` เองได้[/]")


def setup_wizard() -> dict:
    console.print(Panel.fit(
        "[bold bright_blue]✻ BOYSER AI[/] — ตั้งค่าครั้งแรก\n"
        "[dim]เลือกว่าจะใช้สมองจากที่ไหน (เปลี่ยนทีหลังได้ด้วย /model)[/]",
        border_style="bright_blue",
    ))

    backend = menu_select("เลือก backend:", [
        ("Claude API", "Claude ของ Anthropic — API key หรือ login"),
        ("Cloud API", "OpenRouter / Groq / DeepSeek / OpenAI / Gemini ฯลฯ (ใส่ key)"),
        ("Ollama", "โมเดล local ฟรี — ใช้เครื่องตัวเอง"),
        ("llama.cpp", "llama-server แบบ OpenAI-compatible"),
    ])

    if backend == "Claude API":
        model = menu_select("เลือกโมเดล:", CLAUDE_MODELS)
        auth = menu_select("วิธียืนยันตัวตน:", [
            ("API key", "วาง sk-ant-... (จ่ายตามใช้)"),
            ("OAuth login", "ไม่ต้องวาง key — ต้อง `ant auth login` ก่อน (ยังเป็น API auth ไม่ใช่ subscription)"),
        ])
        if auth == "API key":
            key = os.environ.get("ANTHROPIC_API_KEY", "")
            if key:
                console.print("[green]เจอ ANTHROPIC_API_KEY ใน environment แล้ว จะใช้ตัวนั้น[/]")
            else:
                key = ask_text("วาง API key (sk-ant-... จาก platform.claude.com):", password=True)
            cfg = {"backend": "claude", "model": model, "api_key": key}
        else:
            ant_oauth_login()  # เช็ค+login ให้ตรงนี้เลย (ครั้งแรก) — รอบหลัง ant จำไว้
            cfg = {"backend": "claude", "model": model}  # ไม่มี key → SDK ใช้ profile/env

    elif backend == "Cloud API":
        choices = [(n, u) for n, u in CLOUD_PROVIDERS.items()] + [("กำหนดเอง", "ใส่ base_url เอง")]
        prov = menu_select("เลือกผู้ให้บริการ:", choices)
        base = CLOUD_PROVIDERS.get(prov) or ask_text("base_url (OpenAI-compatible):", default="https://")
        key = ask_text(f"วาง API key ของ {prov}:", password=True)
        eg = {"OpenRouter": "anthropic/claude-sonnet-4.6", "Groq": "llama-3.3-70b-versatile",
              "DeepSeek": "deepseek-chat", "OpenAI": "gpt-4o", "Gemini": "gemini-2.0-flash"}.get(prov, "ชื่อโมเดล")
        model = ask_text(f"ชื่อโมเดล (เช่น {eg}):", default=eg)
        cfg = {"backend": "local", "base_url": base, "model": model, "api_key": key}

    elif backend == "Ollama":
        models = list_ollama_models(OLLAMA_URL)
        if models:
            model = menu_select("เลือกโมเดล (จาก ollama list):", [(m, "") for m in models])
        else:
            console.print(f"[yellow]ต่อ Ollama ที่ {OLLAMA_URL} ไม่ได้ — พิมพ์ชื่อโมเดลเอง[/]")
            model = ask_text("ชื่อโมเดล:", default="qwen3-coder-tools")
        cfg = {"backend": "local", "base_url": OLLAMA_URL, "model": model, "num_ctx": ask_ctx()}

    else:  # llama.cpp
        url = ask_text("URL ของ llama-server:", default=LLAMACPP_URL)
        model = ask_text("ชื่อโมเดล (llama.cpp ใส่อะไรก็ได้):", default="default")
        console.print("[dim]หมายเหตุ: llama.cpp กำหนด ctx ตอนรัน server (-c) เป็นหลัก ค่านี้ส่งไปเผื่อรองรับ[/]")
        cfg = {"backend": "local", "base_url": url, "model": model, "num_ctx": ask_ctx()}

    cfg["theme"] = menu_select("เลือกธีมสี:", [(n, "") for n in THEMES])
    save_config(cfg)
    console.print(f"[green]✓ บันทึกที่ {CONFIG_PATH}[/]\n")
    return cfg


# ---------- ui helpers ----------

def confirm(key: str) -> bool:
    """ถามยืนยันก่อนทำ action ที่แก้ไขเครื่อง (y / n / a = อนุญาต tool นี้ตลอด session)"""
    if YOLO or key in ALWAYS_ALLOW:
        return True
    intr = _active_interrupt
    try:
        if intr:
            intr.pause()  # กันไม่ให้ตัวดัก ESC แย่งปุ่ม y/n/a
        ans = console.input("  [yellow]ดำเนินการ? (y / n / a=อนุญาตตลอด)[/] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    finally:
        if intr:
            intr.resume()
    if ans == "a":
        ALWAYS_ALLOW.add(key)
        return True
    return ans == "y"


_active_interrupt = None  # Interrupt ที่ทำงานอยู่ (ให้ confirm() หยุดมันชั่วคราวได้)


class Interrupt:
    """ดักปุ่ม ESC ระหว่างโมเดลกำลังตอบ (อ่าน stdin ใน thread แยก) — กด ESC = หยุด turn นี้
    หยุดอ่านชั่วคราวได้ด้วย pause()/resume() เพื่อไม่แย่งปุ่มตอน input() ถาม y/n"""

    def __init__(self):
        self.event = threading.Event()
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._thread = None
        self._fd = None
        self._old = None

    def __enter__(self):
        global _active_interrupt
        if sys.stdin.isatty():
            import termios
            import tty

            try:
                self._fd = sys.stdin.fileno()
                self._old = termios.tcgetattr(self._fd)
                tty.setcbreak(self._fd)  # อ่านทีละปุ่มโดยไม่ต้องกด Enter
                self._thread = threading.Thread(target=self._run, daemon=True)
                self._thread.start()
            except Exception:
                self._old = None
        _active_interrupt = self
        return self

    def _run(self):
        import select

        while not self._stop.is_set():
            if self._paused.is_set():
                time.sleep(0.05)
                continue
            r, _, _ = select.select([sys.stdin], [], [], 0.1)
            if r and not self._paused.is_set():
                ch = os.read(self._fd, 1)
                if ch == b"\x1b":  # ESC
                    self.event.set()
                    return

    def stopped(self) -> bool:
        return self.event.is_set()

    def pause(self):
        """หยุดอ่านปุ่ม + คืนโหมด terminal ปกติ เพื่อให้ input() (ถาม y/n) ใช้ได้"""
        if self._old is None or not self._thread:
            return
        self._paused.set()
        import termios

        try:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old)
        except Exception:
            pass
        time.sleep(0.06)  # ให้ reader หลุดจาก select รอบปัจจุบันก่อน input()

    def resume(self):
        if self._old is None or not self._thread:
            return
        import tty

        try:
            tty.setcbreak(self._fd)
        except Exception:
            pass
        self._paused.clear()

    def __exit__(self, *a):
        global _active_interrupt
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.3)
        if self._old is not None:
            import termios

            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old)
        _active_interrupt = None


SESSION = {"in": 0, "out": 0, "cached": 0, "turns": 0, "started": 0.0, "rem_tokens": None, "reset_tokens": None}
_status_ctx: dict = {"backend": None, "on": False}


def git_branch() -> str:
    try:
        r = subprocess.run(
            ["git", "-C", WORKDIR, "branch", "--show-current"],
            capture_output=True, text=True, timeout=2,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def parse_reset_time(reset_str: str) -> str:
    if not reset_str:
        return ""
    if "T" in reset_str:
        try:
            s = reset_str.replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(s)
            now = datetime.datetime.now(datetime.timezone.utc)
            delta = dt - now
            seconds = int(delta.total_seconds())
            if seconds <= 0:
                return "0s"
            if seconds < 60:
                return f"{seconds}s"
            minutes = seconds // 60
            secs = seconds % 60
            if minutes < 60:
                return f"{minutes}m{secs}s"
            hours = minutes // 60
            mins = minutes % 60
            return f"{hours}h{mins}m"
        except Exception:
            if "T" in reset_str:
                parts = reset_str.split("T")
                if len(parts) > 1:
                    return parts[1].split(".")[0].rstrip("Z")
            return reset_str
    return reset_str


def format_tokens(tok_str: str) -> str:
    if not tok_str:
        return ""
    try:
        val = int(tok_str)
        if val >= 1_000_000:
            return f"{val / 1_000_000:.1f}M"
        if val >= 1_000:
            return f"{val / 1_000:.0f}k"
        return str(val)
    except Exception:
        return tok_str


def extract_rate_limits(headers) -> tuple[str | None, str | None]:
    if not headers:
        return None, None
    h_lower = {k.lower(): v for k, v in headers.items()}
    
    rem_tokens = None
    for k in ["anthropic-ratelimit-tokens-remaining", "x-ratelimit-remaining-tokens", "x-ratelimit-tokens-remaining"]:
        if k in h_lower:
            rem_tokens = h_lower[k]
            break
            
    reset_tokens = None
    for k in ["anthropic-ratelimit-tokens-reset", "x-ratelimit-reset-tokens", "x-ratelimit-tokens-reset"]:
        if k in h_lower:
            reset_tokens = h_lower[k]
            break
            
    return rem_tokens, reset_tokens


def build_statusline() -> str:
    b = _status_ctx.get("backend")
    parts = [b.name if b else "?"]
    br = git_branch()
    if br:
        parts.append(f"⎇ {br}")
    if SESSION["in"] or SESSION["out"]:
        parts.append(f"↑{SESSION['in']} ↓{SESSION['out']} tok")
    rem = SESSION.get("rem_tokens")
    reset = SESSION.get("reset_tokens")
    if rem or reset:
        lim_parts = []
        if rem:
            lim_parts.append(f"rem {format_tokens(rem)}")
        if reset:
            lim_parts.append(f"reset {parse_reset_time(reset)}")
        parts.append(" ".join(lim_parts))
    return "  ·  ".join(parts)


def usage_line(tokens_in: int, cached: int, tokens_out: int, elapsed: float) -> None:
    SESSION["in"] += tokens_in
    SESSION["out"] += tokens_out
    SESSION["cached"] += cached
    tps = tokens_out / elapsed if elapsed > 0 else 0
    cache_part = f" (+cache {cached})" if cached else ""
    console.print(
        f"[dim]   ⤷ in {tokens_in}{cache_part} · out {tokens_out} · {elapsed:.1f}s · {tps:.0f} tok/s[/]"
    )


def show_tool_call(name: str, tool_input: dict) -> None:
    arg = next(iter(tool_input.values()), "")
    if isinstance(arg, (list, dict)):
        arg = f"{len(arg)} รายการ"
    arg = str(arg).replace("\n", " ")
    if len(arg) > 80:
        arg = arg[:77] + "..."
    console.print(f"[bold {THEME['accent']}]⏺[/] [bold]{name}[/]([dim]{arg}[/])")


def show_tool_result(output: str) -> None:
    lines = output.splitlines() or [""]
    first = lines[0][:100]
    more = f" … (+{len(lines) - 1} บรรทัด)" if len(lines) > 1 else ""
    style = "red" if output.startswith("Error") else "dim"
    console.print(f"  [dim]⎿[/] [{style}]{first}{more}[/]")


def show_diff(path: str, old_text: str, new_text: str) -> None:
    diff = "\n".join(
        difflib.unified_diff(
            old_text.splitlines(), new_text.splitlines(),
            fromfile=path, tofile=path, lineterm="",
        )
    )
    if len(diff) > 4000:
        diff = diff[:4000] + "\n… (diff ยาว ตัดให้ดูบางส่วน)"
    console.print(Syntax(diff, "diff", theme="ansi_dark", background_color="default"))


# ---------- tool implementations ----------

def run_bash(command: str) -> str:
    if not confirm("bash"):
        return "Error: user denied this command."
    try:
        r = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=120, cwd=WORKDIR
        )
        out = (r.stdout + r.stderr).strip()
        return out[:20000] if out else f"(no output, exit code {r.returncode})"
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 120s."


def read_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        return "".join(f"{i + 1}\t{line}" for i, line in enumerate(lines[:2000]))
    except OSError as e:
        return f"Error: {e}"


def write_file(path: str, content: str) -> str:
    old = ""
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                old = f.read()
        except OSError:
            pass
    show_diff(path, old, content)
    if not confirm("write_file"):
        return "Error: user denied this write."
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Wrote {path}"
    except OSError as e:
        return f"Error: {e}"


def edit_file(path: str, old_string: str, new_string: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        return f"Error: {e}"
    n = text.count(old_string)
    if n == 0:
        return "Error: old_string not found in file."
    if n > 1:
        return f"Error: old_string appears {n} times; it must be unique."
    new_text = text.replace(old_string, new_string)
    show_diff(path, text, new_text)
    if not confirm("edit_file"):
        return "Error: user denied this edit."
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_text)
    return f"Edited {path}"


def glob_tool(pattern: str) -> str:
    try:
        matches = globlib.glob(pattern, recursive=True)
    except Exception as e:
        return f"Error: {e}"
    matches = [m for m in matches if "/.venv/" not in m and "/.git/" not in m]
    matches.sort(key=lambda m: os.path.getmtime(m) if os.path.exists(m) else 0, reverse=True)
    if not matches:
        return "(no files matched)"
    return "\n".join(matches[:100])


def grep_tool(pattern: str, path: str = ".") -> str:
    cmd = [
        "grep", "-rn", "-I", "-E", "-m", "5",
        "--exclude-dir=.git", "--exclude-dir=.venv", "--exclude-dir=node_modules",
        "--exclude-dir=__pycache__", "-e", pattern, path,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return "Error: grep timed out."
    if r.returncode == 2:
        return f"Error: {r.stderr.strip()}"
    lines = r.stdout.splitlines()
    if not lines:
        return "(no matches)"
    return "\n".join(lines[:100])


def web_search(query: str) -> str:
    try:
        from ddgs import DDGS

        results = DDGS().text(query, max_results=8)
    except Exception as e:
        return f"Error: {e}"
    if not results:
        return "(no results)"
    out = "\n\n".join(
        f"{r.get('title', '')}\n{r.get('href', '')}\n{r.get('body', '')}" for r in results
    )
    # snippet มักเป็นแค่คำโปรยไม่มีคำตอบจริง → ดึงเนื้อหาหน้าแรกที่ใช้ได้มาแนบเลย
    # (เผื่อโมเดลไม่ chain ไป web_fetch เอง) ลองสูงสุด 3 อันแรกจนกว่าจะได้เนื้อหาจริง
    for r in results[:3]:
        url = r.get("href", "")
        if not url:
            continue
        page = web_fetch(url)
        if not page.startswith("Error") and len(page) > 400:
            out += f"\n\n=== เนื้อหาจาก {url} ===\n{page[:3000]}"
            break
    return out


def web_fetch(url: str) -> str:
    try:
        r = httpx.get(
            url, follow_redirects=True, timeout=20,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"},
        )
        text = r.text
    except Exception as e:
        return f"Error: {e}"
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = htmllib.unescape(re.sub(r"[ \t]+", " ", text))
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    return text[:15000] if text else "(empty page)"


def parse_text_toolcalls(text: str) -> list:
    """fallback: โมเดล local บางตัวพ่น tool call เป็นข้อความ (parser ของ engine จับไม่ได้)
    ดักจับ 3 ฟอร์แมตยอดฮิต → คืน [{name, args(dict)}]"""
    s = text.strip()
    calls: list = []

    # A) ทั้งก้อนเป็น JSON tool call ก้อนเดียว (qwen2.5-coder) หรือใน ```json ... ```
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.S)
    candidate = fence.group(1) if fence else (s if s.startswith("{") else "")
    if candidate and '"name"' in candidate:
        try:
            o = json.loads(candidate)
            if isinstance(o, dict) and "name" in o:
                return [{"name": o["name"], "args": o.get("arguments") or o.get("parameters") or {}}]
        except json.JSONDecodeError:
            pass

    # B) <tool_call>{json}</tool_call> (Hermes/Qwen)
    for m in re.finditer(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", s, re.S):
        try:
            o = json.loads(m.group(1))
            calls.append({"name": o.get("name", ""), "args": o.get("arguments") or o.get("parameters") or {}})
        except json.JSONDecodeError:
            pass
    if calls:
        return calls

    # C) <function=NAME>...<parameter=KEY>VALUE...</...>  (ปิดด้วย </function> หรือ </tool_call> ก็ได้)
    for fm in re.finditer(r"<function=([^>\s]+)>(.*?)(?:</function>|</tool_call>|\Z)", s, re.S):
        name = fm.group(1).strip()
        args = {}
        for pm in re.finditer(
            r"<parameter=([^>\s]+)>\s*(.*?)\s*(?=<parameter=|</parameter>|</function>|</tool_call>|\Z)",
            fm.group(2), re.S,
        ):
            args[pm.group(1).strip()] = pm.group(2).strip()
        if name:
            calls.append({"name": name, "args": args})
    return calls


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


CURRENT_TODOS: list = []
_TODO_MARK = {"pending": ("○", "white"), "in_progress": ("◐", "yellow"), "done": ("●", "green")}


def render_todos(todos: list) -> None:
    body = Text()
    for t in todos:
        mark, color = _TODO_MARK.get(t.get("status", "pending"), ("○", "white"))
        line_style = "green strike" if t.get("status") == "done" else color
        body.append(f"{mark} ", style=color)
        body.append(t.get("task", "") + "\n", style=line_style)
    if body.plain.endswith("\n"):
        body.right_crop(1)
    console.print(Panel(body, title="แผนงาน", border_style="dim", title_align="left"))


def todo_write(todos: list) -> str:
    global CURRENT_TODOS
    CURRENT_TODOS = todos
    render_todos(todos)
    done = sum(1 for t in todos if t.get("status") == "done")
    return f"Plan updated ({done}/{len(todos)} done)."


def remember(fact: str) -> str:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d")
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"- [{stamp}] {fact.strip()}\n")
    return "บันทึกลง memory แล้ว (จะจำได้ใน session ต่อไป)"


def ask_user(question: str, options: list, multiple: bool = False) -> str:
    """ถามผู้ใช้แล้วให้เลือกจากตัวเลือก (radio/checkbox) + 'อื่นๆ พิมพ์เอง' — คืนค่าที่เลือกเป็น tool result"""
    console.print(f"\n[bold {THEME['accent']}]? {question}[/]")
    opts = [str(o) for o in (options or [])] + ["อื่นๆ (พิมพ์เอง)"]
    intr = _active_interrupt
    try:
        if intr:
            intr.pause()  # หยุดตัวดัก ESC ไม่ให้แย่งปุ่มตอนเลือกเมนู
        if not sys.stdin.isatty():
            for i, o in enumerate(opts, 1):
                console.print(f"  {i}. {o}")
            ans = console.input("เลือก (เลข/ข้อความ): ").strip()
            if ans.isdigit() and 1 <= int(ans) <= len(options or []):
                return opts[int(ans) - 1]
            return ans or "(ไม่เลือก)"
        import questionary

        if multiple:
            sel = questionary.checkbox(question, choices=opts).ask()
            if not sel:
                return "(ผู้ใช้ไม่เลือกอะไร)"
            out = []
            for s in sel:
                out.append((questionary.text("ระบุ:").ask() or "") if s.startswith("อื่นๆ") else s)
            return ", ".join(x for x in out if x) or "(ไม่เลือก)"
        sel = questionary.select(question, choices=opts).ask()
        if sel is None:
            return "(ผู้ใช้ยกเลิก)"
        if sel.startswith("อื่นๆ"):
            return questionary.text("ระบุ:").ask() or "(ว่าง)"
        return sel
    except (EOFError, KeyboardInterrupt):
        return "(ผู้ใช้ยกเลิก)"
    finally:
        if intr:
            intr.resume()


def read_memory_lines() -> list:
    try:
        with open(MEMORY_FILE, encoding="utf-8") as f:
            return [ln.rstrip("\n") for ln in f if ln.strip()]
    except OSError:
        return []


def write_memory_lines(lines: list) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))


def print_memory() -> None:
    lines = read_memory_lines()
    if not lines:
        console.print("[dim]ยังไม่มี memory[/]")
        return
    t = Table(show_header=False, box=None, padding=(0, 1))
    for i, ln in enumerate(lines, 1):
        t.add_row(f"[dim]{i}[/]", ln)
    console.print(Panel(t, title=f"memory ({len(lines)})", border_style=THEME["border"], title_align="left"))


def edit_memory() -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(MEMORY_FILE):
        open(MEMORY_FILE, "a").close()
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "nano"
    try:
        subprocess.call([editor, MEMORY_FILE])
    except Exception as e:
        console.print(f"[red]เปิด editor ({editor}) ไม่ได้: {e}[/]")


TOOL_FUNCS = {
    "bash": lambda i: run_bash(i["command"]),
    "read_file": lambda i: read_file(i["path"]),
    "write_file": lambda i: write_file(i["path"], i["content"]),
    "edit_file": lambda i: edit_file(i["path"], i["old_string"], i["new_string"]),
    "glob": lambda i: glob_tool(i["pattern"]),
    "grep": lambda i: grep_tool(i["pattern"], i.get("path", ".")),
    "web_search": lambda i: web_search(i["query"]),
    "web_fetch": lambda i: web_fetch(i["url"]),
    "todo_write": lambda i: todo_write(i["todos"]),
    "remember": lambda i: remember(i["fact"]),
    "use_skill": lambda i: use_skill(i["name"]),
    "ask_user": lambda i: ask_user(i["question"], i.get("options", []), i.get("multiple", False)),
}

# tool ที่ไม่ต้องโชว์บรรทัด ⏺/⎿ (มี UI ของตัวเอง)
_QUIET_TOOLS = {"todo_write", "ask_user"}


def execute_tool(name: str, tool_input: dict) -> str:
    quiet = name in _QUIET_TOOLS
    if not quiet:
        show_tool_call(name, tool_input)
    fn = TOOL_FUNCS.get(name)
    output = fn(tool_input) if fn else f"Error: unknown tool {name}"
    if not quiet:
        show_tool_result(output)
    return output


# ---------- backends ----------

class ClaudeBackend:
    def __init__(self, cfg: dict):
        import anthropic

        self.anthropic = anthropic
        self.model = cfg["model"]
        self.client = anthropic.Anthropic(api_key=cfg.get("api_key") or None)
        self.api_error = anthropic.APIError
        self.name = self.model
        self.label = self.model

    def new_messages(self) -> list:
        return []

    def turn(self, messages: list, intr=None) -> None:
        rounds = 0
        while True:
            rounds += 1
            if rounds > MAX_TOOL_ROUNDS:
                console.print(f"[red]⊘ หยุด: เรียก tool เกิน {MAX_TOOL_ROUNDS} รอบ (อาจติด loop)[/]")
                return
            start = time.monotonic()
            with self.client.messages.stream(
                model=self.model,
                max_tokens=32000,
                system=SYSTEM,
                tools=TOOLS,
                thinking={"type": "adaptive"},  # คิดเงียบๆ ข้างใน ไม่โชว์ (display omitted)
                cache_control={"type": "ephemeral"},  # cache ประวัติ ลดค่า token
                messages=messages,
            ) as stream:
                text = ""
                live = None
                think = Thinking()
                try:
                    for event in stream:
                        if intr and intr.stopped():
                            break
                        if event.type != "content_block_delta" or event.delta.type != "text_delta":
                            continue
                        if think:
                            think.stop()
                            think = None
                        if live is None:
                            live = Live(console=console, vertical_overflow="visible")
                            live.start()
                        text += event.delta.text
                        live.update(Markdown(text))
                finally:
                    if think:
                        think.stop()
                    if live:
                        live.stop()
                if intr and intr.stopped():
                    console.print("[dim]⊘ หยุดแล้ว (ESC)[/]")
                    messages.append({"role": "assistant", "content": text or "(หยุดโดยผู้ใช้)"})
                    return
                response = stream.get_final_message()
                try:
                    if hasattr(stream, "response") and hasattr(stream.response, "headers"):
                        rem_tok, reset_tok = extract_rate_limits(stream.response.headers)
                        if rem_tok:
                            SESSION["rem_tokens"] = rem_tok
                        if reset_tok:
                            SESSION["reset_tokens"] = reset_tok
                except Exception:
                    pass

            u = response.usage
            usage_line(u.input_tokens, u.cache_read_input_tokens, u.output_tokens, time.monotonic() - start)

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                return

            results = []
            for block in response.content:
                if block.type == "tool_use":
                    output = execute_tool(block.name, block.input)
                    results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": output}
                    )
            messages.append({"role": "user", "content": results})


class LocalBackend:
    OPENAI_TOOLS = [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in TOOLS
    ]

    def __init__(self, cfg: dict):
        import openai

        self.model = cfg["model"]
        self.num_ctx = cfg.get("num_ctx")
        self.client = openai.OpenAI(base_url=cfg["base_url"], api_key=cfg.get("api_key") or "local")
        self.api_error = openai.APIError
        # Ollama /v1 ไม่รับ num_ctx (reload ที่ค่า Modelfile เสมอ) → ตรวจว่าเป็น Ollama
        # เพื่อยิงผ่าน native /api/chat ที่ตั้ง num_ctx ได้จริง
        self.api_base = cfg["base_url"].rstrip("/")
        if self.api_base.endswith("/v1"):
            self.api_base = self.api_base[:-3].rstrip("/")
        self.is_ollama = False
        self.supports_think = False
        try:
            r = httpx.get(self.api_base + "/api/version", timeout=2)
            # ต้องเป็น Ollama จริง (status 200 + มี field version) — กัน cloud API ที่ตอบ 404 เฉยๆ
            if r.status_code == 200 and "version" in r.json():
                self.is_ollama = True
                caps = httpx.post(
                    self.api_base + "/api/show", json={"model": self.model}, timeout=5
                ).json().get("capabilities", [])
                self.supports_think = "thinking" in caps  # /think ส่ง think:true เฉพาะตัวที่รองรับ
        except Exception:
            pass
        ctx_tag = f" · ctx {self.num_ctx}" if self.num_ctx else ""
        self.name = self.model
        self.label = f"{self.model} @ {cfg['base_url']}{ctx_tag}"

    def new_messages(self) -> list:
        return [{"role": "system", "content": SYSTEM}]

    def _turn_ollama(self, messages: list, intr=None) -> None:
        """native /api/chat — ตั้ง num_ctx ได้จริง (ใช้ native message shape: tool_calls.arguments เป็น dict)"""
        rounds = 0
        prev_sig = ""
        while True:
            rounds += 1
            if rounds > MAX_TOOL_ROUNDS:
                console.print(f"[red]⊘ หยุด: เรียก tool เกิน {MAX_TOOL_ROUNDS} รอบ (อาจติด loop)[/]")
                return
            start = time.monotonic()
            payload = {
                "model": self.model,
                "messages": messages,
                "tools": self.OPENAI_TOOLS,
                "stream": True,
            }
            if THINK_ON and self.supports_think:
                payload["think"] = True  # /think เปิด → โมเดล reason ก่อน (spinner หมุนระหว่างคิด)
            if self.num_ctx:
                payload["options"] = {"num_ctx": self.num_ctx}

            content = ""
            calls: list = []
            usage = None
            live = None
            think = Thinking()
            try:
                with httpx.stream("POST", f"{self.api_base}/api/chat", json=payload, timeout=None) as r:
                    try:
                        rem_tok, reset_tok = extract_rate_limits(r.headers)
                        if rem_tok:
                            SESSION["rem_tokens"] = rem_tok
                        if reset_tok:
                            SESSION["reset_tokens"] = reset_tok
                    except Exception:
                        pass
                    for line in r.iter_lines():
                        if intr and intr.stopped():
                            break
                        if not line:
                            continue
                        o = json.loads(line)
                        msg = o.get("message", {})
                        if msg.get("content"):
                            content += msg["content"]
                            # ถ้าเดาว่าเป็น tool call ที่พ่นเป็นข้อความ → ไม่ render รอ parse ตอนจบ
                            if not looks_toolish(content):
                                if think:
                                    think.stop()
                                    think = None
                                if live is None:
                                    live = Live(console=console, vertical_overflow="visible")
                                    live.start()
                                live.update(Markdown(strip_special(content)))
                        for tc in msg.get("tool_calls") or []:
                            fn = tc.get("function", {})
                            calls.append({"name": fn.get("name", ""), "args": fn.get("arguments", {})})
                        if o.get("done"):
                            usage = (o.get("prompt_eval_count", 0), o.get("eval_count", 0))
            finally:
                if think:
                    think.stop()
                if live:
                    live.stop()

            if intr and intr.stopped():
                console.print("[dim]⊘ หยุดแล้ว (ESC)[/]")
                messages.append({"role": "assistant", "content": content or "(หยุดโดยผู้ใช้)"})
                return

            if usage:
                usage_line(usage[0], 0, usage[1], time.monotonic() - start)

            # fallback: ถ้า engine ไม่ได้แยก tool call ออกมา แต่โมเดลพ่นเป็นข้อความ → parse เอง
            if not calls and content.strip():
                parsed = parse_text_toolcalls(content)
                if parsed:
                    calls = parsed
                    content = ""
                elif live is None:
                    console.print(Markdown(strip_special(content)))

            assistant: dict = {"role": "assistant", "content": strip_special(content)}
            if calls:
                assistant["tool_calls"] = [{"function": {"name": c["name"], "arguments": c["args"]}} for c in calls]
            messages.append(assistant)

            if not calls:
                return

            sig = "|".join(f"{c['name']}:{json.dumps(c['args'], sort_keys=True, default=str)}" for c in calls)
            if sig and sig == prev_sig:  # เรียก tool เดิมซ้ำเป๊ะ = ติด loop → หยุดทันที
                console.print("[red]⊘ หยุด: โมเดลเรียก tool เดิมซ้ำ (ติด loop)[/]")
                return
            prev_sig = sig

            for c in calls:
                args = c["args"] if isinstance(c["args"], dict) else json.loads(c["args"] or "{}")
                output = execute_tool(c["name"], args)
                messages.append({"role": "tool", "tool_name": c["name"], "content": output})

    def turn(self, messages: list, intr=None) -> None:
        if self.is_ollama:
            return self._turn_ollama(messages, intr)  # native /api/chat → ตั้ง num_ctx ได้จริง
        rounds = 0
        while True:
            rounds += 1
            if rounds > MAX_TOOL_ROUNDS:
                console.print(f"[red]⊘ หยุด: เรียก tool เกิน {MAX_TOOL_ROUNDS} รอบ (อาจติด loop)[/]")
                return
            start = time.monotonic()
            raw_response = self.client.chat.completions.with_raw_response.create(
                model=self.model,
                messages=messages,
                tools=self.OPENAI_TOOLS,
                stream=True,
                stream_options={"include_usage": True},
            )
            try:
                rem_tok, reset_tok = extract_rate_limits(raw_response.headers)
                if rem_tok:
                    SESSION["rem_tokens"] = rem_tok
                if reset_tok:
                    SESSION["reset_tokens"] = reset_tok
            except Exception:
                pass
            stream = raw_response.parse()

            content = ""
            tool_calls: dict[int, dict] = {}  # ประกอบ tool call จากชิ้นส่วนใน stream
            usage = None
            live = None
            think = Thinking()
            try:
                for chunk in stream:
                    if intr and intr.stopped():
                        break
                    if getattr(chunk, "usage", None):
                        usage = chunk.usage
                    if not chunk.choices:
                        continue
                    d = chunk.choices[0].delta

                    if d.content:
                        content += d.content
                        if not looks_toolish(content):  # กัน tool call ที่พ่นเป็นข้อความ
                            if think:
                                think.stop()
                                think = None
                            if live is None:
                                live = Live(console=console, vertical_overflow="visible")
                                live.start()
                            live.update(Markdown(strip_special(content)))

                    if d.tool_calls:
                        for tc in d.tool_calls:
                            e = tool_calls.setdefault(tc.index, {"id": "", "name": "", "args": ""})
                            if tc.id:
                                e["id"] = tc.id
                            if tc.function:
                                e["name"] += tc.function.name or ""
                                e["args"] += tc.function.arguments or ""
            finally:
                if think:
                    think.stop()
                if live:
                    live.stop()

            if intr and intr.stopped():
                console.print("[dim]⊘ หยุดแล้ว (ESC)[/]")
                messages.append({"role": "assistant", "content": content or "(หยุดโดยผู้ใช้)"})
                return

            if usage:
                usage_line(usage.prompt_tokens, 0, usage.completion_tokens, time.monotonic() - start)

            # fallback: บาง local model พ่น tool call เป็นข้อความ → parse เอง
            if not tool_calls and content.strip():
                parsed = parse_text_toolcalls(content)
                if parsed:
                    for i, p in enumerate(parsed):
                        tool_calls[i] = {"id": f"call_{i}", "name": p["name"], "args": json.dumps(p["args"])}
                    content = ""
                elif live is None:
                    console.print(Markdown(strip_special(content)))  # นึกว่า toolish แต่เป็นคำตอบ → โชว์

            calls = [tool_calls[i] for i in sorted(tool_calls)]
            assistant: dict = {"role": "assistant", "content": strip_special(content)}
            if calls:
                assistant["tool_calls"] = [
                    {
                        "id": c["id"] or f"call_{i}",
                        "type": "function",
                        "function": {"name": c["name"], "arguments": c["args"]},
                    }
                    for i, c in enumerate(calls)
                ]
            messages.append(assistant)

            if not calls:
                return

            for i, c in enumerate(calls):
                try:
                    args = json.loads(c["args"] or "{}")
                except json.JSONDecodeError:
                    output = "Error: invalid JSON in tool arguments."
                else:
                    output = execute_tool(c["name"], args)
                messages.append(
                    {"role": "tool", "tool_call_id": c["id"] or f"call_{i}", "content": output}
                )


def make_backend(cfg: dict):
    return ClaudeBackend(cfg) if cfg["backend"] == "claude" else LocalBackend(cfg)


# ---------- slash commands + input ----------

SLASH_COMMANDS = {
    "/help": "ดูวิธีใช้และรายการคำสั่ง",
    "/clear": "ล้างประวัติบทสนทนา",
    "/model": "เปลี่ยนโมเดล / backend (เมนูตั้งค่าใหม่)",
    "/ctx": "ตั้งขนาด context window — เช่น /ctx 32768 (เฉพาะโมเดล local)",
    "/theme": "เปลี่ยนธีมสี",
    "/skills": "ดู skills ที่มี",
    "/memory": "ดู/แก้/ลบ ความจำข้าม session",
    "/save": "บันทึกไฟล์หลายไฟล์จากคำตอบล่าสุด (ที่มี FILE: markers)",
    "/tools": "ดูรายการ tools ทั้งหมด",
    "/status": "สรุปสถานะ session (model, tokens, git, ฯลฯ)",
    "/statusline": "เปิด/ปิด status line ที่ก้นกล่องพิมพ์",
    "/think": "เปิด/ปิดให้โมเดล local คิดก่อนตอบ (ช้าลงแต่ฉลาดขึ้น)",
    "/yolo": "เปิด/ปิดโหมดไม่ถามยืนยัน",
    "/exit": "ออกจากโปรแกรม",
}


def make_prompt():
    """ช่องพิมพ์แบบกล่องมีกรอบ (เหมือน Claude Code): ❯ ในกรอบ + เมนู / เด้ง + hint ล่าง
    ไม่มี TTY → ใช้ input() ธรรมดา"""
    if not sys.stdin.isatty():
        return lambda *a: input("\n> ")

    from prompt_toolkit.application import Application
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Float, FloatContainer, HSplit, Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.layout.menus import CompletionsMenu
    from prompt_toolkit.styles import DynamicStyle, Style
    from prompt_toolkit.widgets import Frame, TextArea

    class SlashCompleter(Completer):
        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            if text.startswith("/") and " " not in text:
                for cmd, desc in SLASH_COMMANDS.items():
                    if cmd.startswith(text):
                        yield Completion(cmd, start_position=-len(text), display=cmd, display_meta=desc)

    os.makedirs(CONFIG_DIR, exist_ok=True)
    state = {"label": ""}

    ta = TextArea(
        prompt=[("class:arrow", "❯ ")],
        multiline=False,
        wrap_lines=True,
        completer=SlashCompleter(),
        complete_while_typing=True,
        history=FileHistory(HISTORY_PATH),
    )

    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        b = ta.buffer
        if b.complete_state and b.complete_state.current_completion:
            b.apply_completion(b.complete_state.current_completion)  # เลือกเมนูก่อน ค่อย submit รอบหน้า
        else:
            event.app.exit(result=b.text)

    @kb.add("c-c")
    def _(event):
        event.app.exit(exception=KeyboardInterrupt)

    @kb.add("c-d")
    def _(event):
        if not ta.text:
            event.app.exit(exception=EOFError)

    def hint():
        if state.get("sl"):
            return [("class:hint", f"  {state['sl']}  ·  / · ESC หยุด")]
        return [("class:hint", f"  {state['label']}  ·  พิมพ์ / ดูคำสั่ง · ESC หยุด · Ctrl+C ออก")]

    root = FloatContainer(
        content=HSplit([Frame(ta), Window(FormattedTextControl(hint), height=1)]),
        floats=[Float(xcursor=True, ycursor=True, content=CompletionsMenu(max_height=8, scroll_offset=1))],
    )
    def build_style():  # อ่าน THEME สดทุกครั้ง → /theme เปลี่ยนสีกล่องได้ทันที
        a = THEME["accent"]
        return Style.from_dict({
            "arrow": f"{a} bold",
            "frame.border": THEME["border"],
            "hint": "#666666",
            "completion-menu.completion": "bg:#222222 #bbbbbb",
            "completion-menu.completion.current": f"bg:{a} #000000",
            "completion-menu.meta.completion": "bg:#222222 #777777",
            "completion-menu.meta.completion.current": f"bg:{a} #000000",
        })

    # erase_when_done = พอกด Enter กล่องหายไป (ไม่ค้างเป็นกล่องซ้ำ) แล้วเราพิมพ์ข้อความที่ส่งเองทีหลัง
    app = Application(
        layout=Layout(root, focused_element=ta), key_bindings=kb,
        style=DynamicStyle(build_style), erase_when_done=True,
    )

    def read(label=""):
        state["label"] = label
        state["sl"] = build_statusline() if _status_ctx.get("on") else ""  # คำนวณครั้งเดียวต่อ prompt
        ta.text = ""
        return app.run() or ""

    return read


def print_help(backend) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    for cmd, desc in SLASH_COMMANDS.items():
        table.add_row(f"[bold cyan]{cmd}[/]", desc)
    console.print(Panel(table, title="คำสั่ง", border_style="dim"))
    console.print(f"[dim]model: {backend.label} · config: {CONFIG_PATH}[/]")


def print_tools() -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    for t in TOOLS:
        table.add_row(f"[bold {THEME['accent']}]{t['name']}[/]", t["description"].split(".")[0])
    console.print(Panel(table, title="Tools", border_style="dim"))


def _fmt_dur(sec: float) -> str:
    sec = int(sec)
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return (f"{h}ชม " if h else "") + (f"{m}น " if m or h else "") + f"{s}วิ"


def print_status(backend, cfg: dict, loaded: list) -> None:
    a = THEME["accent"]
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_row("model", f"[bold {a}]{backend.name}[/]")
    ctx = f"  · ctx {backend.num_ctx}" if getattr(backend, "num_ctx", None) else ""
    t.add_row("backend", cfg["backend"] + ctx)
    br = git_branch()
    t.add_row("cwd", WORKDIR + (f"   ⎇ {br}" if br else ""))
    t.add_row("theme", THEME["name"])
    t.add_row("think", "เปิด" if THINK_ON else "ปิด")
    t.add_row("skills / tools", f"{len(SKILLS)} / {len(TOOL_FUNCS)}")
    if loaded:
        t.add_row("loaded", ", ".join(loaded))
    up = time.monotonic() - SESSION["started"] if SESSION["started"] else 0
    t.add_row("session", f"{SESSION['turns']} turns · {_fmt_dur(up)}")
    t.add_row("tokens", f"↑ {SESSION['in']}   ↓ {SESSION['out']}   (cache {SESSION['cached']})")
    rem = SESSION.get("rem_tokens")
    reset = SESSION.get("reset_tokens")
    if rem or reset:
        lim_str = ""
        if rem:
            lim_str += f"rem {rem} ({format_tokens(rem)})"
        if reset:
            if lim_str:
                lim_str += " · "
            lim_str += f"reset {parse_reset_time(reset)} ({reset})"
        t.add_row("rate limits", lim_str)
    t.add_row("config", CONFIG_PATH)
    console.print(Panel(t, title="status", border_style=THEME["border"], title_align="left"))


# ---------- main ----------

def main() -> None:
    global YOLO
    parser = argparse.ArgumentParser(description="BOYSER AI — mini Claude Code")
    parser.add_argument("--local", nargs="?", const=OLLAMA_URL, default=None, metavar="BASE_URL",
                        help="ข้าม config ใช้โมเดล local ชั่วคราว")
    parser.add_argument("--model", help="ชื่อโมเดล (ใช้คู่ --local)")
    parser.add_argument("--setup", action="store_true", help="เปิดเมนูตั้งค่าใหม่")
    parser.add_argument("--yolo", action="store_true", help="ไม่ถามยืนยันก่อนรัน tool (ระวัง!)")
    args = parser.parse_args()
    YOLO = args.yolo

    # ---- เลือก config: flag ชั่วคราว > ไฟล์ config > เมนูตั้งค่าครั้งแรก ----
    if args.local:
        if not args.model:
            sys.exit("ต้องระบุ --model ด้วย เช่น --model qwen3-coder-tools")
        cfg = {"backend": "local", "base_url": args.local, "model": args.model}
    else:
        cfg = load_config()
        if cfg is None or args.setup:
            cfg = setup_wizard()

    apply_theme(cfg.get("theme", "ฟ้า"))
    global THINK_ON
    THINK_ON = cfg.get("think", False)

    global SYSTEM
    SYSTEM, loaded = build_system(BASE_SYSTEM)

    backend = make_backend(cfg)
    messages = backend.new_messages()
    read_input = make_prompt()
    SESSION["started"] = time.monotonic()
    _status_ctx["backend"] = backend
    _status_ctx["on"] = cfg.get("statusline", False)

    def show_banner():
        accent = THEME["accent"]
        logo_w = max((len(line) for line in LOGO.splitlines()), default=0)
        if console.size.width >= logo_w + 6:  # จอกว้างพอ → โลโก้ใหญ่
            head = Align.center(Text(LOGO, style=f"bold {accent}", no_wrap=True))
        else:  # จอแคบ → ชื่อเล็กกันล้น
            head = Align.center(Text("✻ BOYSER AI", style=f"bold {accent}"))
        details = Text()
        rows = [("model", backend.name), ("cwd", WORKDIR)]
        if loaded:
            rows.append(("loaded", ", ".join(loaded)))
        for k, v in rows:
            details.append(f"{k:<7}", style="dim")
            details.append(v + "\n")
        details.append("พิมพ์ ", style="dim")
        details.append("/", style=f"bold {accent}")
        details.append(" ดูคำสั่ง · ", style="dim")
        details.append("exit", style=f"bold {accent}")
        details.append(" ออก", style="dim")
        if YOLO:
            details.append("  · YOLO MODE", style="bold red")
        body = Group(head, Text(), details)
        # Panel (ไม่ใช่ .fit) → ยืดเต็มความกว้างจอเหมือนกล่องแชต
        console.print(Panel(body, border_style=THEME["border"], padding=(1, 2)))

    show_banner()

    while True:
        try:
            user = (read_input(backend.name) if sys.stdin.isatty() else read_input()).strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user:
            continue
        if sys.stdin.isatty():  # กล่องถูกลบไปแล้ว → โชว์ข้อความที่ส่งเป็นบรรทัดสะอาดๆ
            console.print(Text("❯ ", style=f"bold {THEME['accent']}") + Text(user))
        if user.lower() in ("exit", "quit", "/exit"):
            break
        if user == "/help":
            print_help(backend)
            continue
        if user == "/theme":
            name = menu_select("เลือกธีมสี:", [(n, "ปัจจุบัน" if n == THEME["name"] else "") for n in THEMES])
            apply_theme(name)
            cfg["theme"] = name
            save_config(cfg)
            console.clear()
            show_banner()
            console.print(f"[{THEME['accent']}]เปลี่ยนธีมเป็น {name} แล้ว[/]")
            continue
        if user == "/memory":
            action = menu_select("จัดการ memory:", [
                ("ดู", ""), ("แก้ไข (editor)", ""), ("ลบทีละรายการ", ""),
                ("ล้างทั้งหมด", ""), ("ยกเลิก", ""),
            ])
            changed = False
            if action == "ดู":
                print_memory()
            elif action == "แก้ไข (editor)":
                edit_memory()
                changed = True
            elif action == "ลบทีละรายการ":
                lines = read_memory_lines()
                if not lines:
                    console.print("[dim]ยังไม่มี memory[/]")
                else:
                    pick = menu_select("ลบรายการไหน:", [(ln, "") for ln in lines] + [("(ยกเลิก)", "")])
                    if pick != "(ยกเลิก)" and pick in lines:
                        lines.remove(pick)
                        write_memory_lines(lines)
                        changed = True
                        console.print("[dim]ลบแล้ว[/]")
            elif action == "ล้างทั้งหมด":
                if console.input("  [yellow]ล้าง memory ทั้งหมด? (y/N)[/] ").strip().lower() == "y":
                    write_memory_lines([])
                    changed = True
                    console.print("[dim]ล้าง memory แล้ว[/]")
            if changed:  # โหลด memory ใหม่เข้า context (ล้างแชตให้ system prompt ใหม่มีผล)
                SYSTEM, loaded = build_system(BASE_SYSTEM)
                messages = backend.new_messages()
                console.print("[dim]โหลด memory ใหม่เข้า session แล้ว (ประวัติแชตถูกล้าง)[/]")
            continue
        if user == "/think":
            THINK_ON = not THINK_ON
            cfg["think"] = THINK_ON
            save_config(cfg)
            if THINK_ON and getattr(backend, "is_ollama", False) and not backend.supports_think:
                console.print(f"[yellow]think: เปิดแล้ว แต่ {backend.name} ไม่รองรับ thinking — ลองโมเดลอื่น เช่น gemma/glm[/]")
            else:
                console.print(f"[{THEME['accent'] if THINK_ON else 'dim'}]think mode: {'เปิด — โมเดลจะคิดก่อนตอบ' if THINK_ON else 'ปิด'}[/]")
            continue
        if user == "/status":
            print_status(backend, cfg, loaded)
            continue
        if user == "/statusline":
            on = not cfg.get("statusline", False)
            cfg["statusline"] = on
            _status_ctx["on"] = on
            save_config(cfg)
            console.print(f"[{THEME['accent'] if on else 'dim'}]status line: {'เปิด' if on else 'ปิด'}[/]")
            continue
        if user == "/skills":
            if not SKILLS:
                console.print(f"[dim]ยังไม่มี skill — สร้างที่ {SKILLS_DIRS[1]}/<ชื่อ>/SKILL.md[/]")
            else:
                table = Table(show_header=False, box=None, padding=(0, 2))
                for n, s in SKILLS.items():
                    table.add_row(f"[bold {THEME['accent']}]{n}[/]", s["description"])
                console.print(Panel(table, title="Skills", border_style="dim"))
            continue
        if user == "/save":
            # รวม FILE: จากทุกข้อความ assistant ในบทสนทนา (โมเดลอาจทยอยออกหลาย turn) — path ซ้ำ เอาอันล่าสุด
            seen = {}
            for m in messages:
                if m.get("role") == "assistant":
                    c = m.get("content", "")
                    t = c if isinstance(c, str) else "".join(
                        getattr(b, "text", "") for b in c if getattr(b, "type", None) == "text"
                    )
                    for path, content in extract_files(t):
                        seen[path] = content
            files = list(seen.items())
            if not files:
                console.print("[yellow]ไม่เจอไฟล์ในคำตอบล่าสุด — ให้โมเดลออกแต่ละไฟล์เป็น `FILE: path` ตามด้วย code block[/]")
                continue
            console.print(f"[bold]เจอ {len(files)} ไฟล์:[/]")
            for p, c in files:
                console.print(f"  [{THEME['accent']}]{p}[/] [dim]({c.count(chr(10)) + 1} บรรทัด)[/]")
            if console.input("  [yellow]บันทึกทั้งหมดลง cwd? (y/N)[/] ").strip().lower() == "y":
                for p, c in files:
                    try:
                        ap = p if os.path.isabs(p) else os.path.join(WORKDIR, p)
                        os.makedirs(os.path.dirname(os.path.abspath(ap)), exist_ok=True)
                        with open(ap, "w", encoding="utf-8") as f:
                            f.write(c)
                        console.print(f"  [green]✓[/] {p}")
                    except OSError as e:
                        console.print(f"  [red]✗ {p}: {e}[/]")
            continue
        if user == "/tools":
            print_tools()
            continue
        if user == "/clear":
            messages = backend.new_messages()
            SESSION.update(**{"in": 0, "out": 0, "cached": 0, "turns": 0, "started": time.monotonic(), "rem_tokens": None, "reset_tokens": None})
            console.clear()  # ล้างหน้าจอเหมือนพิมพ์ clear
            show_banner()
            console.print("[dim]ล้างหน้าจอ ประวัติ และตัวนับ token แล้ว[/]")
            continue
        if user == "/yolo":
            YOLO = not YOLO
            console.print(f"[{'red' if YOLO else 'green'}]YOLO mode: {'ON — ไม่ถามยืนยันแล้ว' if YOLO else 'OFF'}[/]")
            continue
        if user == "/model":
            cfg = setup_wizard()
            apply_theme(cfg.get("theme", THEME["name"]))
            backend = make_backend(cfg)
            _status_ctx["backend"] = backend
            messages = backend.new_messages()
            console.print(f"[green]เปลี่ยนเป็น {backend.label} แล้ว (ประวัติถูกล้าง)[/]")
            continue
        if user.startswith("/ctx"):
            if cfg["backend"] != "local":
                console.print("[yellow]/ctx ใช้ได้เฉพาะโมเดล local (Claude ctx 1M คงที่)[/]")
                continue
            parts = user.split()
            if len(parts) < 2 or not parts[1].replace(",", "").isdigit():
                console.print(f"[dim]ตอนนี้ num_ctx = {cfg.get('num_ctx', 'default')} · ใช้: /ctx 32768[/]")
                continue
            cfg["num_ctx"] = int(parts[1].replace(",", ""))
            save_config(cfg)
            backend = make_backend(cfg)  # ประวัติคงไว้ ไม่ต้องล้าง
            console.print(f"[green]ตั้ง num_ctx = {cfg['num_ctx']} แล้ว (ใช้ตั้งแต่ข้อความถัดไป)[/]")
            continue
        if user.startswith("/"):
            console.print("[yellow]ไม่รู้จักคำสั่งนี้ — พิมพ์ /help[/]")
            continue

        messages.append({"role": "user", "content": user})
        SESSION["turns"] += 1
        try:
            with Interrupt() as intr:  # กด ESC ระหว่างตอบ = หยุด
                backend.turn(messages, intr)
        except KeyboardInterrupt:
            console.print("\n[yellow]ยกเลิก turn นี้[/]")
            while messages and messages[-1].get("role") != "user":
                messages.pop()
            if messages and messages[-1].get("role") == "user":
                messages.pop()
        except backend.api_error as e:
            msg = str(getattr(e, "message", e))
            console.print(f"\n[red]API error: {msg}[/]")
            low = msg.lower()
            if "credit balance" in low or "billing" in low:
                console.print("[yellow]→ บัญชี Anthropic เครดิต API หมด/ไม่พอ[/] [dim]เติมที่ console.anthropic.com → Plans & Billing[/]")
                console.print("[dim]  ทางเลือกฟรี: /model → Ollama (local) · หรือ Cloud → OpenRouter[/]")
            elif "authentication" in low or "x-api-key" in low or "credential" in low:
                console.print("[yellow]→ ยืนยันตัวตนไม่ผ่าน[/] [dim]เช็ค API key หรือ `! ant auth login` ใหม่[/]")
            while messages and messages[-1].get("role") != "user":
                messages.pop()
            if messages and messages[-1].get("role") == "user":
                messages.pop()  # เอา turn ที่พังออก ให้ลองใหม่ได้


if __name__ == "__main__":
    main()
