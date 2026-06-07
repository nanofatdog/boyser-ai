"""Tool implementations for BOYSER AI.

Extracted from agent.py — all tool functions + TOOL_FUNCS dispatch dict.
"""

from __future__ import annotations

import difflib
import glob as globlib
import html as htmllib
import json
import os
import re
import shutil
import subprocess
import sys
import time

import httpx
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from boyser.config import (
    ALWAYS_ALLOW,
    CONFIG_DIR,
    GIT_BASH,
    IS_WIN,
    MEMORY_FILE,
    SKILLS,
    THEME,
    WORKDIR,
    YOLO,
)
from boyser.interrupt import _active_interrupt
from boyser.repl import console, show_diff, show_tool_call, show_tool_result

# ============================================================
# CURRENT_TODOS — global state for todo_write
# ============================================================

CURRENT_TODOS: list = []
_TODO_MARK = {
    "pending": ("○", "white"),
    "in_progress": ("◐", "yellow"),
    "done": ("●", "green"),
}

# ============================================================
# confirm
# ============================================================


def confirm(key: str) -> bool:
    """ถามยืนยันก่อนทำ action ที่แก้ไขเครื่อง (y / n / a = อนุญาต tool นี้ตลอด session)"""
    if YOLO or key in ALWAYS_ALLOW:
        return True
    intr = _active_interrupt
    try:
        if intr:
            intr.pause()  # กันไม่ให้ตัวดัก ESC แย่งปุ่ม y/n/a
        ans = (
            console.input("  [yellow]ดำเนินการ? (y / n / a=อนุญาตตลอด)[/] ")
            .strip()
            .lower()
        )
    except (EOFError, KeyboardInterrupt):
        return False
    finally:
        if intr:
            intr.resume()
    if ans == "a":
        ALWAYS_ALLOW.add(key)
        return True
    return ans == "y"


# ============================================================
# _parse_frontmatter (needed by use_skill)
# ============================================================


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
            body = text[end + 4 :].lstrip()
    return meta, body


# ============================================================
# 1. run_bash
# ============================================================


def run_bash(command: str) -> str:
    if not confirm("bash"):
        return "Error: user denied this command."
    common = dict(
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=WORKDIR
    )
    if IS_WIN:
        if GIT_BASH:  # มี Git Bash → คำสั่ง bash ที่โมเดลเขียนใช้ได้เลย
            p = subprocess.Popen([GIT_BASH, "-c", command], **common)
        else:  # ไม่มี → cmd.exe (system prompt บอกโมเดลให้เขียนคำสั่ง Windows แล้ว)
            p = subprocess.Popen(command, shell=True, **common)
    else:
        import signal

        p = subprocess.Popen(
            command,
            shell=True,
            start_new_session=True,  # group ใหม่ → ฆ่าลูกหลานได้หมด
            **common,
        )

    def kill():
        try:
            if IS_WIN:  # taskkill /T ฆ่าทั้ง tree (เทียบเท่า killpg)
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True
                )
            else:
                os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except Exception:
            pass
        try:
            p.communicate(timeout=1)  # เก็บศพ กัน zombie
        except Exception:
            pass

    intr = _active_interrupt
    deadline = time.monotonic() + 120
    while True:
        try:
            out, _ = p.communicate(timeout=0.2)
            out = (out or "").strip()
            return out[:20000] if out else f"(no output, exit code {p.returncode})"
        except subprocess.TimeoutExpired:
            pass
        if intr and intr.stopped():  # ESC → ฆ่าทั้ง process group ทันที
            kill()
            return "Error: ถูกหยุดโดยผู้ใช้ (ESC)"
        if time.monotonic() > deadline:
            kill()
            return "Error: command timed out after 120s."


# ============================================================
# 2. read_file
# ============================================================


def read_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        return "".join(f"{i + 1}\t{line}" for i, line in enumerate(lines[:2000]))
    except OSError as e:
        return f"Error: {e}"


# ============================================================
# 3. write_file
# ============================================================


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


# ============================================================
# 4. edit_file
# ============================================================


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


# ============================================================
# 5. glob_tool
# ============================================================


def glob_tool(pattern: str) -> str:
    try:
        matches = globlib.glob(pattern, recursive=True)
    except Exception as e:
        return f"Error: {e}"
    matches = [
        m
        for m in matches
        if "/.venv/" not in (n := m.replace(os.sep, "/"))
        and "/.git/" not in n
    ]
    matches.sort(
        key=lambda m: os.path.getmtime(m) if os.path.exists(m) else 0, reverse=True
    )
    if not matches:
        return "(no files matched)"
    return "\n".join(matches[:100])


