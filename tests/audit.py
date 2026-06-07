"""Structural audit: import conflicts, duplicate definitions, variable flow"""
import ast, sys

print("=== AUDIT: agent.py import conflicts ===")
with open("/root/boyser-ai-fork/boyser/agent.py") as f:
    agent = ast.parse(f.read())

consoles = []
for node in ast.walk(agent):
    if isinstance(node, ast.ImportFrom) and node.module == "boyser.repl":
        for alias in node.names:
            if alias.name == "console":
                consoles.append(f"  imported at line {node.lineno}")
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "console":
                consoles.append(f"  LOCAL assigned at line {node.lineno}")
    if isinstance(node, ast.Global):
        for name in node.names:
            print(f"  'global {name}' at line {node.lineno}")

for c in consoles:
    print(c)

print()
print("=== AUDIT: THINK_ON/VOTE_ON/SYSTEM reassignment ===")
imports_config = {}
for node in ast.walk(agent):
    if isinstance(node, ast.ImportFrom) and node.module == "boyser.config":
        for alias in node.names:
            imports_config[alias.name] = node.lineno

for v in ("THINK_ON", "VOTE_ON", "SYSTEM"):
    if v in imports_config:
        print(f"  {v} imported from config at line {imports_config[v]}")
    # Find assignments
    for node in ast.walk(agent):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == v:
                    print(f"  {v} REASSIGNED at line {node.lineno}")
    if v in [n for node in ast.walk(agent) if isinstance(node, ast.Global) for n in node.names]:
        print(f"  {v} in 'global' statement")

print()
print("=== AUDIT: backend.py uses which THINK_ON? ===")
with open("/root/boyser-ai-fork/boyser/backend.py") as f:
    backend = ast.parse(f.read())

for node in ast.walk(backend):
    if isinstance(node, ast.ImportFrom) and "boyser.config" in (node.module or ""):
        for alias in node.names:
            if alias.name in ("THINK_ON", "VOTE_ON", "SYSTEM"):
                print(f"  backend imports {alias.name} from config at line {node.lineno}")
    if isinstance(node, ast.Name) and node.id in ("THINK_ON", "VOTE_ON"):
        # Check if it's used (not just imported)
        pass

# Check usage
for node in ast.walk(backend):
    if isinstance(node, ast.Name) and node.id == "THINK_ON":
        print(f"  backend USES THINK_ON at line {node.lineno}")
    if isinstance(node, ast.Name) and node.id == "VOTE_ON":
        print(f"  backend USES VOTE_ON at line {node.lineno}")

print()
print("=== AUDIT: duplicate function names ===")
with open("/root/boyser-ai-fork/boyser/tools.py") as f:
    tools_funcs = {n.name for n in ast.walk(ast.parse(f.read())) if isinstance(n, ast.FunctionDef)}
with open("/root/boyser-ai-fork/boyser/agent.py") as f:
    agent_funcs = {n.name for n in ast.walk(ast.parse(f.read())) if isinstance(n, ast.FunctionDef)}

dups = tools_funcs & agent_funcs
if dups:
    print(f"  DUPLICATE: {dups}")
else:
    print("  No duplicates")

print()
print("=== AUDIT: TOOL_FUNCS vs TOOLS name consistency ===")
# Check if every TOOL_FUNCS name has a corresponding TOOLS entry
sys.path.insert(0, "/root/boyser-ai-fork")
from boyser.config import TOOLS as config_tools
from boyser.tools import TOOL_FUNCS

config_names = {t["name"] for t in config_tools}
func_names = set(TOOL_FUNCS.keys())
if config_names != func_names:
    print(f"  MISMATCH: config only: {config_names - func_names}, funcs only: {func_names - config_names}")
else:
    print(f"  ✓ All {len(config_names)} names match")

print()
print("=== DONE ===")
