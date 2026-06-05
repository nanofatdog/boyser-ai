# BOYSER AI

CLI coding agent แบบ Claude Code รันบนเครื่อง local — ใช้ได้ทั้ง Claude API และโมเดล local (Ollama / llama.cpp).
ไฟล์นี้ถูก auto-load เข้า context ของ agent ทุกครั้งที่รันในโฟลเดอร์นี้ — เป็นทั้ง project ตัวมันเองและ test bed ของมันเอง

## โครงสร้าง

- `agent.py` — ทั้งโปรเจกต์อยู่ในไฟล์เดียว (~1900 บรรทัด) ตั้งใจให้เป็น single-file อ่าน/แก้ง่าย **อย่าแตกเป็นหลายไฟล์โดยไม่จำเป็น**
- `.venv/` — virtualenv (Python 3.12); deps: `anthropic`, `openai`, `rich`, `ddgs`, `questionary`/`prompt_toolkit`, `httpx`, `pyfiglet` (โลโก้ banner; มี fallback ถ้าไม่มี)
- `~/.local/bin/boyser-ai` — launcher (เรียก `boyser-ai` ได้จากทุกที่)
- `~/.config/boyser-ai/` — `config.json` (backend+model, chmod 600 เพราะมี api key), `memory.md` (จำข้าม session), `history` (ประวัติ input)

## รัน / ทดสอบ

```bash
boyser-ai                                          # ใช้ config ที่เซฟไว้ (ครั้งแรกขึ้น wizard)
boyser-ai --setup                                  # เปิด wizard ตั้งค่าใหม่
boyser-ai --local --model qwen3-coder-tools        # บังคับ local ชั่วคราว ไม่แตะ config
boyser-ai --yolo                                   # ไม่ถามยืนยัน tool
.venv/bin/python -m py_compile agent.py            # เช็ค syntax หลังแก้
```

ทดสอบแบบ non-interactive: `printf 'คำถาม\na\nexit\n' | boyser-ai --local --model <m>`
(สำหรับ animation/shimmer ต้องเทสต์ใน PTY จริง เช่น `script -qec "..." /dev/null` — pipe จะเห็นแค่ fallback)

## สถาปัตยกรรม

