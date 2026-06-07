<div align="center">
  <img src="assets/screenshot.png" alt="BOYSER AI" width="700" style="border-radius:8px">
  <br><br>
  <h1>✻ BOYSER AI</h1>
  <p>
    <strong>CLI coding agent — สไตล์ Claude Code รันบนเครื่องคุณ</strong><br>
    <em>Claude Code-style AI coding agent, fully local or cloud</em>
  </p>
  <p>
    <a href="#features"><img src="https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-blue" alt="Platform"></a>
    <a href="#installation"><img src="https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python"></a>
    <a href="https://github.com/nanofatdog/boyser-ai/releases"><img src="https://img.shields.io/github/v/release/nanofatdog/boyser-ai?color=green&logo=github" alt="Release"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
    <a href="https://github.com/nanofatdog/boyser-ai/actions"><img src="https://img.shields.io/github/actions/workflow/status/nanofatdog/boyser-ai/ci.yml?branch=main&label=tests" alt="CI"></a>
    <img src="https://img.shields.io/badge/🇹🇭_Thai_ready-✅-brightgreen" alt="Thai ready">
  </p>
  <br>
</div>

---

## 📋 สารบัญ / Table of Contents

- [🇹🇭 ภาษาไทย](#-ภาษาไทย)
  - [BOYSER AI คืออะไร?](#boyser-ai-คืออะไร)
  - [✨ อะไรใหม่ใน Fork นี้?](#-อะไรใหม่ใน-fork-นี้)
  - [🔧 วิธีติดตั้ง](#-วิธีติดตั้ง)
  - [🚀 วิธีใช้](#-วิธีใช้)
  - [⚡ 16 เครื่องมือ (Tools)](#-16-เครื่องมือ-tools)
  - [🧠 42 Skills](#-42-skills)
  - [🔌 MCP Integration](#-mcp-integration)
  - [🧩 SubAgent](#-subagent)
  - [⌨️ คำสั่งในโปรแกรม](#️-คำสั่งในโปรแกรม)
- [🇬🇧 English](#-english)
  - [What is BOYSER AI?](#what-is-boyser-ai)
  - [✨ What's New in This Fork?](#-whats-new-in-this-fork)
  - [🔧 Installation](#-installation)
  - [🚀 Quick Start](#-quick-start)
  - [⚡ 16 Tools](#-16-tools)
  - [🧠 42 Skills](#-42-skills-1)
  - [🔌 MCP Integration](#-mcp-integration-1)
  - [🧩 SubAgent](#-subagent-1)
  - [⌨️ Slash Commands](#️-slash-commands)

---

# 🇹🇭 ภาษาไทย

## BOYSER AI คืออะไร?

**BOYSER AI** คือ CLI coding agent ที่ทำงานบนเครื่องคุณเอง — ไม่ต้องส่งโค้ดของคุณให้ใคร เหมือน `claude code` แต่ใช้ได้กับหลากหลาย backend:

| Backend | วิธีใช้ | เหมาะกับ |
|---------|--------|----------|
| 🧠 **Claude API** | Anthropic API key (sonnet/opus/haiku) | งานยาก ต้องการความแม่นยำสูง |
| ☁️ **Cloud API** | OpenRouter / Groq / DeepSeek / OpenAI / Together / Gemini | ใช้ API ต่างๆ ผสมกัน |
| 🏠 **Ollama** | โมเดล local ฟรี (qwen3-coder, gemma, llama ฯลฯ) | ทำงานออฟไลน์ ไม่เสียตัง |
| 💻 **llama.cpp** | llama-server OpenAI-compatible | GPU เครื่องตัวเองแรงๆ |

โปรเจกต์นี้ **fork มาจาก** [apgamerinfo/boyser-ai](https://github.com/apgamerinfo/boyser-ai) และได้รับการอัปเกรดครั้งใหญ่โดย **UKA (18yo hacker)** 🚀

---

## ✨ อะไรใหม่ใน Fork นี้?

### 🏗️ สถาปัตยกรรมใหม่ — Multi-Module

จากเดิมโค้ด 2424 บรรทัดในไฟล์เดียว (`agent.py`) → แตกเป็น package 8 modules:

```
boyser/                          # 📦 Package structure
├── __init__.py                  # Entry marker
├── __main__.py                  # python3 -m boyser
├── config.py                    # Constants, paths, TOOLS schema (16 tools), config I/O
├── interrupt.py                 # ESC handler — หยุดโมเดลกลางคัน
├── repl.py                      # prompt_toolkit REPL, slash commands, @ file mentions
├── tools.py                     # 16 tool implementations + dispatch
├── backend.py                   # ClaudeBackend + LocalBackend (Ollama/Cloud/llama.cpp)
├── agent.py                     # build_system, wizard, main loop
├── mcp.py                       # 🔌 NEW — MCP client (Model Context Protocol)
└── subagent.py                  # 🧩 NEW — SubAgent delegation (parallel child agents)

agent.py                         # Thin wrapper 20 บรรทัด
```

### 🛠️ 4 Tools ใหม่ — จาก 12 → 16

| # | Tool | คำอธิบาย |
|---|------|---------|
| 13 | `vision` | วิเคราะห์ภาพผ่าน local multimodal model |
| 14 | `patch` | Smart find-and-replace — 5 strategies ถ้า exact text ไม่เจอ |
| 15 | `search_files` | ค้นหาไฟล์อัจฉริยะ — regex content search + glob file search |
| 16 | `subagent` | Spawn child agent ทำงานเบื้องหลังแบบ parallel |

### 🔌 MCP Support (Model Context Protocol)

เชื่อมต่อ servers ภายนอกเพื่อเพิ่ม tool ได้ไม่จำกัด:
```bash
# สร้างไฟล์ ~/.config/boyser-ai/mcp_servers.json
# แล้ว MCP tool จะถูกค้นพบและใช้งานได้อัตโนมัติ
```

### 🧩 SubAgent Delegation

ทำงานแบบ parallel ได้: โมเดล spawn child agent ไปทำงานเบื้องหลังในขณะที่คุณคุยกันต่อ:
- Child agent มี tools ของตัวเอง (bash, read_file, write_file, grep, glob)
- รองรับ 3 concurrent, 10 total
- เหมาะกับ: วิจัย, ประมวลผลไฟล์, ทดสอบโค้ด

### 📈 สถิติ

| รายการ | ก่อน | หลัง | เพิ่มขึ้น |
|--------|------|------|----------|
| จำนวน tools | 12 | **16** | +33% |
| modules | 1 (single-file) | **8** | +700% |
| บรรทัดโค้ด | 2,424 | **4,451** | +84% |
| ภาษา README | ไทย | **ไทย + English** | bilingual |

---

## 🔧 วิธีติดตั้ง

### ติดตั้งแบบรวดเร็ว (curl → sh) — Linux / macOS

```bash
# แบบใช้ curl (สะดวกที่สุด)
curl -sSL https://raw.githubusercontent.com/nanofatdog/boyser-ai/main/install.sh | sh
```

```bash
# หรือ clone แล้วติดตั้ง
git clone https://github.com/nanofatdog/boyser-ai.git
cd boyser-ai
sh install.sh
```

### ติดตั้งบน Windows

```powershell
# PowerShell (รันเป็น Administrator)
Set-ExecutionPolicy Bypass -Scope Process -Force
iex ((New-Object System.Net.WebClient).DownloadString('https://raw.githubusercontent.com/nanofatdog/boyser-ai/main/install.ps1'))

# หรือใช้ Git Bash
git clone https://github.com/nanofatdog/boyser-ai.git
cd boyser-ai
.\install.bat
```

### ความต้องการพื้นฐาน

- **Python 3.10+** ([python.org](https://python.org))
- **Git** (สำหรับ `/update`)
- **Ollama** (ถ้าจะใช้โมเดล local) — [ollama.com](https://ollama.com) → `ollama pull qwen3-coder`
- **Claude API key** (ถ้าจะใช้ Claude) — [console.anthropic.com](https://console.anthropic.com)

---

## 🚀 วิธีใช้

```bash
boyser-ai                                    # รันด้วย config ที่เซฟไว้
boyser-ai --setup                            # เปิด wizard ตั้งค่าใหม่
boyser-ai --local --model qwen3-coder        # บังคับ local ชั่วคราว
boyser-ai --yolo                             # โหมดไม่ถามยืนยัน (ระวัง!)
```

ในโปรแกรม:
- พิมพ์ `/` ดูรายการคำสั่ง
- พิมพ์ `@file.py` แนบไฟล์ให้โมเดล
- กด `ESC` หยุดโมเดลที่กำลังตอบ
- พิมพ์ `exit` ออกจากโปรแกรม

---

## ⚡ 16 เครื่องมือ (Tools)

BOYSER AI มี tools ให้โมเดลเรียกใช้ทั้งหมด 16 ตัว:

### 📁 File Operations
| Tool | คำอธิบาย | ตัวอย่าง |
|------|---------|----------|
| `read_file` | อ่านไฟล์พร้อมเลขบรรทัด | `read_file("src/main.py")` |
| `write_file` | สร้าง/เขียนทับไฟล์ (แสดง diff ก่อน) | `write_file("index.html", "<h1>Hello</h1>")` |
| `edit_file` | แก้ไขข้อความเฉพาะจุด (exact match) | `edit_file("app.py", "old_text", "new_text")` |
| `patch` | 🔥 **Smart find-and-replace** — 5 strategies: exact, whitespace-normalized, case-insensitive, partial | `patch("config.py", "DEBUG=True", "DEBUG=False")` |
| `search_files` | 🔥 **ค้นหาไฟล์อัจฉริยะ** — regex content search หรือ glob file search | `search_files("def main", target="content", file_glob="*.py")` |
| `glob` | หาไฟล์ตาม pattern (เรียงตามเวลาแก้ไข) | `glob("**/*.py")` |
| `grep` | ค้นหาข้อความในไฟล์ (regex) | `grep("import os", path="src/")` |

### 🌐 Web
| Tool | คำอธิบาย | ตัวอย่าง |
|------|---------|----------|
| `web_search` | ค้นหาเว็บ (DuckDuckGo) — auto-fetch หน้าที่ดีที่สุดให้ | `web_search("Python 3.13 release date")` |
| `web_fetch` | ดึงเนื้อหาจาก URL (HTML stripped) | `web_fetch("https://example.com")` |

### 🖼️ Vision
| Tool | คำอธิบาย | ตัวอย่าง |
|------|---------|----------|
| `vision` | 🔥 **วิเคราะห์ภาพ** — ไฟล์ local หรือ URL ผ่าน local multimodal model | `vision("screenshot.png", "มีอะไรในภาพนี้?")` |

### 💻 Shell
| Tool | คำอธิบาย | ตัวอย่าง |
|------|---------|----------|
| `bash` | รันคำสั่ง shell — timeout 120s, ESC ฆ่าได้ทันที | `bash("pip install flask")` |

### 🧠 Agent Logic
| Tool | คำอธิบาย | ตัวอย่าง |
|------|---------|----------|
| `subagent` | 🔥 **Spawn child agent** ทำงาน parallel | `subagent("วิเคราะห์ log file นี้")` |
| `todo_write` | วางแผนงานหลายขั้นตอน | `todo_write([{task:"ทำ A", status:"in_progress"}])` |
| `remember` | จดจำข้าม session | `remember("User prefers TypeScript")` |
| `use_skill` | โหลด skill สำหรับงานเฉพาะทาง | `use_skill("code-review")` |
| `ask_user` | ถามผู้ใช้เป็นตัวเลือก | `ask_user("เลือก framework?", ["React","Vue"])` |

---

## 🧠 42 Skills

Skills เป็นเหมือนคู่มือเฉพาะทางที่โมเดลโหลดมาใช้ตอนจำเป็น — ระบบ progressive disclosure ช่วยประหยัด context window:

| หมวด | Skills |
|------|--------|
| 🔍 **Code** | code-review, debug, diagnose, refactor, explain-code, security-review, performance, error-explain, tdd, self-check, scrutinize, zoom-out |
| 📊 **Data** | data-analysis, web-research, web-scraping, summarize, sql, pdf-extract, log-analysis |
| 🛠️ **Dev** | regex, bash-script, dockerfile, api-design, git-commit, git-workflow, docs-write, translate-th, write-a-skill, handoff, caveman |
| 📋 **Planning** | grill-me, grill-with-docs, prototype, post-mortem, management-talk, improve-codebase-architecture |
| 🎯 **Domain** | adb-android, backtest-review, trade-journal, nextjs-prisma, frontend-design |

เพิ่ม skill ของคุณเองได้ที่ `~/.config/boyser-ai/skills/<ชื่อ>/SKILL.md`

---

## 🔌 MCP Integration

BOYSER AI รองรับ **Model Context Protocol (MCP)** — มาตรฐานเปิดสำหรับเชื่อมต่อ tools ภายนอก:

1. สร้างไฟล์ตั้งค่า:
```json
// ~/.config/boyser-ai/mcp_servers.json
{
  "servers": [
    {
      "name": "database",
      "command": "python3",
      "args": ["/home/user/mcp-db-server.py"]
    }
  ]
}
```

2. รัน BOYSER AI — MCP tools จะถูกค้นพบอัตโนมัติและเพิ่มเข้าในรายการ tools

3. โมเดลเรียกใช้ MCP tools ได้เหมือน tool ปกติ

---

## 🧩 SubAgent

**SubAgent** ทำงาน parallel — โมเดล spawn child agent ไปทำ研究工作เบื้องหลัง:

```
คุณ: "ช่วยวิเคราะห์ log 100 ไฟล์นี้หน่อย"
โมเดล: calls subagent("analyze_logs", context="logs/...")
       └── Child agent #1: อ่าน log → หา error → สรุปผล
คุณคุยต่อกับโมเดลเรื่องอื่นไปพร้อมกัน...
Child agent #1: "เจอ 23 errors, 5 warnings — รายละเอียด..."
```

ข้อดี:
- ไม่ต้องรอ — คุยต่อได้เลย
- Child agent มี context ของตัวเอง ไม่รบกวน main conversation
- รองรับ 3 ตัวพร้อมกัน

---

## ⌨️ คำสั่งในโปรแกรม

| คำสั่ง | คำอธิบาย |
|-------|---------|
| `/help` | ดูวิธีใช้และรายการคำสั่ง |
| `/model` | เปลี่ยนโมเดล/backend |
| `/theme` | เปลี่ยนธีมสี (6 สี) |
| `/ctx` | ตั้ง context window size |
| `/think` | เปิด/ปิด reasoning สำหรับโมเดล local |
| `/vote` | เปิด/ปิด vote 3 รอบสำหรับเอกสารยาว |
| `/memory` | จัดการความจำข้าม session |
| `/save` | บันทึกหลายไฟล์จากคำตอบล่าสุด |
| `/skills` | ดูรายการ skills |
| `/status` | สรุปสถานะ session |
| `/statusline` | แสดง status bar ล่าง |
| `/update` | อัปเดตเป็นเวอร์ชันล่าสุด |
| `/yolo` | โหมดไม่ถามยืนยัน |
| `/clear` | ล้างหน้าจอและประวัติ |
| `/exit` | ออกจากโปรแกรม |

---

<div align="center">
  <br>
  <p><strong>Made with ❤️ by <a href="https://github.com/nanofatdog">UKA (18yo hacker)</a></strong></p>
  <p>
    <a href="https://github.com/nanofatdog/boyser-ai">GitHub</a> ·
    <a href="https://github.com/nanofatdog/boyser-ai/issues">Report Bug</a> ·
    <a href="https://github.com/nanofatdog/boyser-ai/discussions">Discussions</a>
  </p>
  <p>
    <sub>Forked from <a href="https://github.com/apgamerinfo/boyser-ai">apgamerinfo/boyser-ai</a> · MIT License</sub>
  </p>
</div>

---

# 🇬🇧 English

## What is BOYSER AI?

**BOYSER AI** is a CLI coding agent that runs on your machine — your code never leaves your computer. Like `claude code`, but works with multiple backends:

| Backend | Auth | Best for |
|---------|------|----------|
| 🧠 **Claude API** | API key or OAuth | Complex reasoning, production code |
| ☁️ **Cloud API** | API key | OpenRouter, Groq, DeepSeek, OpenAI, Together, Gemini |
| 🏠 **Ollama** | None (local) | Free local models, offline |
| 💻 **llama.cpp** | None (local) | GPU-powered local inference |

This project is a **fork** of [apgamerinfo/boyser-ai](https://github.com/apgamerinfo/boyser-ai) with major upgrades by **UKA (18yo hacker)** 🚀

---

## ✨ What's New in This Fork?

### 🏗️ Multi-Module Architecture

Refactored from a single 2424-line file into an 8-module package:

```
boyser/                          # 📦 Package
├── __init__.py
├── __main__.py                  # python3 -m boyser
├── config.py                    # Constants, paths, TOOLS schema, config I/O
├── interrupt.py                 # ESC key handler
├── repl.py                      # prompt_toolkit REPL, slash commands, @ mentions
├── tools.py                     # 16 tool implementations + dispatch
├── backend.py                   # ClaudeBackend + LocalBackend
├── agent.py                     # build_system, wizard, main loop
├── mcp.py                       # 🔌 NEW — MCP client
└── subagent.py                  # 🧩 NEW — SubAgent delegation

agent.py                         # Thin wrapper (20 lines)
```

### 🛠️ 4 New Tools (12 → 16)

| # | Tool | Description |
|---|------|-------------|
| 13 | `vision` | Analyze images via local multimodal model |
| 14 | `patch` | Smart find-and-replace — 5 fuzzy matching strategies |
| 15 | `search_files` | Intelligent file search — regex content + glob name |
| 16 | `subagent` | Spawn background child agents for parallel work |

### 🔌 MCP Support

Connect external tool servers via Model Context Protocol:
- Tools discovered automatically at startup
- Use any MCP-compatible tool server
- Configure via `~/.config/boyser-ai/mcp_servers.json`

### 🧩 SubAgent Delegation

Parallel task execution: the model spawns child agents to work in the background while you continue your conversation:
- Each child has its own toolset (bash, read_file, write_file, grep, glob)
- Up to 3 concurrent, 10 total
- Perfect for: research, batch processing, testing

### 📈 Stats

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Tools | 12 | **16** | +33% |
| Modules | 1 (single-file) | **8** | +700% |
| Lines of code | 2,424 | **4,451** | +84% |
| README language | Thai only | **Bilingual (TH/EN)** | |

---

## 🔧 Installation

### Quick Install — Linux / macOS

```bash
# One-liner (easiest)
curl -sSL https://raw.githubusercontent.com/nanofatdog/boyser-ai/main/install.sh | sh

# Or clone then install
git clone https://github.com/nanofatdog/boyser-ai.git
cd boyser-ai
sh install.sh
```

### Windows

```powershell
# PowerShell (run as Administrator)
Set-ExecutionPolicy Bypass -Scope Process -Force
iex ((New-Object System.Net.WebClient).DownloadString('https://raw.githubusercontent.com/nanofatdog/boyser-ai/main/install.ps1'))

# Or via Git Bash
git clone https://github.com/nanofatdog/boyser-ai.git
cd boyser-ai
.\install.bat
```

### Prerequisites

- **Python 3.10+** ([download](https://python.org))
- **Git** (for `/update` support)
- **Ollama** (for local models) — [ollama.com](https://ollama.com) → `ollama pull qwen3-coder`
- **Claude API key** (for Claude) from [console.anthropic.com](https://console.anthropic.com)

---

## 🚀 Quick Start

```bash
boyser-ai                                    # Run with saved config
boyser-ai --setup                            # Open setup wizard
boyser-ai --local --model qwen3-coder        # Force local model (temporary)
boyser-ai --yolo                             # Skip all confirmations
```

Inside the REPL:
- Press `/` to see slash commands
- Type `@file.py` to attach a file
- Press `ESC` to stop the model mid-response
- Type `exit` to quit

---

## ⚡ 16 Tools

### 📁 File Operations
| Tool | Description |
|------|-------------|
| `read_file` | Read a file with line numbers |
| `write_file` | Create/overwrite a file (shows diff) |
| `edit_file` | Exact string replacement (shows diff) |
| `patch` | 🔥 **Smart find-and-replace** — 5 fuzzy strategies: exact, whitespace-normalized, case-insensitive, partial substring |
| `search_files` | 🔥 **Intelligent file search** — regex content mode OR glob file name mode, with 3 output formats |
| `glob` | Find files by glob pattern (sorted by modification time) |
| `grep` | Recursive regex file search (skips .git/.venv/node_modules) |

### 🌐 Web
| Tool | Description |
|------|-------------|
| `web_search` | DuckDuckGo web search — auto-fetches the top result's content |
| `web_fetch` | Fetch URL content (HTML stripped) |

### 🖼️ Vision
| Tool | Description |
|------|-------------|
| `vision` | 🔥 **Image analysis** via local multimodal model (Ollama/llama.cpp) |

### 💻 Shell
| Tool | Description |
|------|-------------|
| `bash` | Run shell commands — 120s timeout, ESC kills instantly |

### 🧠 Agent Logic
| Tool | Description |
|------|-------------|
| `subagent` | 🔥 **Spawn child agent** for parallel background work |
| `todo_write` | Create/update multi-step task plan |
| `remember` | Save facts across sessions |
| `use_skill` | Load specialized skill instructions |
| `ask_user` | Ask the user with structured options |

---

## 🧠 42 Skills

Skills are specialized guides that the model loads on demand — progressive disclosure saves context:

| Category | Skills |
|----------|--------|
| 🔍 **Code** | code-review, debug, diagnose, refactor, explain-code, security-review, performance, error-explain, tdd, self-check, scrutinize, zoom-out |
| 📊 **Data** | data-analysis, web-research, web-scraping, summarize, sql, pdf-extract, log-analysis |
| 🛠️ **Dev Tools** | regex, bash-script, dockerfile, api-design, git-commit, git-workflow, docs-write, translate-th, write-a-skill, handoff, caveman |
| 📋 **Planning** | grill-me, grill-with-docs, prototype, post-mortem, management-talk, improve-codebase-architecture |
| 🎯 **Domain** | adb-android, backtest-review, trade-journal, nextjs-prisma, frontend-design |

Create your own at `~/.config/boyser-ai/skills/<name>/SKILL.md`

---

## 🔌 MCP Integration

BOYSER AI supports **Model Context Protocol (MCP)** — an open standard for connecting external tools:

1. Create a config file:
```json
// ~/.config/boyser-ai/mcp_servers.json
{
  "servers": [
    {
      "name": "database",
      "command": "python3",
      "args": ["/path/to/mcp-db-server.py"]
    }
  ]
}
```

2. Run BOYSER AI — MCP tools are auto-discovered and added to the tool list.

3. The model can use MCP tools just like built-in tools.

---

## 🧩 SubAgent

**SubAgent** enables parallel task execution:

```
You: "Analyze these 100 log files"
Model: calls subagent("analyze_logs", context="logs/")
       └── Child agent #1: reads logs → finds errors → summarizes
You continue talking about other things...
Child agent #1: "Found 23 errors, 5 warnings — details..."
```

Benefits:
- No waiting — continue your conversation
- Each child has its own isolated context
- Up to 3 concurrent agents

---

## ⌨️ Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | Show help and command list |
| `/model` | Change model/backend |
| `/theme` | Change color theme (6 themes) |
| `/ctx` | Set context window size |
| `/think` | Toggle reasoning mode for local models |
| `/vote` | Toggle 3-round voting for long documents |
| `/memory` | Manage cross-session memory |
| `/save` | Save multiple files from the last response |
| `/skills` | List available skills |
| `/status` | Show session status |
| `/statusline` | Toggle bottom status bar |
| `/update` | Update to the latest version |
| `/yolo` | Toggle no-confirmation mode |
| `/clear` | Clear screen and history |
| `/exit` | Exit the program |

---

<div align="center">
  <br>
  <p><strong>Made with ❤️ by <a href="https://github.com/nanofatdog">UKA (18yo hacker)</a></strong></p>
  <p>
    <a href="https://github.com/nanofatdog/boyser-ai">GitHub</a> ·
    <a href="https://github.com/nanofatdog/boyser-ai/issues">Report Bug</a> ·
    <a href="https://github.com/nanofatdog/boyser-ai/discussions">Discussions</a>
  </p>
  <p>
    <sub>Forked from <a href="https://github.com/apgamerinfo/boyser-ai">apgamerinfo/boyser-ai</a> · MIT License</sub>
  </p>
</div>
