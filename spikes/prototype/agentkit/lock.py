"""The test-freeze lock: `tests.lock.json` maps each frozen file to its LF-normalised SHA-256."""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .specs import find_spec, req_regex, set_status
from .util import (
    git,
    git_bytes,
    glob_match,
    is_git_repo,
    list_repo_files,
    rel_to_root,
    sha256_bytes,
    write_bytes,
    write_text_lf,
)

LOCK_VERSION = 1
ALGORITHM = "sha256-lf"
LOG_HEADER = (
    "# Unfreeze log\n\n"
    "Append-only. Written by `agentkit lock unfreeze`, which only a human may run.\n"
)

# Environment variables that reveal an agent-controlled shell.
AGENT_ENV_VARS = ("AGENTKIT_AGENT", "CLAUDECODE", "CODEX_SANDBOX", "CODEX_THREAD_ID", "OPENCODE", "PI_CODING_AGENT")


class LockError(Exception):
    pass


@dataclass
class Violation:
    path: str
    kind: str  # missing | modified

    def __str__(self) -> str:
        return f"{self.kind}: {self.path}"


@dataclass
class FreezeResult:
    added: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# -- lock file I/O ---------------------------------------------------------


def empty_lock() -> dict:
    return {"version": LOCK_VERSION, "algorithm": ALGORITHM, "files": {}}


def parse_lock(raw: bytes | str | None) -> dict:
    if raw is None:
        return empty_lock()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if not raw.strip():
        return empty_lock()
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("files"), dict):
        raise LockError("malformed lock file: expected an object with a 'files' map")
    if data.get("algorithm", ALGORITHM) != ALGORITHM:
        raise LockError(f"unsupported lock algorithm {data.get('algorithm')}")
    return data


def load_lock(cfg: Config) -> dict:
    if not cfg.lock_path.is_file():
        return empty_lock()
    return parse_lock(cfg.lock_path.read_bytes())


def dump_lock(lock: dict) -> str:
    out = {"version": LOCK_VERSION, "algorithm": ALGORITHM, "files": dict(sorted(lock["files"].items()))}
    return json.dumps(out, indent=2, sort_keys=False) + "\n"


def save_lock(cfg: Config, lock: dict) -> None:
    write_text_lf(cfg.lock_path, dump_lock(lock))


def read_file(cfg: Config, rel: str, staged: bool = False) -> bytes | None:
    """Worktree content, or the index (staged) content when `staged`."""
    if staged:
        return git_bytes(cfg.root, "show", f":{rel}")
    p = cfg.root / rel
    return p.read_bytes() if p.is_file() else None


# -- verify / status -------------------------------------------------------


def verify(cfg: Config, staged: bool = False) -> list[Violation]:
    if staged:
        lock = parse_lock(git_bytes(cfg.root, "show", f":{cfg.lock_rel}"))
    else:
        lock = load_lock(cfg)
    out = []
    for rel, entry in sorted(lock["files"].items()):
        data = read_file(cfg, rel, staged)
        if data is None:
            out.append(Violation(rel, "missing"))
        elif sha256_bytes(data) != entry["sha256"]:
            out.append(Violation(rel, "modified"))
    return out


def candidates(cfg: Config) -> list[str]:
    """Files that match the profile's frozen globs (frozen or not)."""
    files = list_repo_files(cfg.root, exclude_globs=cfg.profile.get("build_output_globs", []))
    return [f for f in files if glob_match(f, cfg.frozen_globs)]


def status(cfg: Config) -> dict:
    lock = load_lock(cfg)
    frozen = lock["files"]
    by_spec: dict[str, int] = {}
    for entry in frozen.values():
        key = entry.get("spec") or "-"
        by_spec[key] = by_spec.get(key, 0) + 1
    unfrozen = [f for f in candidates(cfg) if f not in frozen]
    return {
        "frozen": len(frozen),
        "by_spec": dict(sorted(by_spec.items())),
        "unfrozen_candidates": unfrozen,
        "violations": verify(cfg),
    }


# -- freeze ----------------------------------------------------------------


