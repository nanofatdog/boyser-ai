"""
BOYSER AI — CLI coding agent สไตล์ Claude Code
รันบนเครื่อง local: Claude API / Cloud API / Ollama / llama.cpp
42+ skills · MCP · Subagents · Vision

Version auto-generated from git commit count.
"""

__version__ = ""
__version_hash__ = ""
__version_date__ = ""


def _load_version():
    """Read version from git at import time."""
    global __version__, __version_hash__, __version_date__
    import subprocess, os

    _dir = os.path.dirname(os.path.abspath(__file__))
    _root = os.path.dirname(_dir)
    try:
        n = subprocess.run(
            ["git", "-C", _root, "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, timeout=3,
        ).stdout.strip()
        info = subprocess.run(
            ["git", "-C", _root, "log", "-1", "--format=%h %cs"],
            capture_output=True, text=True, timeout=3,
        ).stdout.strip()
        if n and info and len(info.split()) == 2:
            h, d = info.split()
            __version__ = f"v{n}"
            __version_hash__ = h
            __version_date__ = d
    except Exception:
        pass


_load_version()
del _load_version
