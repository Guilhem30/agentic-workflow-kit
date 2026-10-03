"""Bootstrap SessionStart hook: print the resume point of specs/README.md (ADR 0001).

Stands in for `agentkit status` (spec 006) wired by the Claude Code adapter (spec 012); delete it
then. Never fails the session: any error prints nothing.
"""
from pathlib import Path

try:
    text = (Path(__file__).resolve().parent.parent / "specs" / "README.md").read_text(encoding="utf-8")
    i = text.find("## Resume point")
    if i >= 0:
        print(text[i:].strip())
except Exception:
    pass