- 2 backend: `ClaudeBackend` (opus-4-8 default; auth = API key หรือ OAuth login keyless ผ่าน `ant auth login`/`ANTHROPIC_AUTH_TOKEN`) และ `LocalBackend` (OpenAI-compatible — ครอบทั้ง Ollama `:11434/v1`, llama.cpp `:8080/v1`, **และ Cloud API**: OpenRouter/Groq/DeepSeek/OpenAI/Together/Gemini ผ่าน `CLOUD_PROVIDERS` preset, base_url+api_key ใน config). `is_ollama` ตรวจจาก `/api/version` (status 200 + field `version`) — กัน cloud ที่ตอบ 404 หลุดไป native path. **หมายเหตุ: Claude Pro/Max subscription ใช้กับ agent ภายนอกไม่ได้ (ToS) — login เป็น API auth เท่านั้น** ทั้งคู่ stream + แสดง thinking (`Thinking` class, shimmer ใน thread + Live) + บรรทัด usage `⤷ in X · out Y · Zs · W tok/s`
- agentic loop วนจน `stop_reason != tool_use` / ไม่มี tool_calls
- Tools (12): `bash` `read_file` `write_file` `edit_file` `glob` `grep` `web_search` `web_fetch` `todo_write` `remember` `use_skill` `ask_user`. เพิ่ม tool ใหม่ = เพิ่ม dict ใน `TOOLS` + entry ใน `TOOL_FUNCS` (schema เดียวใช้ได้ทั้ง 2 backend; LocalBackend แปลงเป็น OpenAI function อัตโนมัติ)
- system prompt ประกอบที่ `build_system()`: base + memory.md + project file (`BOYSER.md`/`AGENTS.md`/`CLAUDE.md`)
- slash commands ใน REPL: `/help /clear /model /ctx /theme /skills /memory /save /tools /status /statusline /think /update /yolo /exit` (พิมพ์ `/` มี dropdown)
- **เช็คอัปเดต**: `check_update_bg()` (daemon thread ตอนเปิด) เทียบ HEAD กับ `git ls-remote origin` — remote ใหม่กว่า → ขึ้น `⬆ มีเวอร์ชันใหม่` ก่อน prompt; เครื่อง dev ที่ commit ล้ำหน้าไม่เตือน (กันด้วย `merge-base --is-ancestor`). `/update` = `git pull --ff-only` + pip install -r + copytree skills ที่ยังไม่มี (ไม่ทับของ user) แล้วบอกให้รีสตาร์ท. ติดตั้งแบบไม่มี `.git` → ข้ามเงียบๆ
- `/think` = toggle (global `THINK_ON`, เซฟ config) ให้โมเดล local reason ก่อนตอบ — Ollama native ส่ง `think:true` เฉพาะโมเดลที่ `supports_think` (probe จาก `/api/show` capabilities ตอน init); spinner หมุนระหว่างคิด ไม่ dump reasoning. ช้าลงแต่ฉลาดขึ้น (เช่น gemma ทำ logic ยากได้ดีขึ้น). qwen3-coder ไม่รองรับ → เตือน
- `/save` = แยกไฟล์จากคำตอบล่าสุดที่มี marker `FILE: <path>` + code block แล้วเขียนลง cwd (รองรับโฟลเดอร์ย่อย) — ปลดล็อกให้โมเดลที่ขับ tool ไม่เก่ง (เช่น gemma) build multi-file project ได้: ให้มันออกทุกไฟล์เป็นข้อความแล้ว /save. `extract_files()` + system prompt สอนให้ใช้ format นี้ตอนทำ multi-file
- `/memory` = เมนูจัดการ memory.md: ดู / แก้ใน $EDITOR / ลบทีละรายการ / ล้างทั้งหมด — แก้แล้วโหลดใหม่เข้า session ทันที (rebuild จาก `BASE_SYSTEM` + ล้างแชต). memory auto-load ตอนเปิดโปรแกรมเสมอ (`build_system` อ่าน `~/.config/boyser-ai/memory.md`)
- `/status` = Panel สรุป session (model, backend+ctx, cwd+git branch, theme, skills/tools, turns, uptime, tokens ↑↓, config path). `/statusline` = toggle (เซฟ config) แสดง status line ที่ก้นกล่องพิมพ์ (model · ⎇ branch · ↑↓ tokens). token/turn สะสมใน global `SESSION` (อัปเดตใน `usage_line`)
- **Skills** (progressive disclosure แบบ Claude Code): โฟลเดอร์ที่มี `SKILL.md` (frontmatter `name`/`description`) วางได้ที่ `./.boyser/skills/<ชื่อ>/` (project) หรือ `~/.config/boyser-ai/skills/<ชื่อ>/` (global, project ทับ global). `discover_skills()` หา → ใส่ name+description ลง system prompt → โมเดลเรียก tool `use_skill(name)` โหลด body เต็มตอนต้องใช้. `/skills` ดูรายการ. มี 42 skills ติดมาให้ (global ที่ `~/.config/boyser-ai/skills/`): โค้ด (code-review, write-tests, debug, diagnose, refactor, explain-code, security-review, performance, error-explain, tdd, self-check, scrutinize, zoom-out), data/ค้นคว้า (data-analysis, web-research, web-scraping, summarize, sql, pdf-extract, log-analysis), เครื่องมือ (regex, bash-script, dockerfile, api-design, git-commit, git-workflow, docs-write, translate-th, write-a-skill, handoff, caveman), วางแผน/สื่อสาร (grill-me, grill-with-docs, prototype, post-mortem, management-talk, improve-codebase-architecture), สายงานเฉพาะ (adb-android, backtest-review, trade-journal, nextjs-prisma, frontend-design). system prompt โหลดแค่ description
- **ESC = หยุด turn** ระหว่างโมเดลกำลังตอบ: คลาส `Interrupt` (context manager) ตั้ง stdin เป็น cbreak + thread อ่านปุ่ม กด ESC → set event; ลูป stream ทุก backend เช็ค `intr.stopped()` แล้ว break + เก็บข้อความบางส่วน. ทำงานเฉพาะ TTY. ครอบคลุมช่วง "เงียบ" ด้วย: (1) รอ token แรก (โหลดโมเดล/prompt eval) — `esc_watch()` thread ปิด stream ด้วย `hard_close()` ให้หลุดจาก `iter_lines()` ที่ block; (2) ระหว่าง tool หลายตัว/ก่อนรอบถัดไป — เช็คใน tool loop ทุก backend (tool ที่เหลือไม่รัน ใส่ผล `(หยุดโดยผู้ใช้)` แทน เพื่อให้คู่ tool_call/result ครบ ไม่งั้น Claude/OpenAI 400 รอบถัดไป). (3) bash ที่กำลังรัน — `run_bash` ใช้ Popen + `start_new_session` + poll 0.2s: ESC → `killpg` SIGKILL ทั้ง group ทันที (ผล tool = "Error: ถูกหยุดโดยผู้ใช้ (ESC)")

## Conventions

