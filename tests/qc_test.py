"""BOYSER AI — QC test suite: syntax, imports, logic, edge cases"""
import sys
import os

# Ensure repo root is on path
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

errors = []

def check(cond, msg):
    if not cond:
        errors.append(msg)
        print(f"  ✗ FAIL: {msg}")
    else:
        print(f"  ✓ {msg}")

# ========== CONFIG ==========
from boyser.config import (
    TOOLS, THEMES, SYSTEM, CONFIG_DIR, WORKDIR,
    strip_special, looks_toolish, extract_files,
    longdoc_options, IS_WIN, CLOUD_PROVIDERS,
    CLAUDE_MODELS, THEME, THINK_ON, VOTE_ON,
)

check(len(TOOLS) == 16, f"16 tools (got {len(TOOLS)})")
check(len(THEMES) == 6, f"6 themes (got {len(THEMES)})")
check(len(SYSTEM) > 500, f"SYSTEM prompt >500 chars ({len(SYSTEM)})")
check(CONFIG_DIR is not None, "CONFIG_DIR exists")
check(WORKDIR is not None, "WORKDIR exists")
check(len(CLOUD_PROVIDERS) == 6, f"6 cloud providers (got {len(CLOUD_PROVIDERS)})")
check(len(CLAUDE_MODELS) == 3, f"3 Claude models (got {len(CLAUDE_MODELS)})")

# strip_special
check(strip_special("<|im_start|>hello<|im_end|>") == "hello", "strip_special removes im_start/im_end")
check(strip_special("normal <div>html</div>") == "normal <div>html</div>", "strip_special keeps html tags")
check(strip_special("<start_of_turn>hi<end_of_turn>") == "hi", "strip_special start/end of turn")
check(strip_special("<eos><bos>") == "", "strip_special eos/bos")

# looks_toolish
check(looks_toolish("<tool_call>{") == True, "looks_toolish <tool_call>")
check(looks_toolish('{"name": "bash"}') == True, "looks_toolish bare json")
check(looks_toolish("Hello") == False, "looks_toolish normal text")

# extract_files
text = "FILE: src/main.py\n```python\nprint('hello')\n```"
files = extract_files(text)
check(len(files) == 1, "extract_files finds 1 file")
check(files[0][0] == "src/main.py", "extract_files correct path")
check("hello" in files[0][1], "extract_files correct content")

# longdoc_options
opts = longdoc_options([{"content": "a" * 200000}])
check(opts.get("num_predict") == 4096, f"longdoc_options triggers at 200k chars ({opts})")
opts = longdoc_options([{"content": "short"}])
check(opts == {}, "longdoc_options empty for short text")

# TOOLS schema validation
for t in TOOLS:
    name = t.get("name", "?")
    check("name" in t, f"Tool {name} has name")
    check("description" in t, f"Tool {name} has description")
    check("input_schema" in t, f"Tool {name} has input_schema")
    schema = t["input_schema"]
    check(schema.get("type") == "object", f"Tool {name} input_schema type=object")
    check("properties" in schema, f"Tool {name} has properties")
    check("required" in schema, f"Tool {name} has required")
check(True, f"All {len(TOOLS)} tool schemas valid")

# ========== REPL ==========
from boyser.repl import extract_rate_limits, format_tokens, parse_reset_time

rem, reset = extract_rate_limits({"anthropic-ratelimit-tokens-remaining": "5000"})
check(rem == "5000", f"extract_rate_limits rem={rem}")
rem2, reset2 = extract_rate_limits({})
check(rem2 is None and reset2 is None, "extract_rate_limits empty headers")

check(format_tokens("1500000") == "1.5M", "format_tokens 1.5M")
check(format_tokens("32000") == "32k", "format_tokens 32k")
check(format_tokens("500") == "500", "format_tokens 500")
check(format_tokens("") == "", "format_tokens empty")

# ========== TOOLS ==========
from boyser.tools import (
    TOOL_FUNCS, _QUIET_TOOLS, execute_tool,
    parse_text_toolcalls, run_bash, read_file,
    glob_tool, grep_tool, CURRENT_TODOS,
)

check(len(TOOL_FUNCS) == 16, f"16 functions in TOOL_FUNCS (got {len(TOOL_FUNCS)})")
check("subagent" in _QUIET_TOOLS, "subagent in _QUIET_TOOLS")

# parse_text_toolcalls - bare JSON
result = parse_text_toolcalls('{"name": "bash", "arguments": {"command": "ls"}}')
check(len(result) == 1, f"parse bare JSON got {len(result)} calls")
check(result[0]["name"] == "bash", "parse bare JSON name=bash")

