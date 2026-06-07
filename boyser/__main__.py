"""Allow `python3 -m boyser` to run the agent."""
import sys

# Handle --version before importing the full agent (fast path)
if "--version" in sys.argv or "-V" in sys.argv:
    from boyser import __version__, __version_hash__, __version_date__
    if __version__:
        print(f"BOYSER AI {__version__} ({__version_hash__} · {__version_date__})")
    else:
        print("BOYSER AI (no git repo — version unknown)")
    sys.exit(0)

from boyser.agent import main

main()
