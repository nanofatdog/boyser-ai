"""Sub-agent delegation for parallel work in BOYSER AI.

Inspired by Hermes Agent's delegate_task but simplified for running as
subprocess sub-agents that can work on tasks concurrently.

Usage:
    client = SubAgentClient()
    session = client.spawn("Find all TODO comments in src/")
    result = client.wait(session.id)
    print(result.summary)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

# ---------------------------------------------------------------------------
# SubAgentSession
# ---------------------------------------------------------------------------

@dataclass
class SubAgentSession:
    """Tracks a single sub-agent's lifecycle and result."""

    id: str
    goal: str
    status: str = "running"          # running | completed | failed | killed
    summary: str = ""                # final textual output
    tools_called: list[str] = field(default_factory=list)
    started_at: float = 0.0
    completed_at: Optional[float] = None
    process: Optional[subprocess.Popen] = None  # reference to the child process
    _stdout_lines: list[str] = field(default_factory=list)
    _stderr_lines: list[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        end = self.completed_at if self.completed_at else time.time()
        return end - self.started_at

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "goal": self.goal,
            "status": self.status,
            "summary": self.summary,
            "tools_called": self.tools_called,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration": self.duration,
        }


# ---------------------------------------------------------------------------
# Sub-agent Python code (Mode A – self-hosted)
# ---------------------------------------------------------------------------

