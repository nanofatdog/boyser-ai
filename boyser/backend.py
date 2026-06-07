"""Backends: ClaudeBackend (Anthropic) + LocalBackend (OpenAI-compatible / Ollama native)."""

import json
import re
import threading
import time

import httpx
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.text import Text

from boyser.config import (
    SYSTEM,
    TOOLS,
    THEME,
    THINK_ON,
    VOTE_ON,
    MAX_TOOL_ROUNDS,
    longdoc_options,
    vote_consensus,
    strip_special,
    looks_toolish,
    CONFIG_DIR,
)
from boyser.interrupt import hard_close, esc_watch
from boyser.repl import (
    usage_line,
    show_tool_call,
    show_tool_result,
    show_diff,
    build_statusline,
    extract_rate_limits,
    format_tokens,
    console,
)
from boyser.tools import execute_tool, TOOL_FUNCS, confirm, parse_text_toolcalls


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


SESSION = {"in": 0, "out": 0, "cached": 0, "turns": 0, "started": 0.0, "rem_tokens": None, "reset_tokens": None}
_status_ctx: dict = {"backend": None, "on": False}


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
                    # ESC ระหว่าง tool → ข้ามตัวที่เหลือ แต่ใส่ tool_result ครบทุก id (กัน API 400 รอบถัดไป)
                    if intr and intr.stopped():
                        output = "(หยุดโดยผู้ใช้ด้วย ESC)"
                    else:
                        output = execute_tool(block.name, block.input)
                    results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": output}
                    )
            messages.append({"role": "user", "content": results})
            if intr and intr.stopped():
                console.print("[dim]⊘ หยุดแล้ว (ESC)[/]")
                return


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
        # Ollama หลัง auth proxy (เช่น Cloudflare Tunnel + Bearer key) → แนบ header ทุก call native
        self.headers = {"Authorization": f"Bearer {cfg['api_key']}"} if cfg.get("api_key") else {}
        try:
            r = httpx.get(self.api_base + "/api/version", timeout=5, headers=self.headers)
            # ต้องเป็น Ollama จริง (status 200 + มี field version) — กัน cloud API ที่ตอบ 404 เฉยๆ
            if r.status_code == 200 and "version" in r.json():
                self.is_ollama = True
                caps = httpx.post(
                    self.api_base + "/api/show", json={"model": self.model}, timeout=5,
                    headers=self.headers,
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
            opts = longdoc_options(messages)
            if self.num_ctx:
                opts["num_ctx"] = self.num_ctx
            if opts:
                payload["options"] = opts

            content = ""
            calls: list = []
            usage = None
            live = None
            think = Thinking()
            watch = threading.Event()
            try:
                with httpx.stream("POST", f"{self.api_base}/api/chat", json=payload, timeout=None,
                                  headers=self.headers) as r:
                    watch = esc_watch(intr, lambda: hard_close(r))  # ESC ตอนรอ token แรก → ปลุกให้หลุด block
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
            except Exception:
                if not (intr and intr.stopped()):
                    raise  # error จริง — ไม่ใช่ esc_watch ปิด stream เพราะ ESC
            finally:
                watch.set()
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
                # รอบที่ตอบจริง (ไม่มี tool call — จะรอบแรกหรือหลัง tool ก็ได้) บนเอกสารยาว
                # → vote หา consensus กันคำตอบไม่นิ่ง
                if (VOTE_ON and content.strip()
                        and longdoc_options(messages) and not (intr and intr.stopped())):
                    final = vote_consensus(self, messages, strip_special(content), intr)
                    if final is not None:
                        messages[-1]["content"] = final  # turn ต่อไปต่อยอดจาก consensus
                return

            sig = "|".join(f"{c['name']}:{json.dumps(c['args'], sort_keys=True, default=str)}" for c in calls)
            if sig and sig == prev_sig:  # เรียก tool เดิมซ้ำเป๊ะ = ติด loop → หยุดทันที
                console.print("[red]⊘ หยุด: โมเดลเรียก tool เดิมซ้ำ (ติด loop)[/]")
                return
            prev_sig = sig

            for c in calls:
                if intr and intr.stopped():  # ESC ระหว่าง tool → ข้ามตัวที่เหลือ แต่ใส่ผลครบให้ประวัติ valid
                    output = "(หยุดโดยผู้ใช้ด้วย ESC)"
                else:
                    args = c["args"] if isinstance(c["args"], dict) else json.loads(c["args"] or "{}")
                    output = execute_tool(c["name"], args)
                messages.append({"role": "tool", "tool_name": c["name"], "content": output})
            if intr and intr.stopped():
                console.print("[dim]⊘ หยุดแล้ว (ESC)[/]")
                return

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
            watch = esc_watch(intr, lambda: hard_close(stream.response))  # ESC ตอนรอ token แรก → ปลุกให้หลุด block
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
            except Exception:
                if not (intr and intr.stopped()):
                    raise  # error จริง — ไม่ใช่ esc_watch ปิด stream เพราะ ESC
            finally:
                watch.set()
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
                if intr and intr.stopped():  # ESC ระหว่าง tool → ข้ามตัวที่เหลือ แต่ใส่ผลครบให้ประวัติ valid
                    output = "(หยุดโดยผู้ใช้ด้วย ESC)"
                else:
                    try:
                        args = json.loads(c["args"] or "{}")
                    except json.JSONDecodeError:
                        output = "Error: invalid JSON in tool arguments."
                    else:
                        output = execute_tool(c["name"], args)
                messages.append(
                    {"role": "tool", "tool_call_id": c["id"] or f"call_{i}", "content": output}
                )
            if intr and intr.stopped():
                console.print("[dim]⊘ หยุดแล้ว (ESC)[/]")
                return


def make_backend(cfg: dict):
    return ClaudeBackend(cfg) if cfg["backend"] == "claude" else LocalBackend(cfg)