def _expand(cfg: Config, paths: list[str]) -> tuple[list[str], list[str]]:
    files, errors = [], []
    all_files = None
    for p in paths:
        rel = rel_to_root(p, cfg.root, Path.cwd())
        if rel is None:
            errors.append(f"outside repository: {p}")
            continue
        target = cfg.root / rel
        if target.is_file():
            files.append(rel)
        elif target.is_dir():
            if all_files is None:
                all_files = list_repo_files(cfg.root, cfg.profile.get("build_output_globs", []))
            prefix = rel.rstrip("/") + "/" if rel else ""
            files.extend(f for f in all_files if f.startswith(prefix) and glob_match(f, cfg.frozen_globs))
        else:
            errors.append(f"not found: {p}")
    return files, errors


def _belongs_to_spec(cfg: Config, rel: str, spec_id: str) -> bool:
    if re.search(rf"(^|/)({spec_id})(-[^/]*)?(/|$)", rel):
        return True
    try:
        text = (cfg.root / rel).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return any(m.group(1) == spec_id for m in req_regex(cfg).finditer(text))


def freeze(
    cfg: Config,
    paths: list[str] | None = None,
    spec: str | None = None,
    all_candidates: bool = False,
    update_spec_status: bool = True,
) -> FreezeResult:
    """Add files to the lock. Already-frozen files must be unchanged (use unfreeze first)."""
    res = FreezeResult()
    lock = load_lock(cfg)
    frozen = lock["files"]
    spec_id = spec.zfill(3) if spec else None
    if paths:
        targets, res.errors = _expand(cfg, paths)
    elif spec_id or all_candidates:
        targets = [f for f in candidates(cfg) if f not in frozen]
        if spec_id and not all_candidates:
            targets = [f for f in targets if _belongs_to_spec(cfg, f, spec_id)]
    else:
        raise LockError("nothing to freeze: give PATHS, --spec NNN or --all")
    for rel in sorted(set(targets)):
        if rel in (cfg.lock_rel, cfg.unfreeze_log_rel):
            res.errors.append(f"cannot freeze the lock or its log: {rel}")
            continue
        digest = sha256_bytes((cfg.root / rel).read_bytes())
        if rel in frozen:
            if frozen[rel]["sha256"] == digest:
                res.unchanged.append(rel)
            else:
                res.errors.append(f"already frozen with different content (unfreeze first): {rel}")
            continue
        entry = {"sha256": digest}
        if spec_id:
            entry["spec"] = spec_id
        frozen[rel] = entry
        res.added.append(rel)
    if res.errors:
        return res  # all-or-nothing
    if res.added:
        save_lock(cfg, lock)
    if spec_id and update_spec_status:
        s = find_spec(cfg, spec_id)
        if s and s.spec_md.is_file() and s.status in ("tests-approved", "tests-draft", "approved"):
            set_status(s, "frozen")
    return res


# -- unfreeze (human only) ---------------------------------------------------


def agent_environment() -> str | None:
    for var in AGENT_ENV_VARS:
        if os.environ.get(var):
            return var
    return None


def console_confirm(prompt: str, expected: str) -> bool:
    """Ask on the real console (not stdin), so a piped agent shell cannot answer."""
    try:
        if os.name == "nt":
            out = open("CONOUT$", "w", encoding="utf-8")
            inp = open("CONIN$", "r", encoding="utf-8")
        else:
            out = inp = open("/dev/tty", "r+", encoding="utf-8")
    except OSError:
        return False
    try:
        out.write(prompt)
        out.flush()
        answer = inp.readline().strip()
    finally:
        out.close()
        if inp is not out:
            inp.close()
    return answer == expected


def human_check() -> str | None:
    """Reason why this process is not considered a human terminal, or None."""
    var = agent_environment()
    if var:
        return f"refusing: agent environment detected ({var}). Run this in your own terminal."
    return None


def git_user(cfg: Config) -> str:
    try:
        name = git(cfg.root, "config", "user.name").stdout.strip()
    except OSError:
        name = ""
    return name or os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"