_SUBAGENT_SCRIPT = r'''"""
BOYSER sub-agent — lightweight autonomous worker.

Reads a JSON goal from stdin, executes it using a limited set of tools
(bash, read_file, write_file, grep, glob), and writes a structured JSON
result to stdout.

Expected stdin format: {"goal": "...", "context": "...", "toolsets": [...]}
Stdout on success:     {"status": "completed", "output": "...", "tools_called": [...]}
Stdout on error:       {"status": "failed", "output": "...", "tools_called": [...]}
"""
import json
import os
import subprocess
import sys
import time
import glob as globlib


def _bash(command: str, timeout: int = 60) -> str:
    """Run a shell command and return its output."""
    try:
        r = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = r.stdout.strip()
        err = r.stderr.strip()
        if err:
            out = (out + "\nSTDERR:\n" + err) if out else err
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return "(command timed out after {}s)".format(timeout)
    except Exception as e:
        return "(error: {})".format(e)


def _read_file(path: str) -> str:
    """Read a text file."""
    try:
        with open(os.path.expanduser(path), "r") as f:
            return f.read()
    except Exception as e:
        return "(error reading {}: {})".format(path, e)


def _write_file(path: str, content: str) -> str:
    """Write content to a file, creating parent dirs if needed."""
    try:
        path = os.path.expanduser(path)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return "wrote {} bytes to {}".format(len(content), path)
    except Exception as e:
        return "(error writing {}: {})".format(path, e)


def _grep(pattern: str, path: str = ".", max_lines: int = 50) -> str:
    """Search for a pattern in files."""
    results = []
    try:
        for root, dirs, files in os.walk(os.path.expanduser(path)):
            # skip hidden dirs and __pycache__
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fn in files:
                fp = os.path.join(root, fn)
                try:
                    with open(fp, "r", errors="replace") as f:
                        for lineno, line in enumerate(f, 1):
                            if pattern in line:
                                results.append("{}:{}:{}".format(fp, lineno, line.rstrip()))
                                if len(results) >= max_lines:
                                    break
                except Exception:
                    pass
                if len(results) >= max_lines:
                    break
            if len(results) >= max_lines:
                break
        return "\n".join(results) if results else "(no matches)"
    except Exception as e:
        return "(grep error: {})".format(e)


def _glob(pattern: str) -> str:
    """Find files matching a glob pattern."""
    try:
        matches = sorted(globlib.glob(pattern, recursive=True))
        return "\n".join(matches) if matches else "(no files matched '{}')".format(pattern)
    except Exception as e:
        return "(glob error: {})".format(e)


_TOOLS = {
    "bash":       {"fn": _bash,       "desc": "Run a shell command"},
    "read_file":  {"fn": _read_file,  "desc": "Read a text file"},
    "write_file": {"fn": _write_file, "desc": "Write content to a file"},
    "grep":       {"fn": _grep,       "desc": "Search for a pattern in files"},
    "glob":       {"fn": _glob,       "desc": "Find files by glob pattern"},
}


def run_goal(goal: str, context: str = "", max_steps: int = 10) -> dict:
    """Execute a goal by iteratively choosing and running tools."""
    tools_called = []
    output_parts = []
    workdir = context.strip() or os.getcwd()
    os.chdir(workdir)

    # Simple prompt for the simulated "thinking"
    prompt = (
        "You are a BOYSER sub-agent. Your task:\n"
        "{}\n\n"
        "You have these tools: {}\n\n"
        "Think step by step. For each step, output a JSON line:\n"
        '  {{"tool": "<name>", "args": {{...}}}}\n'
        "When done, output:\n"
        '  {{"done": true, "summary": "..."}}\n'
        "---\n".format(goal, ", ".join(sorted(_TOOLS.keys())))
    )

    lines = prompt.split("\n")
    output_parts.append("Goal: {}".format(goal))

    for step in range(max_steps):
        # --- Decide what to do based on previous results ---
        # We use a simple heuristic: try relevant tools based on what we've seen.
        if "find" in goal.lower() or "search" in goal.lower() or "grep" in goal.lower():
            # Try grep with a reasonable pattern derived from the goal
            import re
            # Extract likely search terms from the goal
            words = [w for w in goal.split() if len(w) > 3 and not w.lower() in ("find", "search", "grep", "for", "the", "with", "that", "this", "what", "where", "which")]
            search_term = words[-1] if words else "TODO"
            tool = "grep"
            args = {"pattern": search_term, "path": workdir, "max_lines": 30}
        elif "read" in goal.lower() or "show" in goal.lower() or "open" in goal.lower():
            # Try to find and read files
            for word in goal.split():
                if "." in word and not word.startswith("-"):
                    tool = "read_file"
                    args = {"path": word}
                    break
            else:
                tool = "glob"
                args = {"pattern": "*"}
        elif "write" in goal.lower() or "create" in goal.lower() or "make" in goal.lower():
            tool = "bash"
            args = {"command": "echo '[Sub-agent needs more info to write files]'"}
        elif "count" in goal.lower() or "list" in goal.lower() or "tree" in goal.lower():
            tool = "bash"
            args = {"command": "find . -type f | head -50"}
        else:
            tool = "bash"
            args = {"command": "echo '[Exploring...]' && ls -la && pwd"}

        # --- Execute ---
        func = _TOOLS.get(tool, {}).get("fn")
        if not func:
            result = "(unknown tool: {})".format(tool)
        else:
            try:
                result = func(**args)
            except TypeError as e:
                result = "(tool error: {} - args were {})".format(e, args)

        tools_called.append(tool)
        arg_summary = "; ".join("{}={}".format(k, v) for k, v in args.items())
        output_parts.append("Step {}: {}({})".format(step + 1, tool, arg_summary))
        output_parts.append(result[:2000])  # cap output size

        # --- Check if done: if grep found results, read_file found content,
        #     or we got useful output, we can summarise. ---
        if result and not result.startswith("(no ") and not result.startswith("(error") and not result.startswith("(command timed"):
            if step >= 1:  # at least 2 steps before concluding
                break

    output = "\n\n".join(output_parts)
    return {
        "status": "completed",
        "output": output,
        "tools_called": tools_called,
    }


def main() -> None:
    """Entry point for sub-agent subprocess."""
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: treat entire stdin as the goal
        data = {"goal": raw.strip(), "context": ""}

    goal = data.get("goal", "")
    context = data.get("context", "")
    toolsets = data.get("toolsets", [])

    if not goal:
        result = {"status": "failed", "output": "No goal provided.", "tools_called": []}
    else:
        result = run_goal(goal, context, max_steps=10)

    sys.stdout.write(json.dumps(result))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
'''


# ---------------------------------------------------------------------------
# SubAgentClient
# ---------------------------------------------------------------------------

