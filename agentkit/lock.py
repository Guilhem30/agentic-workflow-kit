"""Test-freeze lock (spec 002)."""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from agentkit import _git, specs
from agentkit.util import glob_match

ALGORITHM = "sha256-lf"
AGENT_ENV_VARS = ("AGENTKIT_AGENT", "CLAUDECODE", "CODEX_SANDBOX", "CODEX_THREAD_ID",
                  "OPENCODE", "PI_CODING_AGENT")

LOG_HEADER = "# Unfreeze log\n\nAppend-only: earlier entries are never rewritten.\n"


class LockError(Exception):
    """A lock problem. The CLI reports it and exits 1."""


class OwnerCheckError(LockError):
    """An owner-only action refused (agent environment, no confirmation). The CLI exits 2."""


@dataclass
class Violation:
    path: str
    kind: str  # "missing" | "modified"


@dataclass
class FreezeResult:
    added: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# helpers ---------------------------------------------------------------------------------

def sha256_lf(data: bytes) -> str:
    """R002-03: SHA-256 of the bytes with every CRLF replaced by LF."""
    return hashlib.sha256(_lf(data)).hexdigest()


def _lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def _empty() -> dict:
    return {"version": 1, "algorithm": ALGORITHM, "files": {}}


def _parse_lock(raw: bytes | None, where: str) -> dict:
    if raw is None or not raw.strip():
        return _empty()
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise LockError(f"{where}: not valid JSON ({exc})") from None
    if not isinstance(data, dict) or not isinstance(data.get("files"), dict):
        raise LockError(f"{where}: lacks a \"files\" object")
    if data.get("algorithm", ALGORITHM) != ALGORITHM:
        raise LockError(f"{where}: unsupported algorithm {data.get('algorithm')!r} "
                        f"(expected {ALGORITHM})")
    for path, entry in data["files"].items():
        if not isinstance(entry, dict) or not isinstance(entry.get("sha256"), str):
            raise LockError(f"{where}: entry for {path} lacks a sha256 in its files object")
    return data


def _write_lock(cfg, files: dict) -> None:
    data = {"version": 1, "algorithm": ALGORITHM,
            "files": {k: files[k] for k in sorted(files)}}
    cfg.lock_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.lock_path.write_bytes((json.dumps(data, indent=2) + "\n").encode("utf-8"))


def _rel(cfg, path) -> str | None:
    """Repo-relative `/` path for an absolute or root-relative path; None when outside."""
    p = Path(path)
    if not p.is_absolute():
        p = cfg.root / p
    p = Path(os.path.normpath(p))
    try:
        rel = p.relative_to(cfg.root)
    except ValueError:
        try:
            rel = p.resolve().relative_to(cfg.root.resolve())
        except ValueError:
            return None
    text = rel.as_posix()
    return "" if text == "." else text


def _same_file(cfg, a: str, b: str) -> bool:
    try:
        return (cfg.root / a).samefile(cfg.root / b)
    except OSError:
        return False


def _lock_key(cfg, files: dict, rel: str) -> str:
    """The lock's spelling of rel. On a case-insensitive file system `Tests/a.py` and an
    existing key `tests/a.py` name the same file, so the existing key wins."""
    if rel in files:
        return rel
    for key in files:
        if key.casefold() == rel.casefold() and _same_file(cfg, key, rel):
            return key
    return rel


def _is_protected(cfg, rel: str) -> bool:
    """The lock and the unfreeze log, compared case-insensitively (R002-11)."""
    return rel.casefold() in {cfg.lock_rel.casefold(), cfg.unfreeze_log_rel.casefold()}


def _is_candidate(cfg, rel: str) -> bool:
    return glob_match(rel, cfg.frozen_globs) and not glob_match(
        rel, cfg.profile["build_output_globs"])


def _candidates(cfg) -> list[str]:
    return [rel for rel in _git.repo_files(cfg.root) if _is_candidate(cfg, rel)]


