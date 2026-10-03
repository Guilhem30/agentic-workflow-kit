"""Tool-neutral pre-tool guard.

Payload adapters (agentkit.payloads.*) turn each agent's hook input into neutral actions;
`evaluate` decides allow / ask / deny. The shell analysis is a best-effort early warning:
the end-of-turn verify, the pre-commit hook and CI are the real guarantee.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .lock import load_lock
from .util import glob_match, glob_to_regex, rel_to_root

ALLOW, ASK, DENY = "allow", "ask", "deny"
_SEVERITY = {ALLOW: 0, ASK: 1, DENY: 2}


@dataclass
class WriteAction:
    paths: list[str]


@dataclass
class ReadAction:
    paths: list[str]


@dataclass
class ShellAction:
    command: str


@dataclass
class Decision:
    verdict: str = ALLOW
    reasons: list[str] = field(default_factory=list)

    def add(self, verdict: str, reason: str) -> None:
        if _SEVERITY[verdict] > _SEVERITY[self.verdict]:
            self.verdict = verdict
        if reason not in self.reasons:
            self.reasons.append(reason)

    @property
    def reason(self) -> str:
        return "; ".join(self.reasons)


RESTORE_HINT = (
    "Frozen tests change only with the human's agreement: ask them (they run `agentkit lock unfreeze`). "
    "To undo an accidental change run `agentkit lock restore`."
)


class Protection:
    """Classifies repo-relative paths: frozen / deny / ask / allow."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.frozen = {p.casefold(): p for p in load_lock(cfg)["files"]}
        g = cfg.guard
        self.deny_globs = g["deny_globs"]
        self.ask_globs = g["ask_globs"]
        self.allow_globs = g["allow_globs"]
        self.build_globs = cfg.profile.get("build_output_globs", [])
        self.deny_build_reads = g["deny_build_output_reads"]
        self.frozen_names = {}
        for key in self.frozen:
            self.frozen_names.setdefault(key.rsplit("/", 1)[-1], []).append(key)

    def classify(self, rel: str) -> tuple[str, str] | None:
        key = rel.casefold()
        if key in self.frozen:
            return DENY, f"{self.frozen[key]} is a frozen test file. {RESTORE_HINT}"
        if glob_match(rel, self.allow_globs):
            return None
        if glob_match(rel, self.deny_globs):
            return DENY, f"{rel} is protected workflow infrastructure; only the human edits it"
        if glob_match(rel, self.ask_globs):
            return ASK, f"{rel} is enforcement configuration (hooks/CI); the human must approve this edit"
        return None

    def covers_dir(self, rel: str) -> str | None:
        """A frozen file under directory `rel` (for rm -r / mv of a directory)."""
        prefix = rel.casefold().rstrip("/") + "/"
        if prefix == "/":
            return next(iter(self.frozen.values()), None)
        for key, orig in self.frozen.items():
            if key.startswith(prefix):
                return orig
        return None

    def glob_hits(self, pattern_rel: str) -> str | None:
        rx = glob_to_regex(pattern_rel)
        for key, orig in self.frozen.items():
            if rx.match(key):
                return orig
        return None


def evaluate(cfg: Config, actions: list, cwd: str | None = None) -> Decision:
    prot = Protection(cfg)
    base = Path(cwd) if cwd else cfg.root
    d = Decision()
    for action in actions:
        if isinstance(action, WriteAction):
            for p in action.paths:
                rel = rel_to_root(p, cfg.root, base)
                if rel is None:
                    continue
                hit = prot.classify(rel)
                if hit:
                    d.add(*hit)
        elif isinstance(action, ReadAction):
            if not prot.deny_build_reads:
                continue
            for p in action.paths:
                rel = rel_to_root(p, cfg.root, base)
                if rel and glob_match(rel, prot.build_globs):
                    d.add(DENY, f"{rel} is build output; use `agentkit test` for a compact summary instead of reading it")
        elif isinstance(action, ShellAction):
            check_shell(prot, action.command, base, d)
    return d