class SubAgentClient:
    """Client for spawning and managing sub-agent processes.

    Two transport modes:
      Mode A (default): Self-hosted — spawns a child Python process with
                        the sub-agent script, goal injected via stdin.
      Mode B (future):  Remote agent API via HTTP (not yet implemented).
    """

    def __init__(self, mode: str = "A", max_concurrent: int = 3, max_total: int = 10):
        if mode not in ("A", "B"):
            raise ValueError("mode must be 'A' or 'B', got {!r}".format(mode))
        self.mode = mode
        self.manager = SubAgentManager(max_concurrent=max_concurrent, max_total=max_total)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def spawn(
        self,
        goal: str,
        context: Optional[str] = None,
        toolsets: Optional[list[str]] = None,
    ) -> SubAgentSession:
        """Spawn a child sub-agent process to work on *goal*.

        Parameters
        ----------
        goal : str
            The task description for the sub-agent.
        context : str or None
            Working directory or contextual info passed to the sub-agent.
        toolsets : list[str] or None
            Permitted toolset names (not yet enforced in Mode A).

        Returns
        -------
        SubAgentSession
        """
        if self.manager.remaining_slots() <= 0:
            raise RuntimeError(
                "Cannot spawn sub-agent: max_concurrent={}, max_total={}, "
                "active={}, total_created={}".format(
                    self.manager.max_concurrent,
                    self.manager.max_total,
                    self.manager.active_count(),
                    self.manager.total_created,
                )
            )

        session = self.manager.create_session(goal)
        context = context or os.getcwd()

        if self.mode == "A":
            self._spawn_mode_a(session, context, toolsets)
        else:
            raise NotImplementedError("Mode B (remote API) not yet implemented")

        return session

    def poll(self, session_id: str) -> SubAgentSession:
        """Check if a sub-agent process has completed.

        Returns the updated session (non-blocking).
        """
        session = self.manager.get(session_id)
        if session is None:
            raise KeyError("Unknown session: {!r}".format(session_id))

        if session.status != "running":
            return session

        return self._check_session(session)

    def wait(self, session_id: str, timeout: float = 300) -> SubAgentSession:
        """Block until a sub-agent completes or *timeout* seconds elapse.

        Returns the updated session.
        """
        session = self.manager.get(session_id)
        if session is None:
            raise KeyError("Unknown session: {!r}".format(session_id))

        deadline = time.time() + timeout
        while time.time() < deadline:
            session = self._check_session(session)
            if session.status != "running":
                return session
            time.sleep(0.5)

        # Timeout — mark as still running and return
        return session

    def wait_all(self) -> list[SubAgentSession]:
        """Wait for all currently running sub-agents to finish.

        Returns a list of completed sessions.
        """
        results = []
        for session in list(self.manager.active_subagents.values()):
            if session.status == "running":
                try:
                    self.wait(session.id, timeout=300)
                except Exception:
                    pass
            results.append(session)
        return results

    def list(self) -> list[dict]:
        """Return a list of all sub-agent sessions (active + finished)."""
        return [s.to_dict() for s in self.manager.all_sessions()]

    def kill(self, session_id: str) -> SubAgentSession:
        """Terminate a running sub-agent process."""
        session = self.manager.get(session_id)
        if session is None:
            raise KeyError("Unknown session: {!r}".format(session_id))

        if session.process and session.process.poll() is None:
            session.process.terminate()
            try:
                session.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                session.process.kill()
                session.process.wait()

        session.status = "killed"
        session.completed_at = time.time()
        self.manager._finish_session(session)
        return session

    # ------------------------------------------------------------------
    # Internal helpers — Mode A (subprocess)
    # ------------------------------------------------------------------

    def _spawn_mode_a(
        self,
        session: SubAgentSession,
        context: str,
        toolsets: Optional[list[str]] = None,
    ) -> None:
        """Spawn via subprocess.Popen with goal on stdin (non-blocking, threaded)."""
        payload = json.dumps({
            "goal": session.goal,
            "context": context,
            "toolsets": toolsets or [],
        })

        proc = subprocess.Popen(
            [sys.executable, "-c", _SUBAGENT_SCRIPT],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=context if os.path.isdir(context) else None,
        )
        session.process = proc

        # Run the blocking communicate() in a daemon thread so spawn() returns
        # immediately and multiple sub-agents can run concurrently.
        def _run():
            try:
                stdout_data, stderr_data = proc.communicate(input=payload, timeout=300)
                session._stdout_lines = (
                    stdout_data.strip().split("\n") if stdout_data.strip() else []
                )
                session._stderr_lines = (
                    stderr_data.strip().split("\n") if stderr_data.strip() else []
                )
                self._parse_result(session, stdout_data, stderr_data, proc.returncode)
            except Exception as exc:
                session.status = "failed"
                session.summary = "Sub-agent thread error: {}".format(exc)
                session.completed_at = time.time()
                self.manager._finish_session(session)

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    def _parse_result(
        self,
        session: SubAgentSession,
        stdout_data: str,
        stderr_data: str,
        returncode: int,
    ) -> None:
        """Parse the sub-agent's JSON result and update the session."""
        session.completed_at = time.time()

        if returncode != 0:
            session.status = "failed"
            session.summary = "Sub-agent exited with code {}.\nSTDERR:\n{}".format(
                returncode, stderr_data.strip()
            )
            self.manager._finish_session(session)
            return

        # Try to parse stdout as JSON
        stdout_clean = stdout_data.strip()
        # Handle trailing content after JSON (just in case)
        json_end = stdout_clean.rfind("}")
        if json_end >= 0:
            stdout_clean = stdout_clean[: json_end + 1]

        try:
            result = json.loads(stdout_clean)
        except json.JSONDecodeError:
            session.status = "failed"
            session.summary = "Sub-agent output was not valid JSON.\nOUTPUT:\n{}".format(
                stdout_clean[:2000]
            )
            self.manager._finish_session(session)
            return

        session.status = result.get("status", "completed")
        session.summary = result.get("output", stdout_clean[:2000])
        session.tools_called = result.get("tools_called", [])
        self.manager._finish_session(session)

    def _check_session(self, session: SubAgentSession) -> SubAgentSession:
        """Poll the process once and update status if done."""
        if session.process is None:
            # Process reference not stored (should not happen in normal flow)
            return session

        retcode = session.process.poll()
        if retcode is not None:
            stdout_data = "\n".join(session._stdout_lines)
            stderr_data = "\n".join(session._stderr_lines)
            self._parse_result(session, stdout_data, stderr_data, retcode)

        return session