def _belongs(cfg, rel: str, spec_id: str) -> bool:
    if any(seg == spec_id or seg.startswith(spec_id + "-") for seg in rel.split("/")):
        return True
    try:
        text = (cfg.root / rel).read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return False
    rx = re.compile(cfg.profile["req_id_regex"])
    return any(m.group(1) == spec_id for m in rx.finditer(text))


def _now_text(now: datetime | None) -> str:
    now = now or datetime.now(timezone.utc)
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_log(cfg, lines: list[str]) -> None:
    """Append one entry (preceded by a blank line) to the unfreeze log (R002-24, R002-25)."""
    path = cfg.unfreeze_log_path
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_bytes() if path.exists() else b""
    if not old.strip():
        prefix = LOG_HEADER.encode("utf-8")
        mode = "wb"
    else:
        prefix = b"" if old.endswith(b"\n") else b"\n"
        mode = "ab"
    with open(path, mode) as f:
        f.write(prefix + ("\n" + "".join(line + "\n" for line in lines)).encode("utf-8"))


def _confirm_on_console(prompt: str, expected: str) -> bool:
    try:
        reader, writer = open_console()
    except OSError as exc:
        raise LockError(f"cannot open the console to confirm ({exc}); nothing changed") from None
    try:
        writer.write(prompt + f"\nType '{expected}' to confirm: ")
        writer.flush()
        answer = reader.readline()
    finally:
        # Close only the console files open_console() opened. A test double (an in-memory
        # stream) stays open so the caller can read what was written to it.
        for f in (reader, writer):
            if isinstance(f, io.TextIOWrapper) and f not in (sys.stdin, sys.stdout, sys.stderr):
                f.close()
    return answer.strip() == expected


def _expand_frozen(cfg, files: dict, paths) -> tuple[list[str], list[str]]:
    """Paths (files or directories) -> (frozen repo-relative paths, bad arguments)."""
    out: list[str] = []
    bad: list[str] = []
    for given in paths:
        rel = _rel(cfg, given)
        if rel is None:
            bad.append(f"{given}: outside the repository")
            continue
        key = _lock_key(cfg, files, rel)
        if key in files:
            out.append(key)
            continue
        inside = [k for k in files if rel == "" or k.startswith(rel.rstrip("/") + "/")]
        if inside:
            out.extend(inside)
        else:
            bad.append(f"{rel or given}: not frozen")
    return sorted(set(out)), bad


# public API ------------------------------------------------------------------------------

def load_lock(cfg) -> dict:
    path = cfg.lock_path
    return _parse_lock(path.read_bytes() if path.exists() else None, cfg.lock_rel)


def _load_staged_lock(cfg) -> dict:
    return _parse_lock(_git.staged(cfg.root, cfg.lock_rel), f"{cfg.lock_rel} (index)")


def verify(cfg, staged: bool = False) -> list[Violation]:
    files = (_load_staged_lock(cfg) if staged else load_lock(cfg))["files"]
    out = []
    pre = _git.prefix(cfg.root) if staged else ""
    for rel in sorted(files):
        if staged:
            data = _git.staged(cfg.root, rel, pre)
        else:
            p = cfg.root / rel
            data = p.read_bytes() if p.is_file() else None
        if data is None:
            out.append(Violation(rel, "missing"))
        elif sha256_lf(data) != files[rel]["sha256"]:
            out.append(Violation(rel, "modified"))
    return out


def status(cfg) -> dict:
    files = load_lock(cfg)["files"]
    by_spec: dict[str | None, int] = {}
    for entry in files.values():
        key = entry.get("spec")
        by_spec[key] = by_spec.get(key, 0) + 1
    return {
        "frozen": len(files),
        "by_spec": by_spec,
        "unfrozen_candidates": sorted(c for c in _candidates(cfg) if c not in files),
        "violations": verify(cfg),
    }


