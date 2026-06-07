# ✻ BOYSER AI

![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)
![Release](https://img.shields.io/github/v/release/nanofatdog/boyser-ai)
![License](https://img.shields.io/badge/license-MIT-green)

CLI coding agent สไตล์ Claude Code — รันบนเครื่องตัวเอง ใช้ได้ทั้ง **Claude API**, **Cloud API** (OpenRouter / Groq / DeepSeek / OpenAI / Together / Gemini) และ**โมเดล local ฟรี** (Ollama / llama.cpp) — รองรับทั้ง **Linux และ Windows**

![BOYSER AI screenshot](assets/screenshot.png)

💥 **Fork โดย UKA (18yo hacker)** — ปรับปรุงจาก [apgamerinfo/boyser-ai](https://github.com/apgamerinfo/boyser-ai) ด้วย additional capabilities

## ฟีเจอร์ (อัปเกรด)

### Core Agent
- **Agentic loop** — โมเดลเรียก tools วนจนงานเสร็จ
- **16 tools** (จากเดิม 12): `bash` `read_file` `write_file` `edit_file` `glob` `grep` `web_search` `web_fetch` `todo_write` `remember` `use_skill` `ask_user` **+ `vision` `patch` `search_files` `subagent`**
- **42 skills** ติดมาให้ — โหลดแบบ progressive disclosure
- **Memory ข้าม session** + auto-load ไฟล์โปรเจกต์
- **UI แบบ Claude Code** — กล่องพิมพ์มีกรอบ, slash menu (`/`), 6 ธีมสี, shimmer spinner, ESC หยุดกลางคัน

### ✨ New in this fork

| ฟีเจอร์ | รายละเอียด |
|---------|-----------|
| **🔍 `patch` tool** | Smart find-and-replace — 5 matching strategies (exact, whitespace-normalized, case-insensitive, partial) ไม่พังเพราะ indent ผิด |
| **👁️ `vision` tool** | วิเคราะห์ภาพผ่าน local multimodal model (Ollama/llama.cpp) หรือ URL |
| **🔎 `search_files` tool** | Search เนื้อหาด้วย regex หรือหาไฟล์ด้วย glob — รองรับ output_mode 3 แบบ |
| **🧩 `subagent` tool** | Spawn child agent สำหรับทำงาน parallel — มี tools ของตัวเอง (bash, read/write, grep, glob) |
| **🔌 MCP support** | Model Context Protocol — เชื่อมต่อ MCP servers เพื่อขยาย tools ได้ไม่จำกัด |
| **🏗️ Multi-module** | โค้ด refactor จาก single-file 2424 บรรทัด เป็น package 8 modules — แก้ง่าย maintenance ได้ |

### Architecture (ใหม่)
```
boyser/                    # Package structure (แทน agent.py เดียว)
├── __init__.py            # Package marker
├── __main__.py            # python3 -m boyser
├── config.py              # Constants, paths, TOOLS schema, config I/O
├── interrupt.py           # ESC handler, hard_close, esc_watch
├── repl.py                # prompt_toolkit REPL, slash commands, @ file mentions
├── tools.py               # 16 tool implementations + TOOL_FUNCS dispatch
├── backend.py             # ClaudeBackend + LocalBackend (Ollama/Cloud/llama.cpp)
├── agent.py               # build_system, wizard, main loop
├── mcp.py                 # MCP client — connect external tool servers
└── subagent.py            # SubAgent delegation — parallel child agents

agent.py                   # Thin wrapper (7 บรรทัด → import + main)
```

## ติดตั้ง

ต้องมี Python 3.10+

```bash
git clone https://github.com/nanofatdog/boyser-ai.git
cd boyser-ai
sh install.sh
boyser-ai          # ครั้งแรกจะมี wizard เลือก backend/โมเดล
```

**Windows:** รัน `.\install.bat` แทน

ใช้โมเดล local ฟรี: ติดตั้ง [Ollama](https://ollama.com) แล้ว `ollama pull qwen3-coder`

## ใช้งาน

```bash
boyser-ai                                   # ใช้ config ที่เซฟไว้
boyser-ai --setup                           # เปิด wizard ตั้งค่าใหม่
boyser-ai --local --model qwen3-coder       # บังคับ local ชั่วคราว
boyser-ai --yolo                            # ไม่ถามยืนยัน tool
```

ใน REPL: พิมพ์ `/` ดูเมนูคำสั่ง · `exit` ออก

## เพิ่ม skill เอง

สร้างโฟลเดอร์ที่มี `SKILL.md` (frontmatter `name`/`description`) วางที่ `./.boyser/skills/<ชื่อ>/` (เฉพาะโปรเจกต์) หรือ `~/.config/boyser-ai/skills/<ชื่อ>/` (ทุกที่)

## เชื่อมต่อ MCP servers

สร้าง `~/.config/boyser-ai/mcp_servers.json`:
```json
{
  "servers": [
    {"name": "my-tools", "command": "python3", "args": ["/path/to/mcp-server.py"]}
  ]
}
```

## License

MIT — Forked from [apgamerinfo/boyser-ai](https://github.com/apgamerinfo/boyser-ai)
