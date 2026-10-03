"""Bootstrap SessionStart hook: print `agentkit status` and the resume point (ADR 0001).

Stands in for the SessionStart wiring of the Claude Code adapter (spec 012); delete it then.
Never fails the session: any error prints nothing for that part.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

try:
    sys.path.insert(0, str(ROOT))
    from agentkit.config import load_config
    from agentkit.status import status_lines
    print("\n".join(status_lines(load_config(root=ROOT))))
except Exception:
    pass

try:
    text = (ROOT / "specs" / "README.md").read_text(encoding="utf-8")
    i = text.find("## Resume point")
    if i >= 0:
        print()
        print(text[i:].strip())
except Exception:
    pass
