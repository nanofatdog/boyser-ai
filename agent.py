#!/usr/bin/env python3
"""BOYSER AI — CLI coding agent สไตล์ Claude Code.

Refactored into multi-module package under boyser/.
Run directly: python3 agent.py
Install: sh install.sh  →  boyser-ai

Usage:
  python3 agent.py              # เปิด interactive session
  python3 agent.py --version    # ดูเวอร์ชัน
  python3 agent.py --help       # ดูตัวเลือกทั้งหมด
  python3 agent.py --local --model qwen3-coder-tools   # ใช้ local model
"""

import sys
import os

# Ensure the repo root is on sys.path so `boyser` package is found.
_REPO = os.path.dirname(os.path.abspath(__file__))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from boyser import __version__, __version_hash__, __version_date__

if __name__ == "__main__":
    # Handle --version before importing everything (fastest path)
    if "--version" in sys.argv or "-V" in sys.argv:
        if __version__:
            print(f"BOYSER AI {__version__} ({__version_hash__} · {__version_date__})")
        else:
            print("BOYSER AI (no git repo — version unknown)")
        sys.exit(0)

    from boyser.agent import main

    main()