- **ตอบไทยเมื่อ user พิมพ์ไทย** คำเทคนิค (code, path, คำสั่ง, ชื่อ lib) คงเป็นอังกฤษ ห้ามโผล่ภาษาจีน
- โค้ดคอมเมนต์/ข้อความ UI เป็นภาษาไทยได้ ให้เข้ากับของเดิม
- แก้แบบ surgical — แตะเฉพาะที่จำเป็น ไม่ refactor ของที่ไม่เกี่ยว

## Gotchas

- **โมเดล Ollama ที่ import เองด้วย `TEMPLATE {{ .Prompt }}` จะใช้ tools ไม่ได้** (400 "does not support tools") — แก้ด้วย `ollama create <ชื่อเดิม> -f Modelfile` ที่มี `FROM <ตัวเอง>` + `RENDERER`/`PARSER` ตามตระกูล (qwen3moe→`qwen3-coder`, qwen35moe→`qwen3.5`, glm→`glm-4.7`; qwen2 ก๊อป TEMPLATE จาก `qwen2.5-coder:32b`). หา renderer ที่ถูกได้จาก config blob ใน registry
- ปัจจุบัน **ทุกโมเดลใน `ollama list` รองรับ tools แล้ว**
- โมเดล local 30B: สมองคือเพดาน — harness ช่วยได้ระดับหนึ่ง งานยากจริงให้ `/model` ไป Claude API
- `local` backend (llama.cpp /v1) ต้อง `stream_options={"include_usage": True}` ถึงจะได้ token count; tool_calls ประกอบจาก stream deltas ทีละ index
- **num_ctx ตั้งได้เฉพาะผ่าน native `/api/chat`** — Ollama `/v1/chat/completions` เมิน options แล้ว reload ที่ค่า Modelfile เสมอ ดังนั้น `LocalBackend` ตรวจ `is_ollama` (probe `/api/version`) แล้วยิง native (`_turn_ollama`) ที่ส่ง `options.num_ctx` ได้จริง; native ใช้ message shape ของตัวเอง (tool_calls.arguments เป็น dict, tool result ใช้ `role:tool`+`tool_name`)
- `think:true` ใน native จะ **400 ถ้าโมเดลไม่มี thinking** → เช็ค capability จาก `/api/show` ตอน init (`supports_think`) ก่อนส่ง
- ตั้ง ctx: wizard ถามตอนเลือก local, หรือ `/ctx 32768` สดๆ (เซฟลง config, ใช้ตั้งแต่ข้อความถัดไป)
- **Ollama ผ่าน LAN**: wizard branch Ollama ถาม URL (ใส่แค่ IP ได้ — เติม `http://`/`:11434`/`/v1` ให้เอง); ฝั่ง server ตั้ง `OLLAMA_HOST=0.0.0.0` ผ่าน systemd override (`ollama.service.d/lan.conf`). backend ใช้ base_url ตรงๆ ทุก endpoint (probe/native/v1) → remote ทำงานเหมือน localhost
- **web_search snippet ไม่มีคำตอบจริง** (DDGS คืนแค่คำโปรยหน้าเว็บ) → โมเดล local มักสรุปได้แค่ "ที่มา/ลิงก์" เพราะไม่ chain ไป web_fetch เอง. แก้: `web_search` auto-fetch เนื้อหาหน้าแรกที่ใช้ได้ (ลอง 3 อันแรก, >400 chars, แนบ 3000 chars) มาให้เลย + system prompt สั่งให้ fetch ก่อนตอบคำถามข้อเท็จจริง. หมายเหตุ: หน้า JS-heavy (ticker ราคาสด) raw-fetch อาจไม่ได้ตัวเลข — จุดนี้คือเพดานของ fetch แบบไม่ render JS
- **`httpx Response.close()` จาก thread อื่น ไม่ปลุก recv ที่ block อยู่** (คืนทันทีแต่ iter_lines block ต่อจน server ส่งข้อมูล — ทดสอบแล้ว) → ต้อง `shutdown()` socket ดิบจาก `r.extensions["network_stream"].get_extra_info("socket")` ก่อน (= `hard_close()`)
- **โมเดล local พ่น tool call เป็นข้อความบ้าง** (parser ของ engine จับไม่ได้ทุกครั้ง) — qwen2.5 พ่น JSON ดิบ `{"name":...}`, qwen3-coder พ่น `<function=...>` ตอน ctx หนัก. มี `parse_text_toolcalls()` เป็น fallback ดัก 3 ฟอร์แมต (bare/```json JSON, `<tool_call>{json}`, `<function=NAME><parameter=K>V`) + `looks_toolish()` กันไม่ให้ render เป็นข้อความระหว่าง stream. ใช้ทั้ง native และ /v1 path