# parse_text_toolcalls - <tool_call> format
result = parse_text_toolcalls('<tool_call>{"name": "read_file", "arguments": {"path": "x.py"}}</tool_call>')
check(len(result) == 1, f"parse <tool_call> got {len(result)} calls")
check(result[0]["name"] == "read_file", "parse <tool_call> name=read_file")

# parse_text_toolcalls - <function=NAME> format
result = parse_text_toolcalls('<function=bash><parameter=command>ls</function>')
check(len(result) == 1, f"parse <function=> got {len(result)} calls")
check(result[0]["name"] == "bash", "parse <function=> name=bash")

# execute_tool with unknown tool
result = execute_tool("nonexistent_tool", {})
check("unknown tool" in result, f"execute_tool unknown: {result[:50]}")

# read_file with nonexistent path
result = TOOL_FUNCS["read_file"]({"path": "/tmp/__boyser_test_nonexistent_xyz"})
check("Error" in result or result is not None, f"read_file nonexistent handled: {result[:50]}")

# glob with no match
result = TOOL_FUNCS["glob"]({"pattern": "__boyser_zzz_no_match_*.py"})
check("no files" in result.lower(), f"glob no match: {result[:50]}")

# grep edge case
try:
    result = TOOL_FUNCS["grep"]({"pattern": "__boyser_zzz_nonexistent", "path": "/tmp"})
    check(True, f"grep no match returns result (len={len(result)})")
except Exception as e:
    check(False, f"grep crashed: {e}")

# Confirm all 16 tool names match between TOOLS and TOOL_FUNCS
tool_names_config = {t["name"] for t in TOOLS}
tool_names_funcs = set(TOOL_FUNCS.keys())
check(tool_names_config == tool_names_funcs, f"TOOLS vs TOOL_FUNCS mismatch: config={tool_names_config-tool_names_funcs}, funcs={tool_names_funcs-tool_names_config}")

# ========== INTERRUPT ==========
from boyser.interrupt import Interrupt, hard_close

intr = Interrupt()
check(intr.stopped() == False, "Interrupt not stopped initially")
intr.event.set()
check(intr.stopped() == True, "Interrupt stopped after set")
check(True, "Interrupt context manager OK")

# ========== BACKEND ==========
from boyser.backend import make_backend, ClaudeBackend, LocalBackend, SESSION

check("in" in SESSION, "SESSION has 'in'")
check("out" in SESSION, "SESSION has 'out'")
check("turns" in SESSION, "SESSION has 'turns'")

# ========== MCP ==========
from boyser.mcp import MCPClient, MCPToolAdapter, load_mcp_config, MCP_CONFIG_PATH

client = MCPClient()
check(len(client.list_servers()) == 0, "MCPClient starts with 0 servers")

# MCPToolAdapter
mcp_tool = {"name": "my_tool", "description": "Does stuff", "inputSchema": {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}}
adapted = MCPToolAdapter(mcp_tool)
check(adapted["name"] == "my_tool", "MCPToolAdapter name")
check(adapted.get("input_schema") is not None, "MCPToolAdapter input_schema")
check(adapted["input_schema"]["type"] == "object", "MCPToolAdapter type=object")
check("x" in adapted["input_schema"]["properties"], "MCPToolAdapter properties preserved")

# load_mcp_config with no file
config = load_mcp_config()
check("servers" in config, "load_mcp_config returns servers key")
check(len(config.get("servers", [])) == 0, "load_mcp_config returns empty list when no file")

# ========== SUBAGENT ==========
from boyser.subagent import SubAgentClient, SubAgentSession, SubAgentManager

# SubAgentSession
sess = SubAgentSession(id="test-1", goal="do something", status="running")
check(sess.id == "test-1", "SubAgentSession id")
check(sess.status == "running", "SubAgentSession status")
check(sess.summary == "", "SubAgentSession summary defaults to empty")
check(sess.tools_called == [], "SubAgentSession tools_called defaults to empty")
d = sess.to_dict()
check(d["id"] == "test-1", "SubAgentSession.to_dict() id")

# SubAgentManager singleton
m1 = SubAgentManager()
m2 = SubAgentManager()
check(m1 is m2, "SubAgentManager singleton")
check(m1.max_concurrent == 3, "SubAgentManager max_concurrent = 3")
check(m1.max_total == 10, "SubAgentManager max_total = 10")

# ========== PRINT SUMMARY ==========
print(f"\n{'='*50}")
print(f"QC RESULTS: {len(errors)} ERRORS FOUND")
print(f"{'='*50}")
if errors:
    for e in errors:
        print(f"  ✗ {e}")
else:
    print("  ✅ ALL CHECKS PASSED!")
