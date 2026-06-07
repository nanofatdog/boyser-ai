#!/usr/bin/env python3
"""BOYSER AI — CLI coding agent สไตล์ Claude Code.

Refactored into multi-module package under boyser/.
Run directly: python3 agent.py
Install: sh install.sh  →  boyser-ai
"""

import sys
import os

# Ensure the repo root is on sys.path so `boyser` package is found.
_REPO = os.path.dirname(os.path.abspath(__file__))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from boyser.agent import main

if __name__ == "__main__":
    main()
