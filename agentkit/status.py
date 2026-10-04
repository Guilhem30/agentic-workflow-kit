"""Session status summary (spec 006)."""
from __future__ import annotations

import re

from agentkit import chaos, lock, specs
from agentkit.config import ConfigError

_MAX_LINES = 10
_MAX_CHARS = 200
_BROKEN = " | chaos: BROKEN ("
_CHAOS_ACTIONS = {  # R020-33
    "draft": "run /spec {id}, then chaos approve {id} approved",
    "tests-draft": "chaos approve {id} tests-approved",
    "tests-approved": "chaos approve {id} frozen",
    "frozen": "run /implement {id}, then chaos approve {id} done",
}
_NEXT_RE = re.compile(r"^\*\*Next:\*\*[ \t]*(\S.*?)[ \t]*\r?$", re.M)
_SNAPSHOT = "<!-- agentkit:snapshot:begin -->"


def _cut(line: str) -> str:
    return line if len(line) <= _MAX_CHARS else line[:_MAX_CHARS - 1] + "…"


def _line_one(cfg) -> tuple[str, bool]:
    """R006-02, R006-08, R020-32. Returns the line and whether the lock is violated."""
    profile = cfg.data.get("kit", {}).get("profile") or "generic"
    violated = False
    try:
        st = lock.status(cfg)
        frozen = st["frozen"]
        bad = st["violations"]
        if bad:
            violated = True
            state = f"VIOLATED ({len(bad)} file(s): run `agentkit lock verify`)"
        else:
            state = "OK"
    except (lock.LockError, ConfigError, OSError, ValueError) as exc:
        frozen, state = 0, f"BROKEN ({' '.join(str(exc).split())})"
    line = f"agentkit: profile {profile} | frozen files: {frozen} | lock: {state}"
    suffix = re.sub(r"\s+", " ", chaos.status_suffix(cfg))
    if len(line + suffix) > _MAX_CHARS and suffix.startswith(_BROKEN):
        msg = " ".join(suffix[len(_BROKEN):-1].split())
        room = _MAX_CHARS - len(line) - len(_BROKEN) - 2
        suffix = f"{_BROKEN}{msg[:max(room, 0)]}…)"
    return _cut(line + suffix), violated


def _chaos_settings(cfg):
    if "chaos" not in cfg.data:
        return None
    try:
        return chaos.settings(cfg)
    except (ConfigError, chaos.ChaosError):
        return None


def _paused(cfg, st) -> int:
    if st is None or not st.enabled:
        return 0
    try:
        return len(chaos.open_escalations(cfg))
    except (ConfigError, chaos.ChaosError):
        return 0


def _progress_next(spec) -> str:
    try:
        text = (spec.dir / "progress.md").read_text(encoding="utf-8")
    except OSError:
        return ""
    # The snapshot's Next line wins; otherwise the last one in the file.
    i = text.find(_SNAPSHOT)
    found = _NEXT_RE.findall(text[i:]) if i >= 0 else []
    found = found or _NEXT_RE.findall(text)
    return found[-1] if found else ""


def _action(spec, st, by_id) -> tuple[str, bool]:
    """The next action of an active spec and whether it is blocked (R006-03, R006-13)."""
    if spec.status == "frozen":
        blockers = [d for d in spec.depends
                    if by_id.get(d) is None or by_id[d].status != "done"]
        if blockers:
            return "blocked by " + ", ".join(blockers), True
    if st is not None and st.applies(spec.id) and spec.status in _CHAOS_ACTIONS:
        return _CHAOS_ACTIONS[spec.status].format(id=spec.id), False
    return spec.next_action(), False


def status_lines(cfg) -> list[str]:
    first, violated = _line_one(cfg)
    st = _chaos_settings(cfg)
    all_specs = specs.list_specs(cfg)
    by_id = {s.id: s for s in all_specs}
    ready, blocked = [], []
    for spec in sorted(all_specs, key=lambda s: s.id):
        if spec.status in ("done", specs.DROPPED):
            continue
        action, is_blocked = _action(spec, st, by_id)
        if spec.status == "frozen":
            note = _progress_next(spec)
            if note:
                action += f" (progress: {note})"  # R006-04
        line = f"spec {spec.id} {spec.slug} [{spec.status}] -> {action}"
        (blocked if is_blocked else ready).append((line, action))
    active = ready + blocked

    tail = []
    escalations = _paused(cfg, st)
    if violated:  # R006-06
        tail.append("next: the lock is violated: restore the frozen files (`agentkit lock "
                    "restore`) or ask the owner to unfreeze them, before anything else")
    elif escalations:  # R020-34
        tail.append(f"next: HUMAN reviews {escalations} escalation(s): agentkit chaos log --open")
    elif active:
        tail.append(f"next: {active[0][1]}")

    body = [line for line, _ in active]
    if not active:  # R006-07
        body = (["no active spec: run /spec NNN (create one with `agentkit new-spec slug`)"]
                if all_specs else ["no spec yet: run /kickoff to write the first specs"])
    room = _MAX_LINES - 1 - len(tail)
    if len(body) > room:  # R006-05
        body = body[:room - 1] + [f"... {len(body) - (room - 1)} more active spec(s)"]
    return [first] + [_cut(line) for line in body + tail]