# ---------------------------------------------------------------------------
# SubAgentManager (singleton)
# ---------------------------------------------------------------------------

class SubAgentManager:
    """Singleton that tracks all running sub-agents across the application."""

    _instance: Optional["SubAgentManager"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        max_concurrent: int = 3,
        max_total: int = 10,
    ):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True
        self.max_concurrent = max_concurrent
        self.max_total = max_total
        self.active_subagents: dict[str, SubAgentSession] = {}
        self._finished: list[SubAgentSession] = []
        self._total_created: int = 0
        self._in_flight: int = 0  # sessions currently running (not yet finished)

    @classmethod
    def get_instance(
        cls,
        max_concurrent: int = 3,
        max_total: int = 10,
    ) -> "SubAgentManager":
        """Return the singleton SubAgentManager, creating it if needed."""
        if cls._instance is None:
            cls._instance = cls(
                max_concurrent=max_concurrent,
                max_total=max_total,
            )
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (useful for testing)."""
        cls._instance = None

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def active_count(self) -> int:
        return self._in_flight

    def remaining_slots(self) -> int:
        """Returns how many more sub-agents can be spawned right now."""
        concurrent_remaining = self.max_concurrent - self._in_flight
        total_remaining = self.max_total - self._total_created
        if total_remaining <= 0:
            return 0
        return max(0, min(concurrent_remaining, total_remaining))

    @property
    def total_created(self) -> int:
        return self._total_created

    def get(self, session_id: str) -> Optional[SubAgentSession]:
        session = self.active_subagents.get(session_id)
        if session is not None:
            return session
        for s in self._finished:
            if s.id == session_id:
                return s
        return None

    def all_sessions(self) -> list[SubAgentSession]:
        return list(self.active_subagents.values()) + self._finished

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def create_session(self, goal: str) -> SubAgentSession:
        """Create a new session and register it as active."""
        if self._total_created >= self.max_total:
            raise RuntimeError(
                "Max total sub-agents ({}) reached.".format(self.max_total)
            )
        if self._in_flight >= self.max_concurrent:
            raise RuntimeError(
                "Max concurrent sub-agents ({}) reached. "
                "Wait for some to complete before spawning more.".format(
                    self.max_concurrent
                )
            )

        session = SubAgentSession(
            id=str(uuid.uuid4())[:8],
            goal=goal,
            started_at=time.time(),
        )
        self.active_subagents[session.id] = session
        self._total_created += 1
        self._in_flight += 1
        return session

    def _finish_session(self, session: SubAgentSession) -> None:
        """Move a session from active to finished."""
        self.active_subagents.pop(session.id, None)
        self._in_flight = max(0, self._in_flight - 1)
        if session not in self._finished:
            self._finished.append(session)


# ---------------------------------------------------------------------------
# Standalone convenience function
# ---------------------------------------------------------------------------

def spawn_subagent(
    goal: str,
    context: Optional[str] = None,
    toolsets: Optional[list[str]] = None,
    max_concurrent: int = 3,
    max_total: int = 10,
    timeout: float = 300,
) -> dict:
    """One-shot convenience: create a client, spawn, wait, return result dict.

    Parameters
    ----------
    goal : str
        Task description for the sub-agent.
    context : str or None
        Working directory (defaults to cwd).
    toolsets : list[str] or None
        Optional toolset names.
    max_concurrent : int
        Max concurrent sub-agents (default 3).
    max_total : int
        Max total sub-agents (default 10).
    timeout : float
        Max seconds to wait for completion.

    Returns
    -------
    dict with keys: id, status, summary, tools_called, duration
    """
    client = SubAgentClient(max_concurrent=max_concurrent, max_total=max_total)
    session = client.spawn(goal, context=context, toolsets=toolsets)
    session = client.wait(session.id, timeout=timeout)
    return session.to_dict()


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------

__all__ = [
    "SubAgentSession",
    "SubAgentClient",
    "SubAgentManager",
    "spawn_subagent",
]