# -- shell analysis -----------------------------------------------------------

WRITE_CMDS = {
    "rm", "rmdir", "mv", "cp", "tee", "truncate", "dd", "touch", "ln", "install", "unlink", "shred",
    "chmod", "chown", "patch",
    "del", "erase", "rd", "ren", "rename", "move", "copy", "xcopy", "robocopy",
    "set-content", "add-content", "out-file", "remove-item", "move-item", "copy-item", "new-item",
    "clear-content", "rename-item", "sc", "ac", "ri", "mi", "cpi", "ni", "rni", "clc",
}
DESTRUCTIVE_CMDS = {"rm", "rmdir", "rd", "del", "erase", "remove-item", "ri", "mv", "move", "move-item", "mi", "shred"}
GIT_WRITE_SUBCMDS = {"checkout", "restore", "rm", "mv", "apply", "am", "update-index"}
INTERPRETERS = {"python", "python3", "py", "node", "deno", "bun", "ruby", "perl", "php", "pwsh", "powershell", "bash", "sh", "zsh"}
PREFIX_WORDS = {"sudo", "env", "command", "builtin", "exec", "nohup", "time", "xargs", "&", "!"}
SEPARATORS = {";", "&&", "||", "|", "&", "\n", "(", ")", "|&", ";;"}
REDIRECTS = {">", ">>", ">|", "&>", "&>>", "1>", "2>", "1>>", "2>>"}

_UNFREEZE_RX = re.compile(r"\block\s+unfreeze\b")
_AGENTKIT_RX = re.compile(r"agentkit")


def _tokenize(command: str) -> list[str]:
    text = command.replace("\\", "/")
    try:
        lex = shlex.shlex(text, posix=True, punctuation_chars=";&|()<>")
        lex.whitespace_split = True
        lex.commenters = ""
        tokens = []
        for tok in lex:
            tokens.append(tok)
        return tokens
    except ValueError:
        return [t for t in re.split(r"\s+|([;&|()<>]+)", text) if t]


def _segments(tokens: list[str]) -> list[list[str]]:
    segs, cur = [], []
    for t in tokens:
        if t in SEPARATORS:
            if cur:
                segs.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        segs.append(cur)
    return segs


def _strip_prefix(seg: list[str]) -> list[str]:
    i = 0
    while i < len(seg):
        t = seg[i]
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", t) or t in PREFIX_WORDS:
            i += 1
            continue
        if t.startswith("-") and i > 0 and seg[i - 1] in ("xargs", "env", "sudo", "time"):
            i += 1
            continue
        break
    return seg[i:]


def _split_redirects(seg: list[str]) -> tuple[list[str], list[str]]:
    words, targets = [], []
    i = 0
    while i < len(seg):
        t = seg[i]
        if t in REDIRECTS or (t.endswith(">") and t.rstrip(">").isdigit()):
            if i + 1 < len(seg):
                targets.append(seg[i + 1])
            i += 2
            continue
        if t in (">&", "<", "<<", "<<<", "<&"):
            i += 2
            continue
        words.append(t)
        i += 1
    return words, targets


