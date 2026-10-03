"""Bootstrap stand-in for `agentkit sync` (R012-09, R012-10, `kit` model mode). See ADR 0001.

Regenerates .claude/skills/ from .agents/skills/ and .claude/agents/ from roles/.
Usage: python3 scripts/bootstrap_sync.py [--check]
Not part of the kit: delete it once `agentkit sync` exists (spec 010/012).
"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = {"strong": "opus", "standard": "sonnet", "fast": "haiku"}
EFFORT = {"strong": "high", "standard": "medium", "fast": "low"}
TOOLS = {"read": ["Read", "Grep", "Glob"], "edit": ["Edit", "Write"], "shell": ["Bash", "PowerShell"]}

def split(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return m.group(1), text[m.end():]

def parse(fm):
    top, meta = {}, {}
    for line in fm.splitlines():
        if line.startswith("  "):
            k, v = line.strip().split(":", 1); meta[k] = v.strip().strip('"')
        else:
            k, v = line.split(":", 1); v = v.strip()
            if k == "metadata": continue
            top[k] = v
    return top, meta

check = "--check" in sys.argv
out = {}
for skill in sorted((ROOT / ".agents/skills").iterdir()):
    src = skill / "SKILL.md"
    fm, body = split(src.read_text())
    top, meta = parse(fm)
    lines = [f"name: {top['name']}", f"description: {top['description']}"]
    for k in ("license", "compatibility", "allowed-tools"):
        if k in top: lines.append(f"{k}: {top[k]}")
    if meta.get("agentkit-user-only") == "true": lines.append("disable-model-invocation: true")
    if "agentkit-args" in meta: lines.append(f'argument-hint: "{meta["agentkit-args"]}"')
    tier = meta.get("agentkit-tier")
    if tier: lines += [f"model: {MODEL[tier]}", f"effort: {meta.get('agentkit-effort', EFFORT[tier])}"]
    comment = f"<!-- generated from .agents/skills/{skill.name}/SKILL.md by the bootstrap sync (ADR 0001); edit the source -->\n"
    out[ROOT / ".claude/skills" / skill.name / "SKILL.md"] = "---\n" + "\n".join(lines) + "\n---\n" + comment + body
for role in sorted((ROOT / "roles").glob("*.md")):
    fm, body = split(role.read_text())
    top, _ = parse(fm)
    tools = [t for key in re.findall(r"\w+", top["tools"]) for t in TOOLS[key]]
    lines = [f"name: {top['name']}", f"description: {top['description']}", f"tools: {', '.join(tools)}",
             f"model: {MODEL[top['tier']]}", f"effort: {top['effort']}"]
    comment = f"<!-- generated from roles/{role.name} by the bootstrap sync (ADR 0001); edit the source -->\n"
    out[ROOT / ".claude/agents" / role.name] = "---\n" + "\n".join(lines) + "\n---\n" + comment + body
drift = 0
for path, text in out.items():
    if check:
        if not path.exists() or path.read_text() != text: print("drift:", path.relative_to(ROOT)); drift = 1
    else:
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, newline="\n")
print("ok" if not drift else "DRIFT"); sys.exit(drift)