def freeze(cfg, paths=None, spec=None, all_candidates=False,
           force=False, confirm=None, user=None, now=None) -> FreezeResult:
    if not paths and spec is None and not all_candidates:
        raise LockError("nothing to freeze: give paths, --spec NNN or --all")
    files = dict(load_lock(cfg)["files"])
    result = FreezeResult()
    spec_obj = None
    forced_from = None
    if spec is not None:
        spec_obj = specs.find_spec(cfg, spec)
        if spec_obj is None:
            raise LockError(f"spec {spec} does not exist")
        if spec_obj.status != "tests-approved":
            if not force:
                raise LockError(f"spec {spec} is in phase {spec_obj.status}; freeze needs "
                                "tests-approved")
            reason = human_check()
            if reason:
                raise OwnerCheckError(reason)
            ask = confirm or _confirm_on_console
            expected = f"force freeze {spec}"
            try:
                ok = ask(f"Force-freeze spec {spec} (status {spec_obj.status}).", expected)
            except LockError as exc:
                raise OwnerCheckError(str(exc)) from None
            if not ok:
                raise OwnerCheckError(f"confirmation did not match {expected!r}; nothing changed")
            forced_from = spec_obj.status

    targets: list[str] = []
    candidates = _candidates(cfg)
    for given in paths or []:
        rel = _rel(cfg, given)
        if rel is None:
            result.errors.append(f"{given}: outside the repository")
            continue
        # Prefer the lock's spelling, then git's, so `Tests/a.py` never adds a second key
        # on a case-insensitive file system.
        rel = _lock_key(cfg, files, rel.rstrip("/"))
        if rel not in files:
            rel = _lock_key(cfg, dict.fromkeys(candidates), rel)
        full = cfg.root / rel
        if _is_protected(cfg, rel):
            result.errors.append(f"{rel}: the lock and the unfreeze log cannot be frozen")
        elif full.is_dir():
            pre = "" if rel == "" else (rel + "/").casefold()
            targets += [c for c in candidates if c.casefold().startswith(pre)]
        elif not full.is_file():
            result.errors.append(f"{rel}: does not exist")
        else:
            targets.append(rel)
    if spec is not None or all_candidates:
        for cand in candidates:
            if cand in files or _is_protected(cfg, cand):
                continue
            if all_candidates or _belongs(cfg, cand, spec):
                targets.append(cand)

    new_entries: dict[str, dict] = {}
    for rel in dict.fromkeys(targets):
        if _is_protected(cfg, rel):
            continue
        digest = sha256_lf((cfg.root / rel).read_bytes())
        if rel in files:
            if files[rel]["sha256"] == digest:
                result.unchanged.append(rel)
            else:
                result.errors.append(f"{rel}: already frozen with a different hash "
                                     "(ask the owner, or run agentkit lock restore)")
            continue
        entry = {"sha256": digest}
        if spec is not None:
            entry["spec"] = spec
        new_entries[rel] = entry
        result.added.append(rel)
    if result.errors:
        result.added = []
        return result
    result.added.sort()
    if new_entries:
        files.update(new_entries)
        _write_lock(cfg, files)
    if forced_from is not None:
        _append_log(cfg, [f"## {_now_text(now)} - {user or _git.user_name(cfg.root)}",
                          f"forced freeze of spec {spec} (status was {forced_from})"]
                    + [f"- {p}" for p in result.added])
    if spec_obj is not None:
        specs.set_status(spec_obj, "frozen")
    return result


def unfreeze(cfg, paths, reason, confirm=None, user=None, now=None) -> list[str]:
    text = (reason or "").strip()
    if len(text) < 5:
        raise LockError("a reason of at least 5 characters is required (--reason)")
    refused = human_check()
    if refused:
        raise OwnerCheckError(refused)
    files = dict(load_lock(cfg)["files"])
    chosen, bad = _expand_frozen(cfg, files, paths)
    if bad or not chosen:
        raise LockError("cannot unfreeze: " + "; ".join(bad or ["no path given"]))
    expected = f"unfreeze {len(chosen)}"
    ask = confirm or _confirm_on_console
    prompt = "Unfreeze these files:\n" + "".join(f"  {p}\n" for p in chosen) + f"reason: {text}"
    if not ask(prompt, expected):
        raise LockError(f"confirmation did not match {expected!r}; nothing changed")
    for rel in chosen:
        del files[rel]
    _write_lock(cfg, files)
    _append_log(cfg, [f"## {_now_text(now)} - {user or _git.user_name(cfg.root)}",
                      f"reason: {text}"] + [f"- {p}" for p in chosen])
    return chosen