# ============================================================
# 6. _grep_py (Python fallback grep)
# ============================================================


def _grep_py(pattern: str, path: str) -> str:
    """grep สำรองภาษา Python ล้วน — ใช้ตอนเครื่องไม่มี grep binary (Windows ที่ไม่มี Git Bash)"""
    try:
        rx = re.compile(pattern)
    except re.error as e:
        return f"Error: invalid pattern: {e}"
    skip = {".git", ".venv", "node_modules", "__pycache__"}
    out: list[str] = []
    deadline = time.monotonic() + 30
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in skip]
        for fn in files:
            if time.monotonic() > deadline:
                return "\n".join(out) if out else "Error: grep timed out."
            fp = os.path.join(root, fn)
            try:
                with open(fp, "rb") as f:
                    head = f.read(1024)
                if b"\0" in head:  # binary → ข้าม (เทียบเท่า grep -I)
                    continue
                hits = 0
                with open(fp, encoding="utf-8", errors="replace") as f:
                    for i, line in enumerate(f, 1):
                        if rx.search(line):
                            out.append(f"{fp}:{i}:{line.rstrip()}")
                            hits += 1
                            if hits >= 5 or len(out) >= 100:
                                break
            except OSError:
                continue
            if len(out) >= 100:
                return "\n".join(out)
    return "\n".join(out) if out else "(no matches)"


# ============================================================
# 7. grep_tool
# ============================================================


