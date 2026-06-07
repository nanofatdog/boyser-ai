"""
MCP (Model Context Protocol) client for BOYSER AI.
Connects external MCP-compatible tools via stdio subprocesses.

MCP JSON-RPC protocol:
  - Initialize handshake → tools/list discovery → tools/call invocations
  - Stdio transport: one JSON-RPC message per line on stdin/stdout
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from typing import Any

from .config import CONFIG_DIR

# ── paths & constants ───────────────────────────────────────────────

MCP_CONFIG_PATH = os.path.join(CONFIG_DIR, "mcp_servers.json")

_MCP_PROTOCOL_VERSION = "2024-11-05"
_CLIENT_INFO = {"name": "boyser-ai", "version": "1.0"}
_DEFAULT_TIMEOUT = 30.0  # seconds per JSON-RPC round-trip

# thread-safe message id counter
_ID_COUNTER = 0
_ID_LOCK = threading.Lock()


def _next_id() -> int:
    global _ID_COUNTER
    with _ID_LOCK:
        _ID_COUNTER += 1
        return _ID_COUNTER


# ── exceptions ──────────────────────────────────────────────────────

class MCPConnectionError(Exception):
    """Raised when MCP connection or communication fails."""
    pass


class MCPToolError(Exception):
    """Raised when an MCP tool call returns an error."""
    pass


# ── helpers ─────────────────────────────────────────────────────────

def MCPToolAdapter(mcp_tool: dict) -> dict:
    """Convert an MCP tool descriptor to BOYSER tool format.

    MCP format:  {name, description, inputSchema}
    BOYSER format: {name, description, input_schema}
    """
    return {
        "name": mcp_tool["name"],
        "description": mcp_tool.get("description", ""),
        "input_schema": mcp_tool.get("inputSchema", {}),
    }


def _read_line(stream, timeout: float = _DEFAULT_TIMEOUT) -> str:
    """Read one line from *stream* with a timeout (best-effort on all platforms).

    On Unix this uses ``os.read`` with a select-based timeout.
    On Windows it falls back to ``stream.readline()`` (no reliable per-line
    timeout on binary pipes in CPython — the overall connect/call timeout
    is the safety net).
    """
    if os.name == "nt":
        line = stream.readline()
        if not line:
            raise MCPConnectionError("MCP server closed stdout (EOF)")
        return line.decode("utf-8", errors="replace") if isinstance(line, bytes) else line

    # Unix: select-based timeout via os.read
    import select
    buf = b""
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise MCPConnectionError(f"MCP server read timeout after {timeout}s")
        ready, _, _ = select.select([stream], [], [], max(0.001, remaining))
        if not ready:
            continue
        chunk = os.read(stream.fileno(), 65536)
        if not chunk:
            raise MCPConnectionError("MCP server closed stdout (EOF)")
        buf += chunk
        if b"\n" in buf:
            line, *_ = buf.split(b"\n", 1)
            return line.decode("utf-8", errors="replace")


def _send_line(proc: subprocess.Popen, data: dict, timeout: float = _DEFAULT_TIMEOUT) -> None:
    """Write a JSON-RPC request to *proc* stdin."""
    raw = (json.dumps(data, ensure_ascii=False) + "\n").encode("utf-8")
    stdin = proc.stdin
    if stdin is None:
        raise MCPConnectionError("MCP server stdin is not available")
    try:
        stdin.write(raw)
        stdin.flush()
    except BrokenPipeError:
        raise MCPConnectionError("MCP server stdin broken pipe (process may have crashed)")


def _recv_line(proc: subprocess.Popen, timeout: float = _DEFAULT_TIMEOUT) -> dict:
    """Read one JSON-RPC response line from *proc* stdout."""
    line = _read_line(proc.stdout, timeout=timeout)
    try:
        return json.loads(line)
    except json.JSONDecodeError as e:
        raise MCPConnectionError(f"Invalid JSON from MCP server: {e}")


def _jsonrpc_request(method: str, params: dict | None = None) -> dict:
    """Build a JSON-RPC 2.0 request dict."""
    msg: dict = {"jsonrpc": "2.0", "id": _next_id(), "method": method}
    if params is not None:
        msg["params"] = params
    return msg


# ── server config loading / saving ──────────────────────────────────

def load_mcp_config() -> dict:
    """Load MCP server config from *MCP_CONFIG_PATH*.

    Returns a dict with ``servers`` key::

        {"servers": [{"name": "...", "command": "...", "args": [...]}]}
    """
    try:
        with open(MCP_CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"servers": []}
    if isinstance(data, list):
        return {"servers": data}
    if isinstance(data, dict):
        servers = data.get("servers", [])
        return {"servers": servers if isinstance(servers, list) else []}
    return {"servers": []}


def save_mcp_config(servers: list[dict]) -> None:
    """Save MCP server list to *MCP_CONFIG_PATH*."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(MCP_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({"servers": servers}, f, indent=2, ensure_ascii=False)


# ── MCP client ──────────────────────────────────────────────────────

