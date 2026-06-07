# Changelog

## 2026-06-07 — UKA Major Upgrade 🚀
- **Multi-module refactor**: แยก single-file agent.py (~2400 บรรทัด) เป็น package 8 modules (`boyser/`)
  - `config.py` — constants, paths, TOOLS schema, config I/O
  - `interrupt.py` — ESC handler, hard_close, esc_watch
  - `repl.py` — prompt_toolkit REPL, slash commands, @ file mentions
  - `tools.py` — 16 tool implementations + TOOL_FUNCS dispatch
  - `backend.py` — ClaudeBackend + LocalBackend (Ollama/Cloud/llama.cpp)
  - `agent.py` — build_system, wizard, main loop
  - `mcp.py` — 🔌 NEW: Model Context Protocol client
  - `subagent.py` — 🧩 NEW: SubAgent delegation for parallel work
- **4 new tools** (12 → 16): `vision`, `patch`, `search_files`, `subagent`
- **MCP integration**: auto-discover MCP servers at startup
- **SubAgent delegation**: spawn child agents for background parallel work
- **GitHub Actions CI**: lint (3 Python versions) + security scan
- **AGENTS.md**: project context for AI agents working on this codebase
- **README bilingual**: ไทย + English, beautiful formatting, all features documented
- **curl one-liner install**: `curl -sSL ... | sh` works for Linux/macOS
- **Windows install.ps1**: PowerShell installer
- **Tool descriptions**: all 16 tools rewritten with clear usage guidance
- **Security audit**: verified no secrets/tokens/IPs in code or git history

## 2026-06-07 (upstream)
- **รองรับ Windows**: ติดตั้งด้วย `install.bat` (venv + skills + launcher `boyser-ai.cmd` + เพิ่ม PATH ให้อัตโนมัติ) — ฟีเจอร์ครบเท่า Linux/macOS
  - ESC หยุดกลางคันใช้ `msvcrt` แทน termios/select
  - tool `bash` ใช้ Git Bash อัตโนมัติถ้ามี (หาจาก git บน PATH + ตำแหน่งติดตั้งมาตรฐาน — จงใจไม่ใช้ `which bash` เพราะบน Windows มักได้ WSL ซึ่งเป็นคนละ filesystem) ไม่มีก็ fallback เป็น cmd.exe พร้อมบอกโมเดลใน system prompt ให้เขียนคำสั่ง Windows
  - ฆ่าคำสั่งที่รันค้าง (ESC/timeout) ด้วย `taskkill /F /T` — ฆ่าลูกหลานครบเหมือน `killpg`
  - tool `grep` มี fallback ภาษา Python ตอนเครื่องไม่มี grep binary (ข้าม binary file + จำกัด 5 hit/ไฟล์ เหมือน grep จริง), `glob` กรอง `.venv`/`.git` ถูกแม้ path เป็น backslash, `/memory` เปิด notepad ถ้าไม่ได้ตั้ง EDITOR

## 2026-06-06 (upstream)
- wizard จำค่าเดิม, ESC ย้อนกลับในเมนู, @ไฟล์ autocomplete, /vote เอกสารยาว, /update, version banner

## 2026-06-05 (upstream)
- เผยแพร่ครั้งแรก: agent.py + 42 skills + install.sh