def grep_tool(pattern: str, path: str = ".") -> str:
    if shutil.which("grep") is None:
        return _grep_py(pattern, path)
    cmd = [
        "grep",
        "-rn",
        "-I",
        "-E",
        "-m",
        "5",
        "--exclude-dir=.git",
        "--exclude-dir=.venv",
        "--exclude-dir=node_modules",
        "--exclude-dir=__pycache__",
        "-e",
        pattern,
        path,
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


# ============================================================
# 8. web_search
# ============================================================


def web_search(query: str) -> str:
    try:
        from ddgs import DDGS

        results = DDGS().text(query, max_results=8)
    except Exception as e:
        return f"Error: {e}"
    if not results:
        return "(no results)"
    out = "\n\n".join(
        f"{r.get('title', '')}\n{r.get('href', '')}\n{r.get('body', '')}"
        for r in results
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


# ============================================================
# 9. web_fetch
# ============================================================


def web_fetch(url: str) -> str:
    try:
        r = httpx.get(
            url,
            follow_redirects=True,
            timeout=20,
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


# ============================================================
# 10. parse_text_toolcalls
# ============================================================


def parse_text_toolcalls(text: str) -> list:
    """fallback: โมเดล local บางตัวพ่น tool call เป็นข้อความ (parser ของ engine จับไม่ได้)
    ดักจับ 3 ฟอร์แมตยอดฮิต → คืน [{name, args(dict)}]"""
    s = text.strip()
    calls: list = []

    # A) JSON tool call เดี่ยว หรือใน ```json ... ```
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.S)
    candidate = fence.group(1) if fence else (s if s.startswith("{") else "")
    if candidate and '"name"' in candidate:
        try:
            o = json.loads(candidate)
            if isinstance(o, dict) and "name" in o:
                return [
                    {
                        "name": o["name"],
                        "args": o.get("arguments") or o.get("parameters") or {},
                    }
                ]
        except json.JSONDecodeError:
            pass

    # B) <tool_call>{json}</tool_call> (Hermes/Qwen)
    for m in re.finditer(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", s, re.S):
        try:
            o = json.loads(m.group(1))
            calls.append(
                {
                    "name": o.get("name", ""),
                    "args": o.get("arguments") or o.get("parameters") or {},
                }
            )
        except json.JSONDecodeError:
            pass
    if calls:
        return calls

    # C) <function=NAME>...<parameter=KEY>VALUE...</...>
    for fm in re.finditer(
        r"<function=([^>\s]+)>(.*?)(?:</function>|</tool_call>|\Z)", s, re.S
    ):
        name = fm.group(1).strip()
        args = {}
        for pm in re.finditer(
            r"<parameter=([^>\s]+)>\s*(.*?)\s*(?=<parameter=|</parameter>|</function>|</tool_call>|\Z)",
            fm.group(2),
            re.S,
        ):
            args[pm.group(1).strip()] = pm.group(2).strip()
        if name:
            calls.append({"name": name, "args": args})
    if calls:
        return calls

    # D) fallback: สแกนหา {…} ด้วยการนับ depth ดัก JSON tool call หลายก้อนติดกัน
    #    (regex จับ nested braces ไม่ได้ → ใช้ pointer scan แทน)
    i = 0
    while i < len(s):
        brace_start = s.find("{", i)
        if brace_start == -1:
            break
        depth = 0
        j = brace_start
        while j < len(s):
            ch = s[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    chunk = s[brace_start : j + 1]
                    if '"name"' in chunk:
                        try:
                            o = json.loads(chunk)
                            if isinstance(o, dict) and "name" in o:
                                calls.append(
                                    {
                                        "name": o["name"],
                                        "args": o.get("arguments") or o.get("parameters") or {},
                                    }
                                )
                        except json.JSONDecodeError:
                            pass
                    i = j + 1
                    break
            elif ch in "\"'" and (j == 0 or s[j - 1] != "\\"):
                # ข้าม string (ป้องกัน } ใน string)
                quote = ch
                j += 1
                while j < len(s):
                    if s[j] == "\\":
                        j += 2
                        continue
                    if s[j] == quote:
                        break
                    j += 1
            j += 1
        else:
            break  # brace เปิดแต่ไม่เจอปิด
    return calls


# ============================================================
# 11. todo_write + render_todos
# ============================================================


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
    # โมเดล local บางตัวส่ง todos เป็น list ของ string (ไม่ใช่ dict) → ห่อให้ก่อน กัน .get() crash ทั้ง turn
    todos = [
        t if isinstance(t, dict) else {"task": str(t), "status": "pending"}
        for t in (todos or [])
    ]
    CURRENT_TODOS = todos
    render_todos(todos)
    done = sum(1 for t in todos if t.get("status") == "done")
    return f"Plan updated ({done}/{len(todos)} done)."


# ============================================================
# 12. remember
# ============================================================


def remember(fact: str) -> str:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d")
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"- [{stamp}] {fact.strip()}\n")
    return "บันทึกลง memory แล้ว (จะจำได้ใน session ต่อไป)"


# ============================================================
# 13. ask_user
# ============================================================


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
                out.append(
                    (questionary.text("ระบุ:").ask() or "")
                    if s.startswith("อื่นๆ")
                    else s
                )
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


# ============================================================
# 14. use_skill
# ============================================================


def use_skill(name: str) -> str:
    sk = SKILLS.get(name)
    if not sk:
        return (
            f"Error: ไม่พบ skill '{name}'. ที่มี: {', '.join(SKILLS) or '(ไม่มี)'}"
        )
    _, body = _parse_frontmatter(sk["path"])
    files = [
        fn for fn in sorted(os.listdir(sk["dir"])) if fn != "SKILL.md"
    ]
    extra = f"\n\n[ไฟล์ประกอบใน {sk['dir']}: {', '.join(files)}]" if files else ""
    return body + extra


# ============================================================
# Memory helpers
# ============================================================


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
    console.print(
        Panel(
            t,
            title=f"memory ({len(lines)})",
            border_style=THEME["border"],
            title_align="left",
        )
    )


def edit_memory() -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(MEMORY_FILE):
        open(MEMORY_FILE, "a").close()
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or (
        "notepad" if IS_WIN else "nano"
    )
    try:
        subprocess.call([editor, MEMORY_FILE])
    except Exception as e:
        console.print(f"[red]เปิด editor ({editor}) ไม่ได้: {e}[/]")


# ============================================================
# 15. vision_tool
# ============================================================


def vision_tool(path_or_url: str, question: str = "") -> str:
    """Analyze an image using a local multimodal vision model endpoint.

    Tries:
      1. llama.cpp server endpoint (http://127.0.0.1:8080/infill)
      2. Ollama multimodal endpoint (http://127.0.0.1:11434/api/chat)
      3. Reads env var VISION_ENDPOINT for a custom URL
    Falls back to a helpful error listing options.
    """
    import base64

    endpoint = os.environ.get("VISION_ENDPOINT", "")

    def _try_llamacpp(img_b64: str) -> str | None:
        try:
            resp = httpx.post(
                "http://127.0.0.1:8080/infill",
                json={
                    "prompt": f"[img]{img_b64}[/img] {question}",
                    "n_predict": 256,
                },
                timeout=60,
            )
            if resp.status_code == 200:
                return resp.json().get("content", resp.text)[:4000]
        except Exception:
            pass
        return None

    def _try_ollama(img_b64: str) -> str | None:
        try:
            resp = httpx.post(
                "http://127.0.0.1:11434/api/chat",
                json={
                    "model": "llava",
                    "messages": [
                        {
                            "role": "user",
                            "content": question or "Describe this image in detail.",
                            "images": [img_b64],
                        }
                    ],
                    "stream": False,
                },
                timeout=60,
            )
            if resp.status_code == 200:
                msg = resp.json().get("message", {})
                return msg.get("content", resp.text)[:4000]
        except Exception:
            pass
        return None

    def _try_custom_endpoint(img_b64: str, url: str) -> str | None:
        try:
            resp = httpx.post(
                url,
                json={"image": img_b64, "question": question},
                timeout=60,
            )
            if resp.status_code == 200:
                return resp.text[:4000]
        except Exception:
            pass
        return None

    # Read image bytes
    try:
        if path_or_url.startswith(("http://", "https://")):
            resp = httpx.get(path_or_url, timeout=30)
            resp.raise_for_status()
            img_bytes = resp.content
        else:
            with open(os.path.expanduser(path_or_url), "rb") as f:
                img_bytes = f.read()
    except Exception as e:
        return f"Error: cannot read image '{path_or_url}': {e}"

    img_b64 = base64.b64encode(img_bytes).decode("utf-8")

    # Try endpoints in order
    out = _try_custom_endpoint(img_b64, endpoint) if endpoint else None
    if out is None:
        out = _try_llamacpp(img_b64)
    if out is None:
        out = _try_ollama(img_b64)

    if out:
        return out

    return (
        f"Error: no vision endpoint available. "
        f"To use vision_tool, start one of:\n"
        f"  - llama.cpp server on http://127.0.0.1:8080\n"
        f"  - Ollama with a multimodal model on http://127.0.0.1:11434\n"
        f"  - Set VISION_ENDPOINT env var to a custom vision API URL\n"
        f"Image size: {len(img_bytes)} bytes, b64: {len(img_b64)} chars."
    )


# ============================================================
# 16. patch_tool
# ============================================================


def patch_tool(
    path: str, old_string: str, new_string: str, replace_all: bool = False
) -> str:
    """Fuzzy find-and-replace that tries multiple matching strategies.

    Strategies (tried in order):
      1. Exact match (same as edit_file)
      2. Strip trailing whitespace from each line
      3. Whitespace-normalized (collapse all whitespace runs to single space)
      4. Partial context — find best substring overlap when old_string
         is a fragment of the actual content

    Returns a unified diff on success, or an error explaining what was tried.
    """
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        return f"Error: {e}"

    strategies = [
        ("exact", lambda s: s),
        ("strip trailing space", lambda s: "\n".join(l.rstrip() for l in s.split("\n"))),
        ("whitespace-normalized", lambda s: re.sub(r"\s+", " ", s).strip()),
    ]

    # Strategy 1-3: match via various normalizations
    for name, normalize in strategies:
        norm_text = normalize(text)
        norm_old = normalize(old_string)
        count = norm_text.count(norm_old)
        if count == 1 or (count > 0 and replace_all):
            # Found match — apply replacement on original text by finding
            # the corresponding span in the original
            idx = norm_text.find(norm_old)
            # Walk the original text to find the byte/char position
            # by counting newlines from the start
            prefix_norm = norm_text[:idx]
            prefix_lines = prefix_norm.count("\n")
            orig_lines = text.split("\n")

            # If normalized is single-line, find it in the original
            if "\n" not in norm_old:
                # Single-line: search line by line for a match
                target = norm_old
                for i, line in enumerate(orig_lines):
                    if normalize(line).strip() == target.strip():
                        start = sum(len(l) + 1 for l in orig_lines[:i])
                        end = start + len(line)
                        new_text = text[:start] + new_string + text[end:]
                        show_diff(path, text, new_text)
                        if not confirm("patch_tool"):
                            return "Error: user denied this edit."
                        with open(path, "w", encoding="utf-8") as f:
                            f.write(new_text)
                        return f"Patched {path} (strategy: {name})"
            else:
                # Multi-line: find the matching block
                block_len = norm_old.count("\n") + 1
                for i in range(len(orig_lines) - block_len + 1):
                    block = "\n".join(orig_lines[i : i + block_len])
                    if normalize(block) == norm_old:
                        start = sum(len(l) + 1 for l in orig_lines[:i])
                        end = sum(len(l) + 1 for l in orig_lines[: i + block_len])
                        new_text = text[:start] + new_string + text[end:]
                        show_diff(path, text, new_text)
                        if not confirm("patch_tool"):
                            return "Error: user denied this edit."
                        with open(path, "w", encoding="utf-8") as f:
                            f.write(new_text)
                        return f"Patched {path} (strategy: {name})"
            # If replace_all and we got here, attempt global replacement
            if replace_all:
                new_text = text
                for i, line in enumerate(orig_lines):
                    if normalize(line).strip() == normalize(old_string).strip():
                        start = sum(len(l) + 1 for l in orig_lines[:i])
                        end = start + len(line)
                        new_text = new_text[:start] + new_string + new_text[end:]
                if new_text != text:
                    show_diff(path, text, new_text)
                    if not confirm("patch_tool"):
                        return "Error: user denied this edit."
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(new_text)
                    return f"Patched {path} (strategy: {name}, replace_all)"
            continue

    # Strategy 4: partial context — try to find old_string as a substring
    # of a larger block in the file
    if old_string in text:
        count = text.count(old_string)
        if count == 1 or (count > 0 and replace_all):
            if replace_all:
                new_text = text.replace(old_string, new_string)
            else:
                new_text = text.replace(old_string, new_string, 1)
            show_diff(path, text, new_text)
            if not confirm("patch_tool"):
                return "Error: user denied this edit."
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_text)
            return f"Patched {path} (strategy: partial-exact)"
    else:
        # Try case-insensitive
        lower_text = text.lower()
        lower_old = old_string.lower()
        if lower_old in lower_text:
            count = lower_text.count(lower_old)
            if count == 1 or (count > 0 and replace_all):
                idx = lower_text.find(lower_old)
                orig_fragment = text[idx : idx + len(old_string)]
                if replace_all:
                    new_text = text.replace(orig_fragment, new_string)
                else:
                    new_text = text.replace(orig_fragment, new_string, 1)
                show_diff(path, text, new_text)
                if not confirm("patch_tool"):
                    return "Error: user denied this edit."
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_text)
                return f"Patched {path} (strategy: case-insensitive)"

    return (
        f"Error: could not find match in {path}.\n"
        f"Tried strategies: exact, strip-trailing-space, whitespace-normalized, "
        f"partial-exact, case-insensitive.\n"
        f"old_string ({len(old_string)} chars) not found via any strategy."
    )


# ============================================================
# 17. search_files_tool
# ============================================================


def search_files_tool(
    pattern: str,
    target: str = "content",
    path: str = ".",
    file_glob: str | None = None,
    limit: int = 50,
    output_mode: str = "content",
) -> str:
    """Smart file search supporting content search (regex) and file search (glob).

    Args:
        pattern: Regex pattern (content search) or glob pattern (file search).
        target: 'content' — search inside files; 'files' — find files by name.
        path: Directory or file to search in.
        file_glob: Filter by file extension/pattern (e.g. '*.py').
        limit: Max results.
        output_mode: 'content' — show matches with line numbers;
                     'files_only' — just file paths;
                     'count' — match counts per file.
    """
    if target == "files":
        # File search mode — use glob-style matching
        matches: list[str] = []
        try:
            import fnmatch

            abs_path = os.path.abspath(os.path.expanduser(path))
            skip_dirs = {".git", ".venv", "node_modules", "__pycache__", ".codegraph"}
            for root, dirs, files in os.walk(abs_path):
                dirs[:] = [d for d in dirs if d not in skip_dirs]
                for fn in files:
                    if fnmatch.fnmatch(fn, pattern):
                        full = os.path.join(root, fn)
                        # Apply file_glob filter if given
                        if file_glob and not fnmatch.fnmatch(fn, file_glob):
                            continue
                        matches.append(full)
                        if len(matches) >= limit:
                            break
                if len(matches) >= limit:
                    break
        except Exception as e:
            return f"Error: {e}"

        if not matches:
            return "(no files matched)"
        return "\n".join(matches)

    # Content search mode — use httpx-based ripgrep if available, else Python fallback
    # First try rg (ripgrep) via subprocess
    def _rg_search() -> str | None:
        if not shutil.which("rg"):
            return None
        cmd = ["rg", "-n", "-I", "--no-heading"]
        if output_mode == "files_only":
            cmd.append("-l")
        elif output_mode == "count":
            cmd.extend(["--count-matches"])
        if file_glob:
            cmd.extend(["-g", file_glob])
        cmd.extend(["-e", pattern, path])
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            return None
        if r.returncode == 2:
            return f"Error: rg — {r.stderr.strip()}"
        out = r.stdout.strip()
        if not out:
            return "(no matches)"
        lines = out.splitlines()
        if len(lines) > limit:
            lines = lines[:limit]
        return "\n".join(lines)

    def _grep_py_search() -> str:
        """Pure Python grep fallback."""
        try:
            rx = re.compile(pattern)
        except re.error as e:
            return f"Error: invalid regex: {e}"
        skip = {".git", ".venv", "node_modules", "__pycache__", ".codegraph"}
        results: list[str] = []
        counts: dict[str, int] = {}
        deadline = time.monotonic() + 30
        abs_path = os.path.abspath(os.path.expanduser(path))

        for root, dirs, files in os.walk(abs_path):
            dirs[:] = [d for d in dirs if d not in skip]
            for fn in files:
                if time.monotonic() > deadline:
                    break
                if file_glob and not fn.endswith(file_glob.replace("*", "")):
                    continue
                fp = os.path.join(root, fn)
                try:
                    with open(fp, "rb") as f:
                        head = f.read(1024)
                    if b"\0" in head:
                        continue
                    file_hits = 0
                    with open(fp, encoding="utf-8", errors="replace") as f:
                        for i, line in enumerate(f, 1):
                            if rx.search(line):
                                file_hits += 1
                                if output_mode == "content" and len(results) < limit:
                                    results.append(f"{fp}:{i}:{line.rstrip()[:500]}")
                    if file_hits:
                        counts[fp] = file_hits
                except OSError:
                    continue
                if output_mode == "content" and len(results) >= limit:
                    break

        if output_mode == "files_only":
            out = "\n".join(sorted(counts.keys())[:limit])
        elif output_mode == "count":
            out = "\n".join(
                f"{fp}:{n}" for fp, n in sorted(counts.items(), key=lambda x: -x[1])[
                    :limit
                ]
            )
        else:
            out = "\n".join(results[:limit])
        return out or "(no matches)"

    # Try rg first, fall back to Python grep
    out = _rg_search()
    if out is None:
        out = _grep_py_search()
    return out


# ============================================================
# TOOL_FUNCS dispatch dict
# ============================================================

def subagent_tool(goal: str, context: str = "") -> str:
    """Subagent delegation — spawn child agent for background work."""
    try:
        from boyser.subagent import SubAgentClient
        client = SubAgentClient()
        session = client.spawn(goal=goal, context=context or None)
        session_id = session.id
        if session.status == "failed":
            return f"Error: {session.summary}"
        final = client.wait(session_id, timeout=300)
        if final.status == "failed":
            return f"Subagent [{session_id}] failed: {final.summary}"
        summary = final.summary or "\n".join(final._stdout_lines[-5:]) or "done"
        return f"Subagent [{session_id}]: {summary}"
    except Exception as e:
        return f"Error spawning subagent: {e}"


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
    "ask_user": lambda i: ask_user(
        i["question"], i.get("options", []), i.get("multiple", False)
    ),
    "vision": lambda i: vision_tool(i["path_or_url"], i.get("question", "")),
    "patch": lambda i: patch_tool(
        i["path"],
        i["old_string"],
        i["new_string"],
        i.get("replace_all", False),
    ),
    "search_files": lambda i: search_files_tool(
        i["pattern"],
        i.get("target", "content"),
        i.get("path", "."),
        i.get("file_glob"),
        i.get("limit", 50),
        i.get("output_mode", "content"),
    ),
    "subagent": lambda i: subagent_tool(i["goal"], i.get("context", "")),
}

# tool ที่ไม่ต้องโชว์บรรทัด ⏺/⎿ (มี UI ของตัวเอง)
_QUIET_TOOLS = {"todo_write", "ask_user", "subagent"}


def execute_tool(name: str, tool_input: dict) -> str:
    quiet = name in _QUIET_TOOLS
    if not quiet:
        show_tool_call(name, tool_input)
    fn = TOOL_FUNCS.get(name)
    output = fn(tool_input) if fn else f"Error: unknown tool {name}"
    if not quiet:
        show_tool_result(output)
    return output
