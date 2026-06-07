"""Main agent orchestration — build_system, wizard, main loop, slash commands."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
import time

import httpx
from rich.align import Align
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from boyser.config import (
    BASE_SYSTEM,
    CLAUDE_MODELS,
    CLOUD_PROVIDERS,
    CONFIG_PATH,
    LLAMACPP_URL,
    MEMORY_FILE,
    OLLAMA_URL,
    PROJECT_FILES,
    REPO_DIR,
    SKILLS,
    SKILLS_DIRS,
    THEME,
    THEMES,
    WORKDIR,
    YOLO,
    apply_theme,
    extract_files,
    load_config,
    save_config,
    LOGO,
)
from boyser.repl import (
    make_prompt,
    print_help,
    print_tools,
    print_status,
    git_branch,
    app_version,
    build_statusline,
    expand_file_mentions,
    console,
    SLASH_COMMANDS,
)
from boyser.backend import make_backend, SESSION, _status_ctx
from boyser.interrupt import Interrupt
from boyser.tools import (
    TOOL_FUNCS,
    CURRENT_TODOS,
    execute_tool,
    confirm,
    read_memory_lines,
    write_memory_lines,
    print_memory,
    edit_memory,
    _parse_frontmatter,
)

console = Console()


# ---------- skills ----------

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
                if name not in skills:  # project (listed first) overrides global
                    skills[name] = {
                        "path": md,
                        "dir": os.path.dirname(md),
                        "description": meta.get("description", ""),
                    }
    return skills


def build_system(base: str) -> tuple[str, list[str]]:
    """ประกอบ system prompt + โหลด memory, project context, รายการ skills"""
    import boyser.config as _cfg

    discovered = discover_skills()
    _cfg.SKILLS.clear()
    _cfg.SKILLS.update(discovered)

    parts = [base]
    loaded = []

    if discovered:
        lines = "\n".join(f"- {n}: {s['description']}" for n, s in discovered.items())
        parts.append(
            "\n# Skills (ความเชี่ยวชาญเฉพาะทาง)\n"
            "เมื่อ task ตรงกับ skill ด้านล่าง เรียก tool `use_skill` ด้วยชื่อนั้นเพื่อโหลดวิธีทำแบบเต็มก่อนลงมือ:\n"
            f"{lines}"
        )
        loaded.append(f"skills ({len(discovered)})")

    # MCP auto-discovery — connect servers and list their tools
    try:
        from boyser.mcp import MCPClient, load_mcp_config
        mcp_config = load_mcp_config()
        mcp_servers = mcp_config.get("servers", [])
        mcp_tools_list = []
        if mcp_servers:
            mcp_client = MCPClient()
            for srv in mcp_servers:
                name = srv.get("name", "")
                cmd = srv.get("command", "")
                args = srv.get("args", [])
                if name and cmd:
                    try:
                        tools = mcp_client.connect_stdio(name, cmd, args)
                        for t in (tools or []):
                            mcp_tools_list.append(f"  [{name}] {t['name']}: {t.get('description', '')[:80]}")
                    except Exception:
                        pass
            if mcp_tools_list:
                parts.append(
                    "\n# MCP Tools (connected external servers)\n"
                    + "\n".join(mcp_tools_list)
                )
                loaded.append(f"MCP ({len(mcp_servers)} servers, {len(mcp_tools_list)} tools)")
    except Exception:
        pass

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


# ---------- wizard ----------

def list_ollama_models(base_url: str, api_key: str = "") -> list[str]:
    try:
        hdr = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        r = httpx.get(base_url.replace("/v1", "/api/tags"), timeout=3, headers=hdr)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def list_openai_models(base_url: str, api_key: str = "") -> list[str]:
    """Scan OpenAI-compatible /v1/models endpoint → list model IDs."""
    try:
        hdr = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        # Normalize: ensure /v1 suffix for the /models endpoint
        url = base_url.rstrip("/")
        if url.endswith("/v1"):
            url = url + "/models"
        else:
            url = url + "/v1/models" if "/v1/" not in url else url + "/models"
        r = httpx.get(url, timeout=5, headers=hdr)
        return [m["id"] for m in r.json().get("data", [])]
    except Exception:
        return []


def menu_select(title: str, choices: list[tuple[str, str]], default: str | None = None) -> str | None:
    """เมนูเลือกด้วยลูกศร (questionary) — ESC = ย้อนกลับ"""
    if default is not None and not any(label == default for label, _ in choices):
        default = None
    if sys.stdin.isatty():
        import questionary
        from prompt_toolkit.keys import Keys

        q_choices = [
            questionary.Choice(title=f"{label}  {desc}" if desc else label, value=label)
            for label, desc in choices
        ]
        q = questionary.select(title, choices=q_choices, default=default)
        q.application.ttimeoutlen = 0.09

        @q.application.key_bindings.add(Keys.Escape, eager=True)
        def _(event):
            event.app.exit(result="__ESC__")

        ans = q.ask()
        if ans == "__ESC__":
            return None
        if ans is None:
            sys.exit(0)
        return ans
    console.print(f"\n[bold]{title}[/]")
    for i, (label, desc) in enumerate(choices, 1):
        console.print(f"  {i}. {label}  [dim]{desc}[/]")
    while True:
        try:
            ans = console.input("เลือกหมายเลข: ").strip()
        except (EOFError, KeyboardInterrupt, ValueError):
            console.print()
            return None
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
    try:
        return console.input(f"{title} ").strip() or default
    except (EOFError, KeyboardInterrupt, ValueError):
        console.print()
        return default


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
    """ตรวจ ant CLI + login"""
    if not shutil.which("ant"):
        console.print("[yellow]ยังไม่มี Anthropic CLI (`ant`) — ต้องติดตั้งก่อนใช้ OAuth:[/]")
        console.print("[dim]  mac:   brew install anthropics/tap/ant[/]")
        console.print("[dim]  go:    go install github.com/anthropics/anthropic-cli/cmd/ant@latest[/]")
        console.print("[dim]ติดตั้งแล้วพิมพ์  ! ant auth login  ในเซสชัน หรือเลือก OAuth ใหม่[/]")
        return
    try:
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


def setup_wizard(old_cfg: dict | None = None) -> dict | None:
    """เมนูตั้งค่า — ESC ในเมนูลึก = ย้อนกลับ"""
    console.print(Panel.fit(
        "[bold bright_blue]✻ BOYSER AI[/] — ตั้งค่า\n"
        "[dim]เลือกว่าจะใช้สมองจากที่ไหน (เปลี่ยนทีหลังได้ด้วย /model · ESC ย้อนกลับ)[/]",
        border_style="bright_blue",
    ))

    old = old_cfg or load_config() or {}
    old_local = old if old.get("backend") == "local" else {}

    while True:
        backend = menu_select("เลือก backend:", [
            ("Claude API", "Claude ของ Anthropic — API key หรือ login"),
            ("Cloud API", "OpenRouter / Groq / DeepSeek / OpenAI / Gemini ฯลฯ"),
            ("Ollama", "โมเดล local ฟรี — ใช้เครื่องตัวเอง"),
            ("llama.cpp", "llama-server แบบ OpenAI-compatible"),
        ], default="Claude API" if old.get("backend") == "claude" else None)
        if backend is None:
            if load_config():
                console.print("[dim]ยกเลิก — ใช้ค่าเดิม[/]")
                return None
            if not sys.stdin.isatty():
                console.print("\n[yellow]ไม่สามารถตั้งค่าได้เพราะ stdin ไม่ใช่ terminal[/]")
                console.print()
                console.print("  รันใน terminal จริงก่อน หรือสร้าง config ด้วย:", style="dim")
                console.print(f"    mkdir -p {os.path.dirname(CONFIG_PATH)}", style="dim")
                console.print(f"    echo '{{\"backend\":\"local\",\"base_url\":\"...\",\"model\":\"...\"}}' > {CONFIG_PATH}", style="dim")
                console.print()
                sys.exit(1)
            console.print("[yellow]ยังไม่เคยตั้งค่า — ต้องเลือก backend ก่อน (Ctrl+C = ออกโปรแกรม)[/]")
            continue

        if backend == "Claude API":
            model = menu_select("เลือกโมเดล:", CLAUDE_MODELS,
                                default=old.get("model") if old.get("backend") == "claude" else None)
            if model is None:
                continue
            auth = menu_select("วิธียืนยันตัวตน:", [
                ("API key", "วาง sk-ant-... (จ่ายตามใช้)"),
                ("OAuth login", "ไม่ต้องวาง key — ต้อง `ant auth login` ก่อน"),
            ])
            if auth is None:
                continue
            if auth == "API key":
                key = os.environ.get("ANTHROPIC_API_KEY", "")
                if key:
                    console.print("[green]เจอ ANTHROPIC_API_KEY ใน environment แล้ว[/]")
                else:
                    key = ask_text("วาง API key (sk-ant-... จาก platform.claude.com):", password=True)
                cfg = {"backend": "claude", "model": model, "api_key": key}
            else:
                ant_oauth_login()
                cfg = {"backend": "claude", "model": model}

        elif backend == "Cloud API":
            choices = [(n, u) for n, u in CLOUD_PROVIDERS.items()] + [("กำหนดเอง", "ใส่ base_url เอง")]
            prov = menu_select("เลือกผู้ให้บริการ:", choices)
            if prov is None:
                continue
            base = CLOUD_PROVIDERS.get(prov) or ask_text("base_url (OpenAI-compatible):",
                                                         default=old_local.get("base_url") or "https://")
            same_prov = base == old_local.get("base_url")
            key = ask_text(f"วาง API key ของ {prov}{' (Enter = ใช้ key เดิม)' if same_prov and old_local.get('api_key') else ''}:",
                           password=True)
            key = key or (old_local.get("api_key", "") if same_prov else "")
            # Scan models from endpoint
            models = list_openai_models(base, key)
            if models:
                model = menu_select("เลือกโมเดล (จาก /v1/models):", [(m, "") for m in models],
                                    default=old_local.get("model"))
                if model is None:
                    continue
            else:
                eg = {"OpenRouter": "anthropic/claude-sonnet-4.6", "Groq": "llama-3.3-70b-versatile",
                      "DeepSeek": "deepseek-chat", "OpenAI": "gpt-4o", "Gemini": "gemini-2.0-flash"}.get(prov, "ชื่อโมเดล")
                model = ask_text(f"ชื่อโมเดล (scan ไม่สำเร็จ — เช่น {eg}):",
                                 default=(old_local.get("model") if same_prov else "") or eg)
            cfg = {"backend": "local", "base_url": base, "model": model, "api_key": key}

        elif backend == "Ollama":
            url = ask_text("Ollama อยู่ที่ไหน (Enter = เครื่องนี้ / ใส่ IP เครื่องอื่น):",
                           default=old_local.get("base_url") or OLLAMA_URL)
            if "://" not in url:
                url = "http://" + url
            if url.startswith("http://") and ":" not in url.split("://", 1)[1]:
                url += ":11434"
            if not url.rstrip("/").endswith("/v1"):
                url = url.rstrip("/") + "/v1"
            key = ask_text("API key (Enter = ใช้ key เดิม):" if old_local.get("api_key")
                           else "API key (ถ้าต่อผ่าน proxy/โดเมน — Enter = ไม่มี):", password=True)
            key = key or old_local.get("api_key", "")
            models = list_ollama_models(url, key)
            if models:
                model = menu_select("เลือกโมเดล (จาก ollama list):", [(m, "") for m in models],
                                    default=old_local.get("model"))
                if model is None:
                    continue
            else:
                console.print(f"[yellow]ต่อ Ollama ที่ {url} ไม่ได้ — พิมพ์ชื่อโมเดลเอง[/]")
                model = ask_text("ชื่อโมเดล:", default=old_local.get("model") or "qwen3-coder-tools")
            cfg = {"backend": "local", "base_url": url, "model": model,
                   "num_ctx": ask_ctx(old_local.get("num_ctx") or 16384)}
            if key:
                cfg["api_key"] = key

        else:  # llama.cpp
            url = ask_text("URL ของ llama-server:", default=old_local.get("base_url") or LLAMACPP_URL)
            # Scan models from OpenAI-compatible endpoint
            models = list_openai_models(url, "")
            if models:
                model = menu_select("เลือกโมเดล (จาก /v1/models):", [(m, "") for m in models],
                                    default=old_local.get("model"))
                if model is None:
                    continue
            else:
                model = ask_text("ชื่อโมเดล (scan ไม่สำเร็จ — พิมพ์เอง):", default=old_local.get("model") or "default")
            console.print("[dim]หมายเหตุ: llama.cpp กำหนด ctx ตอนรัน server (-c) เป็นหลัก[/]")
            cfg = {"backend": "local", "base_url": url, "model": model,
                   "num_ctx": ask_ctx(old_local.get("num_ctx") or 16384)}

        theme = menu_select("เลือกธีมสี:", [(n, "") for n in THEMES], default=old.get("theme"))
        if theme is None:
            continue
        cfg["theme"] = theme
        for k in ("think", "statusline", "vote"):
            if k in old:
                cfg[k] = old[k]
        save_config(cfg)
        console.print(f"[green]✓ บันทึกที่ {CONFIG_PATH}[/]\n")
        return cfg


# ---------- อัปเดต ----------

UPDATE_AVAILABLE = threading.Event()


def check_update_bg() -> None:
    """เช็คเวอร์ชันใหม่จาก git remote ใน daemon thread (เงียบ ไม่ถ่วง startup)"""

    def run():
        try:
            if not os.path.isdir(os.path.join(REPO_DIR, ".git")):
                return
            local = subprocess.run(
                ["git", "-C", REPO_DIR, "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
            remote_out = subprocess.run(
                ["git", "-C", REPO_DIR, "ls-remote", "--quiet", "origin", "HEAD"],
                capture_output=True, text=True, timeout=15,
            ).stdout.split()
            remote = remote_out[0] if remote_out else ""
            if not local or not remote or local == remote:
                return
            anc = subprocess.run(
                ["git", "-C", REPO_DIR, "merge-base", "--is-ancestor", remote, "HEAD"],
                capture_output=True, timeout=5,
            )
            if anc.returncode != 0:
                UPDATE_AVAILABLE.set()
        except Exception:
            pass

    threading.Thread(target=run, daemon=True).start()


# ---------- main ----------

def _save_session_log(messages: list, backend) -> str | None:
    """Save conversation to ~/.config/boyser-ai/history/<timestamp>.md"""
    try:
        import json
        from boyser.config import HISTORY_PATH

        ts = time.strftime("%Y%m%d-%H%M%S")
        model_name = getattr(backend, "name", "unknown")
        path = os.path.join(HISTORY_PATH, f"session-{ts}-{model_name.replace('/', '-')}.md")
        os.makedirs(HISTORY_PATH, exist_ok=True)

        lines = [
            f"# BOYSER AI Session — {ts}",
            f"Model: {model_name}",
            f"Messages: {len(messages)}",
            "---",
        ]
        for i, m in enumerate(messages):
            role = m.get("role", "?")
            content = m.get("content", "")
            if isinstance(content, list):
                content = json.dumps(content, ensure_ascii=False, indent=2)
            lines.append(f"\n### [{i+1}] {role}\n{content}")

        text = "\n".join(lines)
        # Limit to 50 most recent sessions
        existing = sorted(
            f for f in os.listdir(HISTORY_PATH) if f.startswith("session-") and f.endswith(".md")
        )
        while len(existing) >= 50:
            os.remove(os.path.join(HISTORY_PATH, existing.pop(0)))

        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path
    except Exception:
        return None


def main() -> None:
    """Entry point: parse args, setup config, run REPL loop."""
    import boyser.config as _cfg

    # Register auto-save on clean exit
    import atexit
    _saved_path = [None]

    def _save_on_exit():
        p = _save_session_log(messages, backend)
        if p:
            _saved_path[0] = p
            console.print(f"\n[dim]💾 บันทึก session log → {p}[/]")

    parser = argparse.ArgumentParser(description="BOYSER AI — mini Claude Code")
    parser.add_argument("--local", nargs="?", const=OLLAMA_URL, default=None, metavar="BASE_URL",
                        help="ข้าม config ใช้โมเดล local ชั่วคราว")
    parser.add_argument("--model", help="ชื่อโมเดล (ใช้คู่ --local)")
    parser.add_argument("--setup", action="store_true", help="เปิดเมนูตั้งค่าใหม่")
    parser.add_argument("--yolo", action="store_true", help="ไม่ถามยืนยันก่อนรัน tool (ระวัง!)")
    args = parser.parse_args()
    YOLO = args.yolo

    # ---- เลือก config ----
    if args.local:
        if not args.model:
            sys.exit("ต้องระบุ --model ด้วย เช่น --model qwen3-coder-tools")
        cfg = {"backend": "local", "base_url": args.local, "model": args.model}
    else:
        cfg = load_config()
        if cfg is None or args.setup:
            cfg = setup_wizard(cfg) or cfg

    # Only auto-save interactive sessions (has messages)
    atexit.register(_save_on_exit)

    apply_theme(cfg.get("theme", "ฟ้า"))
    _cfg.THINK_ON = cfg.get("think", False)
    _cfg.VOTE_ON = cfg.get("vote", True)

    _cfg.SYSTEM, loaded = build_system(BASE_SYSTEM)

    backend = make_backend(cfg)
    messages = backend.new_messages()
    read_input = make_prompt()
    SESSION["started"] = time.monotonic()
    _status_ctx["backend"] = backend
    _status_ctx["on"] = cfg.get("statusline", False)

    def show_banner():
        from boyser.config import LOGO
        accent = THEME["accent"]
        logo_w = max((len(line) for line in LOGO.splitlines()), default=0)
        if console.size.width >= logo_w + 6:
            head = Align.center(Text(LOGO, style=f"bold {accent}", no_wrap=True))
        else:
            head = Align.center(Text("✻ BOYSER AI", style=f"bold {accent}"))
        details = Text()
        rows = [("model", backend.name), ("cwd", WORKDIR)]
        ver = app_version()
        if ver:
            rows.insert(0, ("version", ver))
        if loaded:
            rows.append(("loaded", ", ".join(loaded)))
        for k, v in rows:
            details.append(f"{k:<9}", style="dim")
            details.append(v + "\n")
        details.append("พิมพ์ ", style="dim")
        details.append("/", style=f"bold {accent}")
        details.append(" ดูคำสั่ง · ", style="dim")
        details.append("exit", style=f"bold {accent}")
        details.append(" ออก", style="dim")
        if YOLO:
            details.append("  · YOLO MODE", style="bold red")
        body = Group(head, Text(), details)
        console.print(Panel(body, border_style=THEME["border"], padding=(1, 2)))

    show_banner()
    check_update_bg()

    while True:
        if UPDATE_AVAILABLE.is_set():
            UPDATE_AVAILABLE.clear()
            console.print(f"[yellow]⬆ มีเวอร์ชันใหม่บน GitHub — พิมพ์ [bold]/update[/bold] เพื่ออัปเดต[/]")
        try:
            user = (read_input(backend.name) if sys.stdin.isatty() else read_input()).strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user:
            continue
        if sys.stdin.isatty():
            console.print(Text("❯ ", style=f"bold {THEME['accent']}") + Text(user))

        if user.lower() in ("exit", "quit", "/exit"):
            break

        # ---- slash commands ----
        if user == "/help":
            print_help(backend)
            continue
        if user == "/theme":
            name = menu_select("เลือกธีมสี:", [(n, "ปัจจุบัน" if n == THEME["name"] else "") for n in THEMES])
            if name is None:
                continue
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
            if changed:
                _cfg.SYSTEM, loaded = build_system(BASE_SYSTEM)
                messages = backend.new_messages()
                console.print("[dim]โหลด memory ใหม่เข้า session แล้ว (ประวัติแชตถูกล้าง)[/]")
            continue
        if user == "/think":
            _cfg.THINK_ON = not _cfg.THINK_ON
            cfg["think"] = _cfg.THINK_ON
            save_config(cfg)
            if _cfg.THINK_ON and getattr(backend, "is_ollama", False) and not backend.supports_think:
                console.print(f"[yellow]think: เปิดแล้ว แต่ {backend.name} ไม่รองรับ thinking — ลองโมเดลอื่น เช่น gemma/glm[/]")
            else:
                console.print(f"[{THEME['accent'] if _cfg.THINK_ON else 'dim'}]think mode: {'เปิด — โมเดลจะคิดก่อนตอบ' if _cfg.THINK_ON else 'ปิด'}[/]")
            continue
        if user == "/vote":
            _cfg.VOTE_ON = not _cfg.VOTE_ON
            cfg["vote"] = _cfg.VOTE_ON
            save_config(cfg)
            console.print(f"[{THEME['accent'] if _cfg.VOTE_ON else 'dim'}]vote mode: "
                          f"{'เปิด — เอกสารยาวจะถามซ้ำ 3 รอบหา consensus' if _cfg.VOTE_ON else 'ปิด'}[/]")
            continue
        if user == "/update":
            if not os.path.isdir(os.path.join(REPO_DIR, ".git")):
                console.print("[yellow]ติดตั้งแบบไม่มี git — อัปเดตด้วยการ clone repo ใหม่[/]")
                continue
            console.print("[dim]กำลังดึงเวอร์ชันใหม่ (git pull)...[/]")
            r = subprocess.run(["git", "-C", REPO_DIR, "pull", "--ff-only"], capture_output=True, text=True)
            out = (r.stdout + r.stderr).strip()
            if r.returncode != 0:
                console.print(f"[red]pull ไม่สำเร็จ:[/] {out}")
                continue
            if "Already up to date" in out:
                console.print(f"[{THEME['accent']}]เป็นเวอร์ชันล่าสุดอยู่แล้ว[/]")
                continue
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r",
                 os.path.join(REPO_DIR, "requirements.txt"), "-q"],
                capture_output=True,
            )
            src = os.path.join(REPO_DIR, "skills")
            added = 0
            if os.path.isdir(src):
                os.makedirs(SKILLS_DIRS[1], exist_ok=True)
                for name in os.listdir(src):
                    s, d = os.path.join(src, name), os.path.join(SKILLS_DIRS[1], name)
                    if os.path.isdir(s) and not os.path.exists(d):
                        shutil.copytree(s, d)
                        added += 1
            extra = f" · skills ใหม่ {added} ตัว" if added else ""
            console.print(f"[green]✓ อัปเดตแล้ว{extra} — ปิดแล้วเปิด boyser-ai ใหม่เพื่อใช้เวอร์ชันล่าสุด[/]")
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
                from boyser.config import SKILLS as _sk
                table = Table(show_header=False, box=None, padding=(0, 2))
                for n, s in _sk.items():
                    table.add_row(f"[bold {THEME['accent']}]{n}[/]", s["description"])
                console.print(Panel(table, title="Skills", border_style="dim"))
            continue
        if user == "/save":
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
            SESSION.update(**{"in": 0, "out": 0, "cached": 0, "turns": 0, "started": time.monotonic(),
                              "rem_tokens": None, "reset_tokens": None})
            console.clear()
            show_banner()
            console.print("[dim]ล้างหน้าจอ ประวัติ และตัวนับ token แล้ว[/]")
            continue
        if user == "/yolo":
            YOLO = not YOLO
            console.print(f"[{'red' if YOLO else 'green'}]YOLO mode: {'ON — ไม่ถามยืนยันแล้ว' if YOLO else 'OFF'}[/]")
            continue
        if user == "/model":
            new_cfg = setup_wizard(cfg)
            if new_cfg is None:
                continue
            cfg = new_cfg
            apply_theme(cfg.get("theme", THEME["name"]))
            _cfg.THINK_ON = cfg.get("think", False)
            _cfg.VOTE_ON = cfg.get("vote", True)
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
            backend = make_backend(cfg)
            console.print(f"[green]ตั้ง num_ctx = {cfg['num_ctx']} แล้ว (ใช้ตั้งแต่ข้อความถัดไป)[/]")
            continue
        if user.startswith("/"):
            console.print("[yellow]ไม่รู้จักคำสั่งนี้ — พิมพ์ /help[/]")
            continue

        # ---- normal message ----
        expanded, attached = expand_file_mentions(user)
        if attached:
            console.print(f"[dim]📎 แนบไฟล์: {', '.join(attached)}[/]")
        messages.append({"role": "user", "content": expanded})
        SESSION["turns"] += 1
        try:
            with Interrupt() as intr:
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
                console.print("[yellow]→ บัญชี Anthropic เครดิต API หมด/ไม่พอ[/] [dim]เติมที่ console.anthropic.com[/]")
                console.print("[dim]  ทางเลือกฟรี: /model → Ollama (local) · หรือ Cloud → OpenRouter[/]")
            elif "authentication" in low or "x-api-key" in low or "credential" in low:
                console.print("[yellow]→ ยืนยันตัวตนไม่ผ่าน[/] [dim]เช็ค API key หรือ `! ant auth login` ใหม่[/]")
            while messages and messages[-1].get("role") != "user":
                messages.pop()
            if messages and messages[-1].get("role") == "user":
                messages.pop()


if __name__ == "__main__":
    main()
