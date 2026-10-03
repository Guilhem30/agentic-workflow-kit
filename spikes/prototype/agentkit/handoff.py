"""`agentkit handoff NNN`: refresh the auto snapshot in `specs/NNN-*/progress.md` so a new
session can resume from files instead of from conversation history."""

from __future__ import annotations

import datetime as _dt
import re

from .config import Config
from .specs import find_spec
from .util import git, is_git_repo, write_text_lf

BEGIN = "<!-- agentkit:snapshot:begin -->"
END = "<!-- agentkit:snapshot:end -->"


def _tasks(spec_dir) -> tuple[int, int, str]:
    p = spec_dir / "tasks.md"
    if not p.is_file():
        return 0, 0, ""
    done = total = 0
    first_open = ""
    for line in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*- \[([ xX])\]\s*(.*)", line)
        if not m:
            continue
        total += 1
        if m.group(1) != " ":
            done += 1
        elif not first_open:
            first_open = m.group(2).strip()
    return done, total, first_open


def snapshot(cfg: Config, spec_id: str, note: str = "", next_step: str = "", now=None) -> str:
    spec = find_spec(cfg, spec_id)
    if not spec:
        raise ValueError(f"spec {spec_id} not found")
    done, total, first_open = _tasks(spec.dir)
    stamp = (now or _dt.datetime.now(_dt.timezone.utc)).strftime("%Y-%m-%d %H:%M UTC")
    lines = [BEGIN, f"_Snapshot {stamp}, phase `{spec.status}`._", ""]
    lines.append(f"- Tasks: {done}/{total} done" + (f"; next open: {first_open}" if first_open else ""))
    last = cfg.state_dir / "last-test.txt"
    if last.is_file():
        summary = last.read_text(encoding="utf-8").strip().splitlines()
        lines.append("- Last `agentkit test`: " + (summary[0] if summary else "n/a"))
        for extra in summary[1:9]:
            lines.append("  " + extra)
    if is_git_repo(cfg.root):
        branch = git(cfg.root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        dirty = [l for l in git(cfg.root, "status", "--porcelain").stdout.splitlines() if l.strip()]
        lines.append(f"- Git: branch `{branch}`, {len(dirty)} uncommitted change(s)")
    if note:
        lines.append(f"- Note: {note}")
    lines.append("")
    lines.append(f"**Next:** {next_step or first_open or spec.next_action()}")
    lines.append(END)
    block = "\n".join(lines)

    p = spec.dir / "progress.md"
    text = p.read_text(encoding="utf-8") if p.is_file() else f"# Progress: spec {spec.id}\n"
    if BEGIN in text and END in text:
        pre, rest = text.split(BEGIN, 1)
        _, post = rest.split(END, 1)
        text = pre + block + post
    else:
        text = text.rstrip("\n") + "\n\n" + block + "\n"
    write_text_lf(p, text)
    return block
