"""`agentkit status`: at most 10 lines describing where the work stands (used at session start)."""

from __future__ import annotations

import re

from .config import Config
from .lock import LockError, load_lock, verify
from .specs import list_specs

MAX_LINES = 10


def _progress_next(spec) -> str:
    p = spec.dir / "progress.md"
    if not p.is_file():
        return ""
    m = re.search(r"^\*\*Next:\*\*\s*(.+)$", p.read_text(encoding="utf-8"), re.MULTILINE)
    return m.group(1).strip() if m else ""


def status_lines(cfg: Config) -> list[str]:
    lines = []
    try:
        frozen = len(load_lock(cfg)["files"])
        violations = verify(cfg)
        lock_state = "OK" if not violations else f"VIOLATED ({len(violations)} file(s): run `agentkit lock verify`)"
    except LockError as e:
        frozen, violations, lock_state = 0, [], f"BROKEN ({e})"
    lines.append(f"agentkit: profile {cfg.profile.get('name')} | frozen files: {frozen} | lock: {lock_state}")
    active = [s for s in list_specs(cfg) if s.status != "done"]
    if not active:
        lines.append("no active spec: start one with /spec (agentkit new-spec NNN slug)")
    for s in active[: MAX_LINES - 3]:
        nxt = _progress_next(s)
        line = f"spec {s.id} {s.slug} [{s.status}] -> {s.next_action()}"
        if nxt and s.status == "frozen":
            line += f" (progress: {nxt})"
        lines.append(line[:200])
    if len(active) > MAX_LINES - 3:
        lines.append(f"... {len(active) - (MAX_LINES - 3)} more active spec(s)")
    if violations:
        lines.append("FIRST: restore frozen files (`agentkit lock restore`) or ask the human to unfreeze.")
    elif active:
        lines.append("next: " + active[0].next_action())
    return lines[:MAX_LINES]