def unfreeze(cfg: Config, paths: list[str], reason: str, confirm=None, user: str | None = None, now=None) -> list[str]:
    """Remove files from the lock and append an entry to the unfreeze log.

    `confirm(prompt, expected) -> bool` defaults to an on-console prompt; tests inject their own.
    """
    if not reason or len(reason.strip()) < 5:
        raise LockError("a --reason of at least 5 characters is required")
    lock = load_lock(cfg)
    frozen = lock["files"]
    rels = []
    for p in paths:
        rel = rel_to_root(p, cfg.root, Path.cwd())
        if rel is None:
            raise LockError(f"outside repository: {p}")
        if rel.endswith("/") or (cfg.root / rel).is_dir():
            prefix = rel.rstrip("/") + "/"
            matched = [f for f in frozen if f.startswith(prefix)]
        else:
            matched = [rel] if rel in frozen else []
        if not matched:
            raise LockError(f"not frozen: {p}")
        rels.extend(matched)
    rels = sorted(set(rels))
    confirm = confirm or console_confirm
    expected = f"unfreeze {len(rels)}"
    listing = "\n".join(f"  {r}" for r in rels)
    if not confirm(f"About to unfreeze {len(rels)} file(s):\n{listing}\nType '{expected}' to confirm: ", expected):
        raise LockError("not confirmed (an interactive terminal is required)")
    for r in rels:
        del frozen[r]
    save_lock(cfg, lock)
    stamp = (now or _dt.datetime.now(_dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = f"\n## {stamp} - {user or git_user(cfg)}\n\nreason: {reason.strip()}\n\n" + "".join(f"- {r}\n" for r in rels)
    log = cfg.unfreeze_log_path
    text = log.read_text(encoding="utf-8") if log.is_file() else LOG_HEADER
    write_text_lf(log, text.rstrip("\n") + "\n" + entry)
    return rels


def parse_log(text: str) -> list[tuple[str, list[str]]]:
    """[(header, [paths])] for every `## ` entry of the unfreeze log."""
    entries: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        if line.startswith("## "):
            entries.append((line[3:].strip(), []))
        elif entries and line.startswith("- "):
            entries[-1][1].append(line[2:].strip())
    return entries


# -- restore / audit -----------------------------------------------------------


def restore(cfg: Config, paths: list[str] | None = None, ref: str = "HEAD") -> tuple[list[str], list[str]]:
    """Put tampered frozen files back from git when the committed content matches the lock."""
    lock = load_lock(cfg)
    restored, failed = [], []
    targets = [v.path for v in verify(cfg)]
    if paths:
        wanted = {rel_to_root(p, cfg.root, Path.cwd()) for p in paths}
        targets = [t for t in targets if t in wanted]
    for rel in targets:
        data = git_bytes(cfg.root, "show", f"{ref}:{rel}")
        if data is not None and sha256_bytes(data) == lock["files"][rel]["sha256"]:
            write_bytes(cfg.root / rel, data)
            restored.append(rel)
        else:
            failed.append(rel)
    return restored, failed


def audit(cfg: Config, base: str = "HEAD", staged: bool = False) -> list[str]:
    """Every lock entry removed or changed since `base` must be covered by a new unfreeze-log entry."""
    if not is_git_repo(cfg.root):
        return []
    if git(cfg.root, "rev-parse", "--verify", "--quiet", base + "^{commit}").returncode != 0:
        return []  # no base yet (first commit)
    old = parse_lock(git_bytes(cfg.root, "show", f"{base}:{cfg.lock_rel}"))
    if staged:
        new = parse_lock(git_bytes(cfg.root, "show", f":{cfg.lock_rel}"))
        new_log = (git_bytes(cfg.root, "show", f":{cfg.unfreeze_log_rel}") or b"").decode("utf-8", "replace")
    else:
        new = load_lock(cfg)
        new_log = cfg.unfreeze_log_path.read_text(encoding="utf-8") if cfg.unfreeze_log_path.is_file() else ""
    old_log = (git_bytes(cfg.root, "show", f"{base}:{cfg.unfreeze_log_rel}") or b"").decode("utf-8", "replace")
    old_headers = {h for h, _ in parse_log(old_log)}
    if not new_log.startswith(old_log.rstrip("\n")):
        problems = [f"{cfg.unfreeze_log_rel} was rewritten (it is append-only)"]
    else:
        problems = []
    allowed = set()
    for header, paths in parse_log(new_log):
        if header not in old_headers:
            allowed.update(paths)
    for rel, entry in old["files"].items():
        cur = new["files"].get(rel)
        if cur is None or cur["sha256"] != entry["sha256"]:
            if rel not in allowed:
                change = "removed from" if cur is None else "re-hashed in"
                problems.append(f"{rel} {change} the lock without an unfreeze-log entry")
    return problems