class MCPClient:
    """Manages connections to MCP servers and their tools.

    Each server entry in ``_servers`` has this structure::

        {
            "proc": subprocess.Popen | None,  # stdio transport
            "connected": bool,
            "tools": [{"name": ..., "description": ..., "input_schema": ...}],
        }
    """

    def __init__(self) -> None:
        self._servers: dict[str, dict] = {}
        self._lock = threading.Lock()

    # ── connection ──────────────────────────────────────────────

    def connect_stdio(
        self,
        name: str,
        command: str,
        args_list: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> list[dict]:
        """Spawn an MCP server as a subprocess, perform the MCP initialize
        handshake, and discover its tools.

        Parameters
        ----------
        name:
            Logical name for this server (used as key in ``_servers``).
        command:
            Executable path or name.
        args_list:
            Additional CLI arguments for the subprocess.
        env:
            Optional environment overrides (merged into current env).

        Returns
        -------
        The discovered tools list in BOYSER format.
        """
        if name in self._servers:
            raise ValueError(f"MCP server '{name}' is already connected")

        args = [command] + (args_list or [])
        merged_env = dict(os.environ)
        if env:
            merged_env.update(env)

        try:
            proc = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=merged_env,
            )
        except FileNotFoundError:
            raise MCPConnectionError(
                f"Command '{command}' not found — ensure the executable is installed"
            )
        except OSError as e:
            raise MCPConnectionError(f"Failed to spawn '{command}': {e}")

        entry: dict = {
            "proc": proc,
            "connected": False,
            "tools": [],
        }
        self._servers[name] = entry

        try:
            # 1. initialize handshake
            req = _jsonrpc_request(
                "initialize",
                {
                    "protocolVersion": _MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": _CLIENT_INFO,
                },
            )
            _send_line(proc, req)
            resp = _recv_line(proc)
            if "error" in resp:
                err = resp["error"]
                raise MCPConnectionError(
                    f"MCP initialize error: {err.get('message', err)}"
                )

            # 2. initialized notification (fire-and-forget)
            _send_line(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

            # 3. tool discovery
            req = _jsonrpc_request("tools/list")
            _send_line(proc, req)
            resp = _recv_line(proc)
            if "error" in resp:
                err = resp["error"]
                raise MCPConnectionError(
                    f"MCP tools/list error: {err.get('message', err)}"
                )

            result = resp.get("result", {})
            raw_tools = result.get("tools", [])
            adapted = [MCPToolAdapter(t) for t in raw_tools]
            entry["tools"] = adapted
            entry["connected"] = True

        except Exception:
            self._cleanup_proc(name)
            raise

        return adapted  # list[dict] — caller sees discovered tools

    def connect_http(
        self,
        name: str,
        url: str,
        api_key: str | None = None,
    ) -> dict:
        """Connect to an MCP server via HTTP (not yet implemented).

        This is a placeholder for future HTTP-based MCP transport.
        """
        raise NotImplementedError("HTTP MCP transport is not yet implemented")

    # ── tool invocation ─────────────────────────────────────────

    def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> Any:
        """Call a tool on the specified MCP server.

        Parameters
        ----------
        server_name:
            Name of the connected server.
        tool_name:
            Name of the tool to invoke.
        arguments:
            Arguments to pass to the tool.
        timeout:
            Per-call timeout in seconds.

        Returns
        -------
        The content list from the tool result (list of ``{type, text}`` dicts).
        """
        entry = self._servers.get(server_name)
        if not entry:
            raise MCPConnectionError(f"No MCP server named '{server_name}'")
        if not entry["connected"]:
            raise MCPConnectionError(f"MCP server '{server_name}' is not connected")
        proc = entry.get("proc")
        if not proc or proc.poll() is not None:
            raise MCPConnectionError(f"MCP server '{server_name}' process has exited")

        req = _jsonrpc_request(
            "tools/call",
            {"name": tool_name, "arguments": arguments or {}},
        )
        _send_line(proc, req, timeout=timeout)
        resp = _recv_line(proc, timeout=timeout)

        if "error" in resp:
            err = resp["error"]
            raise MCPToolError(
                f"MCP tool '{tool_name}' error: {err.get('message', err)}"
            )

        result = resp.get("result", {})
        if "isError" in result and result["isError"]:
            content = result.get("content", [])
            msg = "; ".join(
                c.get("text", "") for c in content if c.get("type") == "text"
            )
            raise MCPToolError(f"MCP tool '{tool_name}' returned error: {msg}")

        return result.get("content", [])

    # ── introspection ───────────────────────────────────────────

    def list_tools(self) -> list[dict]:
        """Return all discovered tools across all servers in BOYSER format.

        Each tool dict has ``name``, ``description``, and ``input_schema``.
        """
        tools: list[dict] = []
        with self._lock:
            for name, entry in self._servers.items():
                if not entry["connected"]:
                    continue
                for t in entry["tools"]:
                    tools.append(t)
        return tools

    def list_servers(self) -> dict[str, int]:
        """Return a dict mapping connected server names to their tool counts."""
        with self._lock:
            return {
                name: len(entry["tools"])
                for name, entry in self._servers.items()
                if entry["connected"]
            }

    def get_server_info(self, name: str) -> dict | None:
        """Return the server entry dict for *name*, or ``None``."""
        return self._servers.get(name)

    # ── disconnection ───────────────────────────────────────────

    def disconnect(self, name: str) -> None:
        """Disconnect and clean up a single MCP server."""
        self._cleanup_proc(name)
        self._servers.pop(name, None)

    def disconnect_all(self) -> None:
        """Disconnect and clean up all MCP servers."""
        for name in list(self._servers.keys()):
            self._cleanup_proc(name)
        self._servers.clear()

    # ── internal helpers ────────────────────────────────────────

    def _cleanup_proc(self, name: str) -> None:
        """Terminate the subprocess for *name* (if any) and close pipes."""
        entry = self._servers.get(name)
        if not entry:
            return
        proc: subprocess.Popen | None = entry.get("proc")
        if proc is None:
            return
        entry["connected"] = False
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
        except OSError:
            pass
        try:
            if proc.stdout and not proc.stdout.closed:
                proc.stdout.close()
        except OSError:
            pass
        try:
            if proc.stderr and not proc.stderr.closed:
                proc.stderr.close()
        except OSError:
            pass
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        entry["proc"] = None