def check_shell(prot: Protection, command: str, cwd: Path, d: Decision) -> None:
    lowered = command.lower()
    # 1. the unfreeze command itself
    if _AGENTKIT_RX.search(lowered) and _UNFREEZE_RX.search(lowered):
        d.add(DENY, "`agentkit lock unfreeze` may only be run by the human, in their own terminal")
    tokens = _tokenize(command)
    for seg in _segments(tokens):
        words, redirect_targets = _split_redirects(seg)
        words = _strip_prefix(words)
        if words and words[0] == "cd" and len(words) > 1:
            nxt = rel_to_root(words[1], prot.cfg.root, cwd)
            if nxt is not None:
                cwd = prot.cfg.root / nxt
            continue
        for t in redirect_targets:
            _check_target(prot, t, cwd, d, destructive=False)
        if not words:
            continue
        cmd = words[0].rsplit("/", 1)[-1].casefold()
        if cmd.endswith(".exe"):
            cmd = cmd[:-4]
        args = words[1:]
        if cmd == "git":
            _check_git(prot, args, cwd, d)
            continue
        write = destructive = False
        if cmd in WRITE_CMDS:
            write, destructive = True, cmd in DESTRUCTIVE_CMDS
        elif cmd in ("sed", "perl") and any(re.fullmatch(r"-[a-zA-Z]*i\S*|--in-place\S*", a) for a in args):
            write = True
        elif cmd == "find" and any(a in ("-delete", "-exec", "-execdir") for a in args):
            write = destructive = True
        elif cmd in INTERPRETERS and any(a in ("-c", "-e", "-command", "--eval", "-r") for a in (x.casefold() for x in args)):
            write = True  # inline scripts that mention a protected path
            _check_inline(prot, " ".join(args), d)
        if write:
            for a in args:
                if a.startswith("-") and "=" not in a:
                    continue
                _check_target(prot, a.split("=", 1)[-1], cwd, d, destructive)


def _check_git(prot: Protection, args: list[str], cwd: Path, d: Decision) -> None:
    joined = " ".join(args).casefold()
    if "core.hookspath" in joined:
        d.add(DENY, "changing git core.hooksPath disables the pre-commit lock check")
    sub_i = 0
    while sub_i < len(args) and args[sub_i].startswith("-"):
        sub_i += 2 if args[sub_i] in ("-c", "-C") else 1
    if sub_i >= len(args):
        return
    sub, rest = args[sub_i], args[sub_i + 1 :]
    if sub in ("commit", "push", "merge", "rebase", "am", "cherry-pick", "revert"):
        for a in rest:
            if a == "--no-verify" or (sub == "commit" and re.fullmatch(r"-[a-zA-Z]*n[a-zA-Z]*", a)):
                d.add(DENY, "--no-verify bypasses the pre-commit lock check; it is forbidden")
                break
    if sub == "update-index" and any(a in ("--assume-unchanged", "--skip-worktree") for a in rest):
        d.add(DENY, "git update-index --assume-unchanged/--skip-worktree hides changes from the lock check")
    if sub in GIT_WRITE_SUBCMDS:
        for a in rest:
            if a.startswith("-") or a == "--":
                continue
            _check_target(prot, a, cwd, d, destructive=sub in ("rm", "mv"))


def _check_inline(prot: Protection, script: str, d: Decision) -> None:
    low = script.casefold().replace("\\", "/")
    for key, orig in prot.frozen.items():
        if key in low or (len(key.rsplit("/", 1)[-1]) > 4 and key.rsplit("/", 1)[-1] in low):
            d.add(DENY, f"inline script mentions frozen file {orig}. {RESTORE_HINT}")
            return
    for name in (prot.cfg.lock_rel, prot.cfg.unfreeze_log_rel):
        if name.casefold() in low:
            d.add(DENY, f"inline script mentions {name}; only the human edits it")


def _check_target(prot: Protection, token: str, cwd: Path, d: Decision, destructive: bool) -> None:
    token = token.strip().strip("'\"")
    if not token or token in ("/dev/null", "nul", "NUL", "$null") or token.startswith("$"):
        return
    rel = rel_to_root(token, prot.cfg.root, cwd)
    if rel is None:
        return
    if any(ch in token for ch in "*?["):
        hit = prot.glob_hits(rel)
        if hit:
            d.add(DENY, f"`{token}` matches frozen file {hit}. {RESTORE_HINT}")
        return
    if rel != "":
        hit = prot.classify(rel)
        if hit:
            d.add(*hit)
            return
    if destructive:
        under = prot.covers_dir(rel)
        if under:
            d.add(DENY, f"`{token}` contains frozen file {under}. {RESTORE_HINT}")
            return
    if "/" not in token:
        for key in prot.frozen_names.get(token.casefold(), []):
            d.add(DENY, f"`{token}` looks like frozen file {prot.frozen[key]}. {RESTORE_HINT}")
            return
