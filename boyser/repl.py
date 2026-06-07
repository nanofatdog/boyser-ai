"""REPL input with prompt_toolkit, slash commands, @ file mentions.

Extracted from agent.py — exported symbols for CLI input/display.
"""

import difflib
import os
import re
import subprocess
import sys
import time

import datetime

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

console = Console()


def extract_rate_limits(headers) -> tuple:
    """ดึง rate limit headers จาก response — รองรับหลาย naming convention"""
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


# ---------- globals (set by caller at runtime) ----------

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
    "/vote": "เปิด/ปิด vote 3 รอบบนเอกสารยาว (กันคำตอบไม่นิ่งของโมเดล local)",
    "/update": "อัปเดต BOYSER AI เป็นเวอร์ชันล่าสุดจาก GitHub",
    "/yolo": "เปิด/ปิดโหมดไม่ถามยืนยัน",
    "/exit": "ออกจากโปรแกรม",
}

_FILE_SCAN: dict = {"t": 0.0, "files": []}
_SCAN_SKIP: set = {".git", "node_modules", "__pycache__", ".venv", "venv", ".cache", "dist", "build"}

_MENTION_RE = re.compile(r"@([\w./+~-]+)", re.UNICODE)

WORKDIR: str = os.getcwd()
REPO_DIR: str = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR: str = os.path.expanduser("~/.config/boyser-ai")
CONFIG_PATH: str = os.path.join(CONFIG_DIR, "config.json")
HISTORY_PATH: str = os.path.join(CONFIG_DIR, "history")

THEMES: dict = {
    "ฟ้า": {"accent": "#22b8e6", "border": "#5fafff"},
    "เขียว": {"accent": "#56d364", "border": "#3fb950"},
    "ม่วง": {"accent": "#a371f7", "border": "#bc8cff"},
    "ส้ม": {"accent": "#ff9e3d", "border": "#ff8700"},
    "ชมพู": {"accent": "#ff79c6", "border": "#ff87d7"},
    "ขาวดำ": {"accent": "#dddddd", "border": "#888888"},
}
THEME: dict = {"name": "ฟ้า", **THEMES["ฟ้า"]}
THINK_ON: bool = False
VOTE_ON: bool = True

SESSION: dict = {"in": 0, "out": 0, "cached": 0, "turns": 0, "started": 0.0, "rem_tokens": None, "reset_tokens": None}
_status_ctx: dict = {"backend": None, "on": False}

TOOLS: list = []
TOOL_FUNCS: dict = {}
SKILLS: dict = {}
SKILLS_DIRS: list = [os.path.join(WORKDIR, ".boyser", "skills"), os.path.join(CONFIG_DIR, "skills")]


# ---------- scanned functions — copied verbatim from agent.py ----------


def scan_files(limit: int = 2000) -> list:
    """รายชื่อไฟล์ใต้ cwd สำหรับ @ autocomplete (ข้าม dir ขยะ/ซ่อน) — cache 5 วิ"""
    if time.time() - _FILE_SCAN["t"] < 5:
        return _FILE_SCAN["files"]
    out = []
    for dirpath, dirnames, filenames in os.walk("."):
        dirnames[:] = sorted(d for d in dirnames if d not in _SCAN_SKIP and not d.startswith("."))
        for f in sorted(filenames):
            if f.startswith("."):
                continue
            out.append(os.path.join(dirpath, f)[2:])  # ตัด ./ หน้า path
            if len(out) >= limit:
                break
        if len(out) >= limit:
            break
    _FILE_SCAN.update(t=time.time(), files=out)
    return out


def expand_file_mentions(text: str):
    """แปลง @path ที่เป็นไฟล์จริงเป็นเนื้อไฟล์แนบท้ายข้อความ → (ข้อความส่งโมเดล, [ไฟล์ที่แนบ])"""
    attached, parts = [], [text]
    for m in _MENTION_RE.finditer(text):
        p = m.group(1).rstrip(".")  # กัน "@a.py." ท้ายประโยค
        if p in attached or not os.path.isfile(p):
            continue
        try:
            data = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if len(data) > 100_000:
            data = data[:100_000] + "\n... (ไฟล์ยาว ตัดที่ 100k ตัวอักษร — ใช้ tool อ่านส่วนที่เหลือ)"
        attached.append(p)
        parts.append(f"\n--- เนื้อไฟล์ {p} (user แนบด้วย @) ---\n{data}\n--- จบไฟล์ {p} ---")
    return "\n".join(parts), attached


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
                return
            # @ไฟล์ (แนบเนื้อไฟล์) หรือ ./path (เติม path เฉยๆ) → เด้งรายชื่อไฟล์ใน cwd
            m = re.search(r"(@|\./)([\w./+~-]*)$", text, re.UNICODE)
            if not m:
                return
            prefix = "@" if m.group(1) == "@" else ""
            q = m.group(2).lower()
            hits = [p for p in scan_files() if q in p.lower()]
            # ไฟล์ที่ชื่อ (basename) ขึ้นต้นด้วยคำค้นมาก่อน แล้วค่อยเรียงตาม path สั้น
            hits.sort(key=lambda p: (not os.path.basename(p).lower().startswith(q.rsplit("/", 1)[-1]), len(p)))
            for p in hits[:50]:
                yield Completion(prefix + p, start_position=-len(m.group(0)), display=p)

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
        return [("class:hint", f"  {state['label']}  ·  / คำสั่ง · @ แนบไฟล์ · ESC หยุด · Ctrl+C ออก")]

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
    ver = app_version()
    if ver:
        t.add_row("version", ver)
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


# ---------- utility functions — copied verbatim from agent.py ----------


def git_branch() -> str:
    try:
        r = subprocess.run(
            ["git", "-C", WORKDIR, "branch", "--show-current"],
            capture_output=True, text=True, timeout=2,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def app_version() -> str:
    """เวอร์ชันจาก git ของ repo เอง (ไม่ต้อง bump เลขมือ — /update แล้วเลขขยับเอง):
    v<จำนวน commit> (<hash> · <วันที่>) เช่น v42 (1542f99 · 2026-06-06); ไม่ใช่ git → ว่าง"""
    try:
        n = subprocess.run(["git", "-C", REPO_DIR, "rev-list", "--count", "HEAD"],
                           capture_output=True, text=True, timeout=3).stdout.strip()
        info = subprocess.run(["git", "-C", REPO_DIR, "log", "-1", "--format=%h %cs"],
                              capture_output=True, text=True, timeout=3).stdout.strip()
        if n and info and len(info.split()) == 2:
            h, d = info.split()
            return f"v{n} ({h} · {d})"
    except Exception:
        pass
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
