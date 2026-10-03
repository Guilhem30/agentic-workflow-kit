"""Chaos mode: agent-approved gates (spec 020).

Call 002's functions through the module (`lock.freeze`, `lock.open_console`, as the contract
writes them), not with `from agentkit.lock import ...`: the tests patch those attributes.
"""
from __future__ import annotations

import json
import posixpath
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from agentkit import _git, lock, specs
from agentkit.config import ConfigError
from agentkit.util import glob_match


class ChaosError(Exception):
    """A chaos refusal. The CLI exits 1."""


class ChaosUsageError(ChaosError):
    """A chaos usage problem. The CLI exits 2."""


GATES = ("approved", "tests-approved", "frozen", "done")
REVIEWS: dict[str, list[tuple[str, str, str]]] = {
    "approved": [("spec-reviewer", "verdict: ready for owner approval", "verdict: needs changes")],
    "tests-approved": [("test-auditor", "verdict: ready to freeze", "verdict: needs changes")],
    "done": [("impl-reviewer", "verdict: approve", "verdict: needs changes")],
    "unfreeze": [("test-auditor", "verdict: unfreeze justified", "verdict: keep frozen"),
                 ("impl-reviewer", "verdict: unfreeze justified", "verdict: keep frozen")],
}
NEEDS_OWNER = "verdict: needs owner"
CAUSES = ("rejections", "verify", "audit", "protected", "base", "owner")
DEFAULT_LOG = "chaos-log.jsonl"

DEFAULT_ESCALATE_GLOBS = ["{specs}/000-*/**", "AGENTS.md", "CLAUDE.md", "docs/adr/**",
                          "agentkit.toml", "{roles}/**"]
REQUIRED_PHASE = {"approved": "draft", "tests-approved": "tests-draft",
                  "frozen": "tests-approved", "done": "frozen"}
HINT = "owner: agentkit chaos log --open"
_SPEC_RE = re.compile(r"^\d{3}$")
_COMMON = ("seq", "time", "kind", "commit", "user", "actor")
_KIND_FIELDS = {
    "approve": ("spec", "gate", "reviews"),
    "reject": ("spec", "gate", "reviews"),
    "escalate": ("spec", "gate", "cause", "detail"),
    "unfreeze": ("spec", "gate", "files", "reason", "reviews"),
    "clear": ("escalations", "note"),
}


@dataclass
class Settings:
    enabled: bool
    specs: list[str]
    max_rejections: int
    log_rel: str
    escalate_globs: list[str]
    log_path: Path

    def applies(self, spec_id: str) -> bool:
        """R020 Conventions: enabled, not spec 000, and listed (or no list)."""
        return (self.enabled and spec_id != "000"
                and (not self.specs or spec_id in self.specs))


# settings ------------------------------------------------------------------------------

def _placeholders(cfg, globs: list[str]) -> list[str]:
    return [g.replace("{specs}", cfg.path("specs")).replace("{roles}", cfg.path("roles"))
            for g in globs]


