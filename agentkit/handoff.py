"""Handoff: the resume snapshot in progress.md (spec 006)."""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone

from agentkit import _git, specs

_BEGIN = "<!-- agentkit:snapshot:begin -->"
_END = "<!-- agentkit:snapshot:end -->"
_TASK_RE = re.compile(r"^\s*[-*] \[([ xX])\]\s*(.*?)\s*$")
_SUMMARY_LINES = 9


def _tasks(spec) -> tuple[int, int, str]:
    try:
        text = (spec.dir / "tasks.md").read_text(encoding="utf-8")
    except OSError:
        return 0, 0, ""
    done = total = 0
    first_open = ""
    for line in text.split("\n"):
        m = _TASK_RE.match(line)
        if not m:
            continue
        total += 1
        if m.group(1) != " ":
            done += 1
        elif not first_open:
            first_open = m.group(2)
    return done, total, first_open


def _last_test(cfg) -> list[str]:
    try:
        text = (cfg.state_dir / "last-test.txt").read_text(encoding="utf-8")
    except OSError:
        return []
    return [l for l in text.split("\n") if l.strip()][:_SUMMARY_LINES]


def _git_line(cfg) -> str:
    if not _git.is_repo(cfg.root):
        return ""
    proc = _git.run(cfg.root, "symbolic-ref", "--short", "-q", "HEAD")
    branch = proc.stdout.decode("utf-8", "replace").strip() if proc.returncode == 0 else ""
    if not branch:
        proc = _git.run(cfg.root, "rev-parse", "--short", "HEAD")
        branch = "detached " + proc.stdout.decode("utf-8", "replace").strip()
    proc = _git.run(cfg.root, "status", "--porcelain")
    changes = len([l for l in proc.stdout.split(b"\n") if l.strip()]) if proc.returncode == 0 else 0
    return f"- Branch `{branch}`, {changes} uncommitted change(s)"


def _phase_action(cfg, spec) -> str:
    from agentkit import status
    st = status._chaos_settings(cfg)
    by_id = {s.id: s for s in specs.list_specs(cfg)}
    return status._action(spec, st, by_id)[0] or "none"


def snapshot(cfg, spec_id, note="", next_step="", now=None) -> str:
    spec = specs.find_spec(cfg, spec_id)
    if spec is None:
        raise LookupError(f"spec {spec_id} not found")
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    done, total, first_open = _tasks(spec)
    lines = [_BEGIN, f"- {now.strftime('%Y-%m-%d %H:%M')} (UTC), phase `{spec.status}`"]
    tasks = f"- Tasks: {done}/{total} done"
    lines.append(tasks + (f"; first open: {first_open}" if first_open else ""))
    summary = _last_test(cfg)
    if summary:
        lines.append("- Last `agentkit test`:")
        lines += [f"  {l}" for l in summary]
    git_line = _git_line(cfg)
    if git_line:
        lines.append(git_line)
    note, next_step = " ".join(note.split()), " ".join(next_step.split())
    if note:
        lines.append(f"- Note: {note}")
    nxt = next_step or first_open or _phase_action(cfg, spec)
    lines += ["", f"**Next:** {nxt}", _END]
    return "\n".join(lines) + "\n"


def _cli(cfg, args) -> int:
    try:
        block = snapshot(cfg, args.id, note=args.note, next_step=args.next_step)
    except LookupError as exc:
        print(f"agentkit: {exc}", file=sys.stderr)
        return 1  # R006-12
    spec = specs.find_spec(cfg, args.id)
    path = spec.dir / "progress.md"
    text = path.read_bytes().decode("utf-8") if path.exists() else ""
    if "\r\n" in text:  # keep the file's line endings (R006-09: the rest stays unchanged)
        block = block.replace("\n", "\r\n")
    start = text.find(_BEGIN)
    end = text.find(_END, start) if start >= 0 else -1
    if start < 0 or end < 0:  # drop orphan markers, then append
        text = "".join(l for l in text.splitlines(keepends=True)
                       if l.strip() not in (_BEGIN, _END))
        start = -1
    if start >= 0:
        stop = end + len(_END)
        for nl in ("\r\n", "\n"):
            if text.startswith(nl, stop):
                stop += len(nl)
                break
        text = text[:start] + block + text[stop:]
    else:
        nl = "\r\n" if "\r\n" in text else "\n"
        if text and not text.endswith("\n"):
            text += nl
        text += (nl if text else "") + block
    path.write_bytes(text.encode("utf-8"))
    print(f"spec {spec.id}: snapshot written to {path.relative_to(cfg.root).as_posix()}")
    return 0