def human_check() -> str | None:
    for name in AGENT_ENV_VARS:
        if os.environ.get(name):
            return (f"refused: {name} is set, so this runs inside an agent tool; only the owner "
                    "may do this, from their own terminal")
    return None


def open_console():
    name_in, name_out = ("CONIN$", "CONOUT$") if os.name == "nt" else ("/dev/tty", "/dev/tty")
    reader = open(name_in, "r", encoding="utf-8")
    try:
        writer = open(name_out, "w", encoding="utf-8")
    except OSError:
        reader.close()
        raise
    return reader, writer


def restore(cfg, paths=None, ref="HEAD") -> tuple[list[str], list[str]]:
    files = load_lock(cfg)["files"]
    violated = {v.path for v in verify(cfg)}
    failed: list[str] = []
    if paths:
        wanted = []
        for given in paths:
            rel = _rel(cfg, given)
            if rel is not None:
                rel = _lock_key(cfg, files, rel)
            if rel is None or rel not in files:
                failed.append(rel or str(given))
            elif rel in violated:
                wanted.append(rel)
    else:
        wanted = sorted(violated)
    commit = _git.resolve_commit(cfg.root, ref)
    if commit is None:
        return [], sorted(set(failed) | set(wanted))
    restored = []
    pre = _git.prefix(cfg.root)
    for rel in wanted:
        data = _git.at_ref(cfg.root, commit, rel, pre)
        if data is None or sha256_lf(data) != files[rel]["sha256"]:
            failed.append(rel)
            continue
        target = cfg.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        restored.append(rel)
    return sorted(restored), sorted(failed)


def _log_entries(text: str) -> list[tuple[str, list[str]]]:
    entries: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        if line.startswith("## "):
            entries.append((line, []))
        elif entries and line.startswith("- "):
            entries[-1][1].append(line[2:].strip())
    return entries


def audit(cfg, base="HEAD", staged=False) -> list[str]:
    problems: list[str] = []
    root = cfg.root
    if staged:
        now_lock = _load_staged_lock(cfg)
        log_now = _git.staged(root, cfg.unfreeze_log_rel) or b""
    else:
        now_lock = load_lock(cfg)
        p = cfg.unfreeze_log_path
        log_now = p.read_bytes() if p.exists() else b""
    commit = _git.resolve_commit(root, base) if _git.is_repo(root) else None
    if commit is not None:
        pre = _git.prefix(root)
        base_lock = _parse_lock(_git.at_ref(root, commit, cfg.lock_rel, pre),
                                f"{cfg.lock_rel} at {base}")
        log_base = _git.at_ref(root, commit, cfg.unfreeze_log_rel, pre) or b""
        if not _lf(log_now).startswith(_lf(log_base)):
            problems.append(f"{cfg.unfreeze_log_rel}: rewritten since {base} (the log is "
                            "append-only)")
        base_text = log_base.decode("utf-8", "replace")
        base_headers = {h for h, _ in _log_entries(base_text)}
        covered = set()
        for header, entry_paths in _log_entries(log_now.decode("utf-8", "replace")):
            if header not in base_headers:
                covered.update(entry_paths)
        current = now_lock["files"]
        for rel, entry in sorted(base_lock["files"].items()):
            if rel in covered:
                continue
            if rel not in current:
                problems.append(f"{rel}: removed from the lock since {base} without an "
                                "unfreeze-log entry")
            elif current[rel].get("sha256") != entry.get("sha256"):
                problems.append(f"{rel}: re-hashed in the lock since {base} without an "
                                "unfreeze-log entry")
    problems += _chaos_audit(cfg, base, staged)
    return problems


def _chaos_audit(cfg, base, staged) -> list[str]:
    """R002-33: when a chaos log exists (in the index with --staged), audit it too."""
    from agentkit import chaos
    rel = chaos._log_rel_lenient(cfg)
    exists = (_git.staged(cfg.root, rel) is not None) if staged else (cfg.root / rel).is_file()
    return chaos.audit(cfg, base=base, staged=staged) if exists else []