def _check_log_rel(value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError("chaos.log: must be a non-empty relative path")
    text = value.replace("\\", "/")
    if text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        raise ConfigError(f"chaos.log: must be relative to the repository root, got {value!r}")
    norm = posixpath.normpath(text)
    if norm == ".." or norm.startswith("../") or norm == ".":
        raise ConfigError(f"chaos.log: must stay inside the repository root, got {value!r}")
    return norm


def settings(cfg) -> Settings:
    """The `[chaos]` table (R020-01); ConfigError names the dotted key (R020-02, R020-03)."""
    table = cfg.data.get("chaos", {})
    if not isinstance(table, dict):
        raise ConfigError("chaos: must be a table")
    enabled = table.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ConfigError("chaos.enabled: must be true or false")
    chosen = table.get("specs", [])
    if not isinstance(chosen, list) or not all(isinstance(s, str) and _SPEC_RE.match(s)
                                               for s in chosen):
        raise ConfigError('chaos.specs: must be a list of three-digit spec numbers ("012")')
    if "000" in chosen:
        raise ConfigError("chaos.specs: spec 000 (vision and constitution) is never under "
                          "chaos mode")
    max_rej = table.get("max_rejections", 2)
    if isinstance(max_rej, bool) or not isinstance(max_rej, int) or max_rej < 1:
        raise ConfigError("chaos.max_rejections: must be an integer of at least 1")
    log_rel = _check_log_rel(table.get("log", DEFAULT_LOG))
    globs = table.get("escalate_globs", DEFAULT_ESCALATE_GLOBS)
    if not isinstance(globs, list) or not all(isinstance(g, str) for g in globs):
        raise ConfigError("chaos.escalate_globs: must be a list of globs")
    return Settings(enabled=enabled, specs=list(chosen), max_rejections=max_rej,
                    log_rel=log_rel, escalate_globs=_placeholders(cfg, globs),
                    log_path=cfg.root / log_rel)


def _log_rel_lenient(cfg) -> str:
    """The configured log path, or the default one when `[chaos]` is malformed (R020-42)."""
    try:
        return settings(cfg).log_rel
    except ConfigError:
        return DEFAULT_LOG


# the log -------------------------------------------------------------------------------

def _dumps(record: dict) -> str:
    return json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _parse_log(data: bytes, rel: str) -> list[dict]:
    """R020-37: every line a valid record whose seq is its line number."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ChaosError(f"{rel}: not valid UTF-8") from None
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    records = []
    for no, line in enumerate(lines, start=1):
        where = f"{rel}: line {no}"
        try:
            rec = json.loads(line.rstrip("\r"))
        except ValueError as exc:
            raise ChaosError(f"{where}: not JSON ({exc.msg})") from None
        if not isinstance(rec, dict):
            raise ChaosError(f"{where}: not a JSON object")
        missing = [k for k in _COMMON if k not in rec]
        if missing:
            raise ChaosError(f"{where}: lacks {', '.join(missing)}")
        kind = rec["kind"]
        if kind not in _KIND_FIELDS:
            raise ChaosError(f"{where}: unknown kind {kind!r}")
        need = list(_KIND_FIELDS[kind])
        if kind == "approve" and rec.get("gate") == "frozen":
            need += ["files", "based_on"]
        missing = [k for k in need if k not in rec]
        if missing:
            raise ChaosError(f"{where}: a {kind} record lacks {', '.join(missing)}")
        if isinstance(rec["seq"], bool) or rec["seq"] != no:
            raise ChaosError(f"{where}: seq is {rec['seq']!r}, expected {no}")
        records.append(rec)
    return records


def read_log(cfg) -> list[dict]:
    """All records (R020-37). A missing log reads as no records."""
    rel = _log_rel_lenient(cfg)
    path = cfg.root / rel
    if not path.is_file():
        return []
    return _parse_log(path.read_bytes(), rel)


def _cleared(records: list[dict]) -> set:
    out: set = set()
    for rec in records:
        if rec["kind"] == "clear":
            out.update(rec["escalations"])
    return out


def _open_in(records: list[dict]) -> list[dict]:
    cleared = _cleared(records)
    return [r for r in records if r["kind"] == "escalate" and r["seq"] not in cleared]


def open_escalations(cfg) -> list[dict]:
    """Escalations that no `clear` record lists (R020-11)."""
    return _open_in(read_log(cfg))


class _Log:
    """The records read once per command, and appends that keep seq = line number."""

    def __init__(self, cfg, records: list[dict], user=None, now=None):
        self.cfg = cfg
        self.records = records
        self.rel = _log_rel_lenient(cfg)
        self.user = user or _git.user_name(cfg.root)
        self.time = lock._now_text(now)

    @property
    def next_seq(self) -> int:
        return len(self.records) + 1

    def append(self, kind: str, **fields) -> dict:
        rec = {"seq": self.next_seq, "time": self.time, "kind": kind,
               "commit": _git.resolve_commit(self.cfg.root, "HEAD") or "",
               "user": self.user, "actor": "agent" if lock.human_check() else "human"}
        rec.update(fields)
        path = self.cfg.root / self.rel
        path.parent.mkdir(parents=True, exist_ok=True)
        old = path.read_bytes() if path.exists() else b""
        sep = b"" if not old or old.endswith(b"\n") else b"\n"
        with open(path, "ab") as f:
            f.write(sep + (_dumps(rec) + "\n").encode("utf-8"))
        self.records.append(rec)
        return rec


# reviews -------------------------------------------------------------------------------

def _normalise(line: str) -> str:
    return " ".join(line.strip().strip("`* \t").split()).lower()


def parse_verdict(text: str, gate: str, role: str) -> str:
    """R020-13: the last non-empty line, normalised: "pass", "fail" or "owner"."""
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise ChaosUsageError(f"the {role} review has no verdict line (it is empty)")
    found = lines[-1].strip()
    verdict = _normalise(found)
    for name, passing, failing in REVIEWS.get(gate, []):
        if name != role:
            continue
        if verdict == passing:
            return "pass"
        if verdict == failing:
            return "fail"
        if verdict == NEEDS_OWNER:
            return "owner"
        raise ChaosUsageError(
            f"the {role} review must end with {passing!r}, {failing!r} or {NEEDS_OWNER!r}; "
            f"its last line is {found!r}")
    raise ChaosUsageError(f"no {role} review is defined for {gate}")


@dataclass
class _Review:
    role: str
    data: bytes
    verdict: str   # pass | fail | owner
    line: str      # the normalised verdict line

    def store(self, cfg, spec, seq: int, gate: str) -> dict:
        """R020-14: copy byte for byte and cite it with its hash."""
        target = spec.dir / "reviews" / f"{seq}-{gate}-{self.role}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.data)
        rel = target.relative_to(cfg.root).as_posix()
        return {"role": self.role, "verdict": self.line, "review": rel,
                "review_sha256": lock.sha256_lf(self.data)}


def _read_review(path, gate: str, role: str) -> _Review:
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise ChaosUsageError(f"cannot read the {role} review {path}: "
                              f"{exc.strerror or exc}") from None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ChaosUsageError(f"the {role} review {path} is not UTF-8") from None
    verdict = parse_verdict(text, gate, role)
    line = _normalise([x for x in text.splitlines() if x.strip()][-1])
    return _Review(role, data, verdict, line)


# shared checks -------------------------------------------------------------------------

def _require_git(cfg) -> None:
    if not _git.is_repo(cfg.root):
        raise ChaosUsageError("chaos mode needs a git repository")


def _base_commit(cfg, records: list[dict]) -> str:
    """The newest record's commit, else the newest commit that changed agentkit.toml."""
    if records:
        return records[-1]["commit"]
    proc = _git.run(cfg.root, "log", "-1", "--format=%H", "--", "agentkit.toml")
    commit = proc.stdout.decode("ascii", "replace").strip() if proc.returncode == 0 else ""
    if not commit:
        raise ChaosUsageError("no base commit: commit agentkit.toml first "
                              "(git add agentkit.toml && git commit)")
    return commit


def _check_paused(records: list[dict]) -> None:
    opened = _open_in(records)
    if opened:
        lines = format_log(opened)
        raise ChaosError("chaos mode is paused by open escalation(s):\n"
                         + "\n".join(f"  {line}" for line in lines)
                         + "\nhint: ask the owner to review them (agentkit chaos log --open)"
                           " and clear them")


def _changed_since(cfg, base: str) -> list[str]:
    out: set = set()
    proc = _git.run(cfg.root, "diff", "--name-only", "--no-renames", "--relative", "-z", base)
    if proc.returncode == 0:
        out.update(p.decode("utf-8", "surrogateescape") for p in proc.stdout.split(b"\0") if p)
    proc = _git.run(cfg.root, "ls-files", "--others", "--exclude-standard", "-z")
    if proc.returncode == 0:
        out.update(p.decode("utf-8", "surrogateescape") for p in proc.stdout.split(b"\0") if p)
    return sorted(out)


def _critical(cfg, st: Settings, base: str) -> tuple[str, list[str]] | None:
    """R020-19: the first failing critical check as (cause, detail)."""
    root = cfg.root
    commit = _git.resolve_commit(root, base)
    if commit is None or _git.run(root, "merge-base", "--is-ancestor", commit,
                                  "HEAD").returncode != 0:
        return "base", [base]
    violations = lock.verify(cfg)
    if violations:
        return "verify", [f"{v.kind} {v.path}" for v in violations]
    problems = lock.audit(cfg, base=commit)
    if problems:
        return "audit", problems
    hits = [p for p in _changed_since(cfg, commit) if glob_match(p, st.escalate_globs)]
    if hits:
        return "protected", hits
    return None


def _escalate(log: _Log, spec_id: str, gate: str, cause: str, detail: list[str]) -> dict:
    return log.append("escalate", spec=spec_id, gate=gate, cause=cause, detail=detail)


def _maybe_escalate_rejections(log: _Log, st: Settings, spec_id: str, gate: str) -> dict | None:
    """R020-21: too many rejects of one spec and gate since the last reset."""
    reset = 0
    for rec in log.records:
        if rec["kind"] == "clear" or (rec["kind"] in ("approve", "unfreeze")
                                      and rec.get("spec") == spec_id and rec.get("gate") == gate):
            reset = rec["seq"]
    rejects = [r["seq"] for r in log.records if r["kind"] == "reject" and r["seq"] > reset
               and r.get("spec") == spec_id and r.get("gate") == gate]
    if len(rejects) >= st.max_rejections:
        return _escalate(log, spec_id, gate, "rejections", [f"#{s}" for s in rejects])
    return None


def _settle(cfg, st, log, spec, gate, reviews: list[_Review]):
    """R020-43, R020-20, R020-21: an escalation or a reject, or None when all pass."""
    seq = log.next_seq
    if any(r.verdict != "pass" for r in reviews):
        cited = [r.store(cfg, spec, seq, gate) for r in reviews]
        owners = [c for r, c in zip(reviews, cited) if r.verdict == "owner"]
        if owners:
            return _escalate(log, spec.id, gate, "owner",
                             [f"{c['role']} {c['review']}" for c in owners])
        log.append("reject", spec=spec.id, gate=gate, reviews=cited)
        return _maybe_escalate_rejections(log, st, spec.id, gate) or log.records[-1]
    return None


# commands ------------------------------------------------------------------------------

def _start(cfg) -> Settings:
    st = settings(cfg)
    if not st.enabled:
        raise ChaosUsageError("chaos mode is off: the owner approves gates "
                              "(agentkit spec-status, agentkit lock freeze)")
    return st


def approve(cfg, spec_id, gate, review=None, user=None, now=None) -> dict:
    """R020-15 to R020-22, in the order of R020-38. Returns the last record appended."""
    st = _start(cfg)
    if gate not in GATES:
        raise ChaosUsageError(f"unknown gate {gate!r}; gates: {', '.join(GATES)}")
    if gate == "frozen" and review:
        raise ChaosUsageError("frozen takes no --review: the test-auditor's verdict on "
                              "tests-approved is the freeze verdict")
    if gate != "frozen" and not review:
        raise ChaosUsageError(f"{gate} needs --review FILE")
    _require_git(cfg)
    records = read_log(cfg)
    base = _base_commit(cfg, records)
    spec = specs.find_spec(cfg, spec_id)
    if spec is None:
        raise ChaosError(f"spec {spec_id} does not exist")
    if not st.applies(spec.id):
        raise ChaosError(f"spec {spec_id} is not under chaos mode; the owner approves its gates")
    if spec.status != REQUIRED_PHASE[gate]:
        raise ChaosError(f"spec {spec_id} ({spec.dir.name}) is in phase {spec.status}; "
                         f"{gate} needs phase {REQUIRED_PHASE[gate]}")
    reviews = [] if gate == "frozen" else [_read_review(review, gate, REVIEWS[gate][0][0])]
    _check_paused(records)
    if gate == "tests-approved":
        from agentkit import trace
        code, lines = trace._trace_command(cfg, spec.id)
        if code != 0:
            raise ChaosError(f"trace --spec {spec.id} fails:\n" + "\n".join(lines))
    log = _Log(cfg, records, user=user, now=now)
    critical = _critical(cfg, st, base)
    if critical:
        return _escalate(log, spec.id, gate, *critical)
    settled = _settle(cfg, st, log, spec, gate, reviews)
    if settled is not None:
        return settled
    if gate == "frozen":
        result = lock.freeze(cfg, spec=spec.id)
        if result.errors:
            raise ChaosError("lock freeze refused; nothing changed:\n"
                             + "\n".join(f"  {e}" for e in result.errors))
        based_on = None
        for rec in records:
            if (rec["kind"] == "approve" and rec.get("spec") == spec.id
                    and rec.get("gate") == "tests-approved"):
                based_on = rec["seq"]
        return log.append("approve", spec=spec.id, gate="frozen", reviews=[],
                          files=sorted(result.added), based_on=based_on)
    seq = log.next_seq
    cited = [r.store(cfg, spec, seq, gate) for r in reviews]
    specs.set_status(spec, gate)
    return log.append("approve", spec=spec.id, gate=gate, reviews=cited)


def unfreeze(cfg, paths, reason, auditor_review, impl_review, user=None, now=None) -> dict:
    """R020-23 to R020-25, R020-39, in the order of R020-38."""
    st = _start(cfg)
    text = (reason or "").strip()
    if len(text) < 5:
        raise ChaosUsageError("a reason of at least 5 characters is required (--reason)")
    if not auditor_review or not impl_review:
        raise ChaosUsageError("both --auditor-review and --impl-review are required")
    if not paths:
        raise ChaosUsageError("give the frozen paths to unfreeze")
    _require_git(cfg)
    records = read_log(cfg)
    base = _base_commit(cfg, records)
    files = dict(lock.load_lock(cfg)["files"])
    chosen, bad = lock._expand_frozen(cfg, files, paths)
    hint = "; ask the owner (agentkit lock unfreeze, in their own terminal)"
    if bad:
        raise ChaosError("cannot unfreeze: " + "; ".join(bad) + hint)
    owners = {p: files[p].get("spec") for p in chosen}
    no_spec = sorted(p for p, s in owners.items() if not s)
    if no_spec:
        raise ChaosError("frozen without a spec: " + ", ".join(no_spec) + hint)
    if len(set(owners.values())) > 1:
        listed = ", ".join(f"{p} ({s})" for p, s in sorted(owners.items()))
        raise ChaosError(f"the paths belong to different specs: {listed}" + hint)
    spec_id = next(iter(owners.values()))
    spec = specs.find_spec(cfg, spec_id)
    if spec is None:
        raise ChaosError(f"spec {spec_id} does not exist" + hint)
    if not st.applies(spec.id):
        raise ChaosError(f"spec {spec_id} is not under chaos mode" + hint)
    if spec.status not in ("frozen", "done"):
        raise ChaosError(f"spec {spec_id} is in phase {spec.status}; an agent unfreeze needs "
                         "frozen or done")
    roles = REVIEWS["unfreeze"]
    reviews = [_read_review(auditor_review, "unfreeze", roles[0][0]),
               _read_review(impl_review, "unfreeze", roles[1][0])]
    _check_paused(records)
    log = _Log(cfg, records, user=user, now=now)
    critical = _critical(cfg, st, base)
    if critical:
        return _escalate(log, spec.id, "unfreeze", *critical)
    settled = _settle(cfg, st, log, spec, "unfreeze", reviews)
    if settled is not None:
        return settled
    seq = log.next_seq
    cited = [r.store(cfg, spec, seq, "unfreeze") for r in reviews]
    for rel in chosen:
        del files[rel]
    lock._write_lock(cfg, files)
    specs.set_status(spec, "tests-draft")
    lock._append_log(cfg, [f"## {log.time} - chaos agent ({log.user})", f"reason: {text}"]
                     + [f"review: {c['review']} sha256 {c['review_sha256']} (chaos log #{seq})"
                        for c in cited]
                     + [f"- {p}" for p in chosen])
    return log.append("unfreeze", spec=spec.id, gate="unfreeze", files=list(chosen),
                      reason=text, reviews=cited)


def clear(cfg, seqs=None, note="", all_open=False, confirm=None, user=None, now=None) -> dict:
    """R020-26, R020-40: the owner clears escalations after a console confirmation."""
    refused = lock.human_check()
    if refused:
        raise lock.OwnerCheckError(refused)
    _require_git(cfg)
    if bool(seqs) == bool(all_open):
        raise ChaosUsageError("give the escalation numbers or --all, not both")
    text = (note or "").strip()
    if len(text) < 5:
        raise ChaosUsageError("a note of at least 5 characters is required (--note)")
    records = read_log(cfg)
    opened = {r["seq"]: r for r in _open_in(records)}
    if all_open:
        targets = sorted(opened)
        if not targets:
            raise ChaosError("no open escalation to clear")
    else:
        wanted = []
        for s in seqs:
            try:
                wanted.append(int(str(s).lstrip("#")))
            except ValueError:
                raise ChaosUsageError(f"not an escalation number: {s!r}") from None
        not_open = sorted({s for s in wanted if s not in opened})
        if not_open:
            raise ChaosError("not open escalation(s): " + ", ".join(f"#{s}" for s in not_open))
        targets = sorted(set(wanted))
    expected = f"clear {len(targets)}"
    prompt = ("Clear these escalations:\n"
              + "".join(f"  {line}\n" for line in format_log([opened[s] for s in targets]))
              + f"note: {text}")
    ask = confirm or lock._confirm_on_console
    try:
        ok = ask(prompt, expected)
    except lock.LockError as exc:
        raise ChaosError(str(exc)) from None
    if not ok:
        raise ChaosError(f"confirmation did not match {expected!r}; nothing changed")
    return _Log(cfg, records, user=user, now=now).append("clear", escalations=targets, note=text)


# reporting -----------------------------------------------------------------------------

def _info(rec: dict) -> str:
    kind = rec["kind"]
    if kind == "approve" and rec.get("gate") == "frozen":
        return f"files={len(rec.get('files') or [])}"
    if kind in ("approve", "reject", "unfreeze"):
        return " + ".join(r.get("verdict", "?") for r in rec.get("reviews") or [])
    if kind == "escalate":
        return str(rec.get("cause"))
    return ",".join(f"#{s}" for s in rec.get("escalations") or []) + f": {rec.get('note', '')}"


def _line(rec: dict) -> str:
    line = (f"#{rec['seq']} {rec['time']} {rec['kind']} {rec.get('spec') or '-'} "
            f"{rec.get('gate') or '-'} {_info(rec)} ({rec['actor']})")
    return line if len(line) <= 200 else line[:199] + "…"


def format_log(records: list[dict], open_only=False) -> list[str]:
    """R020-27 (one line per record) and R020-41 (open escalations with their detail)."""
    if not open_only:
        return [_line(r) for r in records]
    out = []
    for rec in _open_in(records):
        out.append(_line(rec))
        out += [f"  {d}" for d in rec.get("detail") or []]
    return out or ["no open escalation"]


def audit(cfg, base="HEAD", staged=False) -> list[str]:
    """R020-28: the log reads, its cited reviews match, and it only grew since REF."""
    root = cfg.root
    rel = _log_rel_lenient(cfg)

    def read(path_rel: str) -> bytes | None:
        if staged:
            return _git.staged(root, path_rel)
        p = root / path_rel
        return p.read_bytes() if p.is_file() else None

    current = read(rel)
    problems: list[str] = []
    records: list[dict] = []
    if current is not None:
        try:
            records = _parse_log(current, rel)
        except ChaosError as exc:
            problems.append(str(exc))
    for rec in records:
        for cited in rec.get("reviews") or []:
            data = read(cited.get("review", ""))
            if data is None:
                problems.append(f"{cited.get('review')}: cited by chaos log #{rec['seq']} "
                                "but missing")
            elif lock.sha256_lf(data) != cited.get("review_sha256"):
                problems.append(f"{cited.get('review')}: changed since chaos log #{rec['seq']} "
                                "cited it")
    if _git.is_repo(root):
        commit = _git.resolve_commit(root, base)
        if commit is not None:
            before = _git.at_ref(root, commit, rel) or b""
            if not lock._lf(current or b"").startswith(lock._lf(before)):
                problems.append(f"{rel}: rewritten since {base} (the chaos log is append-only)")
    return problems


def status_suffix(cfg) -> str:
    """R020-32: the end of status line 1; "" when chaos mode is off or has no table."""
    if "chaos" not in cfg.data:
        return ""
    try:
        st = settings(cfg)
        if not st.enabled:
            return ""
        opened = open_escalations(cfg)
    except (ConfigError, ChaosError) as exc:
        msg = str(exc)
        return f" | chaos: BROKEN ({msg if len(msg) <= 100 else msg[:99] + '…'})"
    if opened:
        return f" | chaos: PAUSED ({len(opened)} open escalation(s))"
    return " | chaos: on"


def _agent_gate_refusal(cfg, spec_id: str, gate: str) -> tuple[int, str] | None:
    """R020-31, R002-34: (exit code, message) when an agent's gate move must go through
    `chaos approve`; None otherwise."""
    if not lock.human_check():
        return None
    try:
        st = settings(cfg)
    except ConfigError as exc:
        return 2, f"agentkit.toml [chaos] is malformed ({exc}); gate moves are refused"
    if st.applies(spec_id):
        return 1, (f"spec {spec_id} is under chaos mode: run "
                   f"`agentkit chaos approve {spec_id} {gate}` instead")
    return None


# CLI -----------------------------------------------------------------------------------

def _report(rec: dict) -> int:
    kind = rec["kind"]
    if kind == "approve":
        extra = f" ({len(rec['files'])} file(s) frozen)" if rec["gate"] == "frozen" else ""
        print(f"spec {rec['spec']}: status {rec['gate']}{extra} (chaos log #{rec['seq']})")
        return 0
    if kind == "unfreeze":
        print(f"spec {rec['spec']}: unfrozen {len(rec['files'])} file(s), status tests-draft "
              f"(chaos log #{rec['seq']})")
        for p in rec["files"]:
            print(f"  - {p}")
        return 0
    if kind == "reject":
        print(f"rejected (chaos log #{rec['seq']}): "
              + " + ".join(r["verdict"] for r in rec["reviews"]))
        print("hint: address the findings, then ask for a new review")
        return 1
    print(f"escalated (chaos log #{rec['seq']}): {rec['cause']} blocks spec {rec['spec']} "
          f"{rec['gate']}")
    for d in rec.get("detail") or []:
        print(f"  {d}")
    print(HINT)
    return 1


def _cli(args) -> int:
    from agentkit.config import load_config
    cfg = load_config()
    sub = args.chaos_cmd
    try:
        if sub == "approve":
            return _report(approve(cfg, args.id, args.gate, review=args.review))
        if sub == "unfreeze":
            return _report(unfreeze(cfg, args.paths, args.reason, args.auditor_review,
                                    args.impl_review))
        if sub == "clear":
            rec = clear(cfg, seqs=args.seqs, note=args.note or "", all_open=args.all)
            print(f"cleared {', '.join(f'#{s}' for s in rec['escalations'])} "
                  f"(chaos log #{rec['seq']})")
            return 0
        if sub == "log":
            if args.last < 1:
                raise ChaosUsageError("--last needs a number of at least 1")
            records = read_log(cfg)
            if args.open:
                lines = format_log(records, open_only=True)
            else:
                if args.spec:
                    records = [r for r in records if r.get("spec") == args.spec]
                lines = format_log(records[-args.last:])
            for line in lines:
                print(line)
            return 0
        if sub == "audit":
            problems = audit(cfg, base=args.base, staged=args.staged)
            for p in problems:
                print(f"chaos audit: {p}")
            if problems:
                print("hint: restore the chaos log and the reviews from git, or ask the owner")
                return 1
            print("chaos audit: OK")
            return 0
    except ChaosUsageError as exc:
        print(f"agentkit: {exc}", file=sys.stderr)
        return 2
    except ChaosError as exc:
        print(f"agentkit: {exc}", file=sys.stderr)
        return 1
    print("chaos needs a subcommand: approve, unfreeze, clear, log or audit", file=sys.stderr)
    return 2
