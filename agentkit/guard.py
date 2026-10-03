"""Guard: neutral actions and allow/ask/deny decisions (spec 003)."""
from __future__ import annotations

import os
import posixpath
import re
import shlex
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .util import glob_match, glob_to_regex

ALLOW, ASK, DENY = "allow", "ask", "deny"


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
    verdict: str
    reasons: list[str] = field(default_factory=list)

    @property
    def reason(self) -> str:
        return "; ".join(self.reasons)


_SEVERITY = {ALLOW: 0, ASK: 1, DENY: 2}

_STATE_GLOBS = [".agentkit/state/**"]
_ASK_GLOBS = [".claude/settings.json", ".codex/hooks.json", ".codex/config.toml",
              ".opencode/plugins/**", "opencode.json", ".pi/**", ".githooks/**",
              ".github/workflows/**", ".gitlab-ci.yml", "CODEOWNERS", ".github/CODEOWNERS"]
_CONFIG_NAME = "agentkit.toml"
_DEFAULT_LOCK = "tests.lock.json"
_DEFAULT_UNFREEZE_LOG = "tests.unfreeze-log.md"
_DEFAULT_CHAOS_LOG = "chaos-log.jsonl"
_DEFAULT_SPECS = "specs"

_PREFIX_WORDS = {"sudo", "env", "command", "builtin", "exec", "nohup", "time", "xargs"}
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_OPERATORS = {";", "&&", "||", "|", "&", "(", ")", "|&", ";;", "&;", "\n"}
_NULL_TARGETS = {"/dev/null", "nul", "$null"}
_UNKNOWN_DIR = re.compile(r"[$%~`]")

_POSIX_WRITERS = {"rm", "rmdir", "mv", "cp", "tee", "truncate", "dd", "touch", "ln", "install",
                  "unlink", "shred", "chmod", "chown", "patch"}
_CMD_WRITERS = {"del", "erase", "rd", "ren", "rename", "move", "copy", "xcopy", "robocopy"}
_PS_WRITERS = {"set-content", "add-content", "out-file", "remove-item", "move-item", "copy-item",
               "new-item", "clear-content", "rename-item",
               "sc", "ac", "ri", "mi", "cpi", "ni", "rni", "clc"}
_WRITERS = _POSIX_WRITERS | _CMD_WRITERS | _PS_WRITERS
_DESTRUCTIVE = {"rm", "rmdir", "rd", "del", "erase", "remove-item", "ri", "mv", "move",
                "move-item", "mi", "shred"}
_GIT_PATH_COMMANDS = {"checkout", "restore", "rm", "mv", "apply", "am", "update-index"}
_GIT_NO_VERIFY = {"commit", "push", "merge", "rebase", "am", "cherry-pick", "revert"}
_GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
_INTERPRETERS = re.compile(r"^(python[0-9.]*|py|node|deno|bun|ruby|perl|php|pwsh|powershell|"
                           r"bash|sh|zsh)$")
_INLINE_FLAGS = {"-c", "-e", "-command", "--eval", "-r"}
_CD = {"cd", "pushd", "set-location", "chdir"}

_RESTORE_HINT = "if it must change, ask the owner; to undo an edit run `agentkit lock restore`"
_OWNER_HINT = "only the owner may do this; ask the owner"


# paths ---------------------------------------------------------------------------------

def _norm(text: str) -> str:
    """Forward slashes, Git-Bash drive paths on Windows (R003-05), no dot segments."""
    p = text.replace("\\", "/")
    if os.name == "nt":
        m = re.match(r"^/([A-Za-z])(/|$)", p)
        if m:
            p = m.group(1).upper() + ":/" + p[m.end():]
    return p


def _is_abs(p: str) -> bool:
    return p.startswith("/") or bool(re.match(r"^[A-Za-z]:/", p))


def _join(base: str, p: str) -> str:
    p = _norm(p)
    full = p if _is_abs(p) else base.rstrip("/") + "/" + p
    drive = ""
    if re.match(r"^[A-Za-z]:", full):
        drive, full = full[:2], full[2:]
    norm = posixpath.normpath(full)
    if norm.startswith("//"):
        norm = "/" + norm.lstrip("/")
    return drive + norm


class _Root:
    def __init__(self, root: Path) -> None:
        self.text = _join("/", str(root)) if os.name != "nt" else _join("", str(root))
        self.key = self.text.casefold().rstrip("/")

    def rel(self, path: str, cwd: str) -> str | None:
        """The repo-relative path ("" for the root), or None outside the repository (R003-04)."""
        if not path:
            return None
        full = _join(cwd, path)
        rel = self._strip(full)
        if rel is None and os.path.isabs(full):
            try:
                rel = self._strip(_join("/", os.path.realpath(full)) if os.name != "nt"
                                  else _join("", os.path.realpath(full)))
            except (OSError, ValueError):
                rel = None
        return rel

    def _strip(self, full: str) -> str | None:
        key = full.casefold().rstrip("/")
        if key == self.key:
            return ""
        if key.startswith(self.key + "/"):
            return full.rstrip("/")[len(self.key) + 1:]
        return None


def _shipped_frozen_globs() -> list[str]:
    from .config import PROFILE_DEFAULTS, _kit_source
    out: list[str] = []
    for path in sorted((_kit_source() / "profiles").glob("*.toml")):
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError):
            continue
        globs = data.get("frozen_globs", PROFILE_DEFAULTS["frozen_globs"])
        if isinstance(globs, list):
            out += [g for g in globs if isinstance(g, str) and g not in out]
    return out or list(PROFILE_DEFAULTS["frozen_globs"])


def _chaos_logs(cfg) -> list[str]:
    """The default chaos log and the configured one (R020-29, R020-42)."""
    logs = [_DEFAULT_CHAOS_LOG]
    try:
        from .chaos import _log_rel_lenient
        rel = _log_rel_lenient(cfg)
    except Exception:  # noqa: BLE001 - fall back to the default path
        rel = _DEFAULT_CHAOS_LOG
    if rel not in logs:
        logs.append(rel)
    return logs


# context -------------------------------------------------------------------------------

class _Context:
    def __init__(self, cfg, cwd: str | None) -> None:
        from .lock import load_lock
        self.root = _Root(cfg.root)
        self.cwd = self._start(cwd)
        frozen = list(load_lock(cfg)["files"])
        self.frozen = {p.casefold(): p for p in frozen}
        self.frozen_names: dict[str, str] = {}
        self.frozen_dirs = {""}
        for p in frozen:
            parts = p.casefold().split("/")
            self.frozen_names.setdefault(parts[-1], p)
            for i in range(1, len(parts)):
                self.frozen_dirs.add("/".join(parts[:i]))
        guard = cfg.guard
        specs = cfg.path("specs").rstrip("/")
        self.kit_files = {cfg.lock_rel.casefold(), cfg.unfreeze_log_rel.casefold(),
                          _CONFIG_NAME}
        self.chaos_logs = _chaos_logs(cfg)
        self.always_deny = [*self.chaos_logs, f"{specs}/*/reviews/**"]
        self.deny_globs = [".agentkit/**", *_strings(guard.get("deny_globs"))]
        self.allow_globs = _STATE_GLOBS + _strings(guard.get("allow_globs"))
        self.ask_globs = _ASK_GLOBS + _strings(guard.get("ask_globs"))
        deny_reads = guard.get("deny_build_output_reads", True)
        self.build_globs = list(cfg.profile.get("build_output_globs") or []) \
            if deny_reads is not False else []
        self.mentions = [cfg.lock_rel.casefold(), cfg.unfreeze_log_rel.casefold(),
                         *(log.casefold() for log in self.chaos_logs)]
        self.reviews_rx = re.compile(re.escape(specs.casefold()) + r"/[^/\s'\"]+/reviews/")

    def _start(self, cwd: str | None) -> str:
        if not cwd:
            return self.root.text
        return _join(self.root.text, cwd)

    # write rules (R003-07 to R003-10) ----------------------------------------------------
    def write(self, rel: str) -> tuple[str, str] | None:
        if rel == "":
            return None
        key = rel.casefold()
        if key in self.frozen:
            return DENY, f"{rel} is a frozen test file; {_RESTORE_HINT}"
        if glob_match(rel, self.always_deny):
            return DENY, f"{rel} is a chaos-mode record written only by agentkit; {_OWNER_HINT}"
        if glob_match(rel, self.allow_globs):
            return None
        if key in self.kit_files or glob_match(rel, self.deny_globs):
            return DENY, f"{rel} is protected by agentkit; {_OWNER_HINT}"
        if glob_match(rel, self.ask_globs):
            return ASK, (f"{rel} configures enforcement (hooks, CI or permissions); "
                         "ask the owner to approve this change")
        return None

    def read(self, rel: str) -> tuple[str, str] | None:
        if rel and self.build_globs and glob_match(rel, self.build_globs):
            return DENY, (f"{rel} is build output; run `agentkit test` for a compact summary "
                          "instead, or ask the owner")
        return None


def _strings(value) -> list[str]:
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


class _Collector:
    def __init__(self) -> None:
        self.verdict = ALLOW
        self.reasons: list[str] = []

    def add(self, found: tuple[str, str] | None) -> None:
        if found is None:
            return
        verdict, reason = found
        if _SEVERITY[verdict] > _SEVERITY[self.verdict]:
            self.verdict = verdict
        if reason not in self.reasons:
            self.reasons.append(reason)

    def decision(self) -> Decision:
        return Decision(self.verdict, self.reasons)


# shell ---------------------------------------------------------------------------------

def _tokens(command: str) -> list[str]:
    """POSIX tokens after `\\` → `/` (R003-26); on unbalanced quotes, a plain split."""
    text = command.replace("\\", "/").replace("\r\n", "\n").replace("\n", " ; ")
    try:
        lex = shlex.shlex(text, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        lex.commenters = ""
        return list(lex)
    except ValueError:
        found = re.findall(r"&&|\|\||\|&|>>|>\||&>|[0-9]*>&?|[;&|()<>]|[^\s;&|()<>]+", text)
        return [t if t in _OPERATORS or ">" in t or t == "<" else t.strip("'\"")
                for t in found if t.strip("'\"") or t in _OPERATORS]


def _segments(tokens: list[str]) -> list[tuple[list[str], list[str]]]:
    """Split at operators; each segment is (words, redirect targets) (R003-16, R003-18)."""
    out: list[tuple[list[str], list[str]]] = []
    words: list[str] = []
    targets: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in _OPERATORS:
            if words or targets:
                out.append((words, targets))
            words, targets = [], []
        elif _is_redirect(tok):
            if i + 1 < len(tokens) and tokens[i + 1] not in _OPERATORS \
                    and not _is_redirect(tokens[i + 1]):
                target = tokens[i + 1]
                dup = tok.endswith("&") and (target.isdigit() or target == "-")
                if ">" in tok and not dup:
                    targets.append(target)
                i += 1
            if words and words[-1].isdigit() and tok.startswith((">", "<")):
                words.pop()  # the N of `N>`
        else:
            words.append(tok)
        i += 1
    if words or targets:
        out.append((words, targets))
    return out


def _is_redirect(tok: str) -> bool:
    return bool(re.fullmatch(r"[0-9]*(?:&?>>?\|?|>&|<|<<|<<<|<&)", tok))


def _command_name(word: str) -> str:
    name = word.rsplit("/", 1)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def _strip_prefix(words: list[str]) -> list[str]:
    i = 0
    while i < len(words):
        w = words[i]
        if _ASSIGNMENT.match(w) or _command_name(w) in _PREFIX_WORDS:
            i += 1
        else:
            break
    return words[i:]


def _args(words: list[str]) -> list[str]:
    """Non-flag arguments, plus the value of `--opt=value` and `key=value` (R003-19)."""
    out = []
    for w in words:
        if w == "--" or not w:
            continue
        if w.startswith("-"):
            if "=" in w:
                out.append(w.split("=", 1)[1])
            continue
        out.append(w)
        if "=" in w:
            out.append(w.split("=", 1)[1])
    return out


class _Shell:
    def __init__(self, ctx: _Context, out: _Collector) -> None:
        self.ctx = ctx
        self.out = out
        self.cwd: str | None = ctx.cwd
        self.stack: list[str | None] = []

    def run(self, command: str) -> None:
        tokens = _tokens(command)
        self._forbidden_kit(command, tokens)
        for words, targets in _segments(tokens):
            for target in targets:
                if target.casefold() not in _NULL_TARGETS:
                    self.write_arg(target, False, f"redirection > {target}")
            words = _strip_prefix(words)
            if words:
                self.segment(words, " ".join(words))

    def deny(self, reason: str) -> None:
        self.out.add((DENY, reason))

    # R003-13 ---------------------------------------------------------------------------
    def _forbidden_kit(self, command: str, tokens: list[str]) -> None:
        low = [t.lower() for t in tokens]
        if not any("agentkit" in t for t in low):
            return
        pairs = set(zip(low, low[1:]))
        if ("lock", "unfreeze") in pairs:
            self.deny(f"`{command}`: lock unfreeze is for the owner only; {_OWNER_HINT}")
        if ("lock", "freeze") in pairs and "--force" in low:
            self.deny(f"`{command}`: a forced freeze is for the owner only; {_OWNER_HINT}")
        if ("chaos", "clear") in pairs:
            self.deny(f"`{command}`: chaos clear is for the owner only; {_OWNER_HINT}")

    # one segment -----------------------------------------------------------------------
    def segment(self, words: list[str], text: str) -> None:
        name = _command_name(words[0])
        rest = words[1:]
        if name in _CD:
            self.change_dir(name, rest)
        elif name == "popd":
            self.cwd = self.stack.pop() if self.stack else self.cwd
        elif name == "git":
            self.git(rest, text)
        elif name in ("sed", "perl") and any(self._in_place(name, w) for w in rest):
            for arg in _args(rest):
                self.write_arg(arg, False, text)
        elif name == "find":
            self.find(rest, text)
        elif name in _WRITERS:
            for arg in _args(rest):
                self.write_arg(arg, name in _DESTRUCTIVE, text)
        if _INTERPRETERS.match(name):
            self.interpreter(name, rest, text)

    def change_dir(self, name: str, rest: list[str]) -> None:
        targets = [w for w in rest if not (w.startswith("-") and w != "-")
                   and w.lower() != "/d"]
        if name == "pushd":
            self.stack.append(self.cwd)
        target = targets[0] if targets else None
        if self.cwd is None or target is None or target == "-" or _UNKNOWN_DIR.search(target) \
                or "$(" in target:
            self.cwd = None  # R003-32
        else:
            self.cwd = _join(self.cwd, target)

    @staticmethod
    def _in_place(name: str, word: str) -> bool:
        if name == "sed" and word.startswith("--in-place"):
            return True
        return bool(re.match(r"^-[A-Za-z]*i", word)) and not word.startswith("--")

    def find(self, rest: list[str], text: str) -> None:
        actions = {"-delete", "-exec", "-execdir"}
        if not actions & set(rest):
            return
        starts = []
        for w in rest:
            if w.startswith("-") or w in ("(", "!"):
                break
            starts.append(w)
        for arg in starts or ["."]:
            self.write_arg(arg, "-delete" in rest, text)

    def git(self, rest: list[str], text: str) -> None:
        if any("core.hookspath" in w.lower() for w in rest):
            self.deny(f"`{text}` changes core.hooksPath and would bypass the hooks; "
                      f"{_OWNER_HINT}")
        i = 0
        while i < len(rest) and rest[i].startswith("-"):
            i += 2 if rest[i] in _GIT_VALUE_OPTIONS else 1
        if i >= len(rest):
            return
        sub, args = rest[i], rest[i + 1:]
        if sub in _GIT_NO_VERIFY and "--no-verify" in args:
            self.deny(f"`{text}` uses --no-verify and skips the git hooks; run it without "
                      f"--no-verify, or ask the owner")
        if sub == "commit" and any(self._short_n(w) for w in args):
            self.deny(f"`{text}` uses -n (--no-verify) and skips the git hooks; run it without "
                      f"-n, or ask the owner")
        if sub == "update-index" and ({"--assume-unchanged", "--skip-worktree"} & set(args)):
            self.deny(f"`{text}` hides changes from git; {_OWNER_HINT}")
        if sub in _GIT_PATH_COMMANDS:
            for arg in _args(args):
                self.write_arg(arg, sub in ("rm", "mv"), text)

    @staticmethod
    def _short_n(word: str) -> bool:
        if not re.match(r"^-[A-Za-z]+$", word):
            return False
        for ch in word[1:]:
            if ch == "n":
                return True
            if ch in "mFcCt":
                return False
        return False

    def interpreter(self, name: str, rest: list[str], text: str) -> None:
        for i, w in enumerate(rest):
            low = w.lower()
            inline = low in _INLINE_FLAGS or (name in ("perl", "ruby")
                                              and re.match(r"^-[a-z]*e$", low))
            if inline:
                self.inline_script(" ".join(rest[i + 1:]), text)
                return

    def inline_script(self, script: str, text: str) -> None:
        low = script.casefold()
        hits = [p for k, p in self.ctx.frozen.items() if k in low]
        hits += [p for k, p in self.ctx.frozen_names.items() if len(k) > 4 and k in low]
        hits += [m for m in self.ctx.mentions if m in low]
        if self.ctx.reviews_rx.search(low):
            hits.append("a stored review")
        if hits:
            self.deny(f"`{text}` runs an inline script that mentions {hits[0]}; "
                      f"{_RESTORE_HINT}")

    # write arguments (R003-17 to R003-24) ----------------------------------------------
    def write_arg(self, arg: str, destructive: bool, text: str) -> None:
        arg = arg.strip()
        if not arg or arg.casefold() in _NULL_TARGETS:
            return
        ctx = self.ctx
        p = _norm(arg)
        if any(c in p for c in "*?["):
            self.glob_arg(p, text)
            return
        if self.cwd is None and not _is_abs(p):
            if "/" not in p and p.casefold() in ctx.frozen_names:
                self.deny(f"`{text}` may touch the frozen test file "
                          f"{ctx.frozen_names[p.casefold()]} (working directory unknown); "
                          f"{_RESTORE_HINT}")
            return
        rel = ctx.root.rel(p, self.cwd or ctx.root.text)
        if rel is None:
            return
        found = ctx.write(rel)
        if found is not None:
            verdict, reason = found
            self.out.add((verdict, f"{reason} (in `{text}`)"))
        if destructive and rel.casefold() in ctx.frozen_dirs:
            shown = rel or "the repository root"
            self.deny(f"`{text}` would remove {shown}, which contains frozen test files; "
                      f"{_RESTORE_HINT}")

    def glob_arg(self, pattern: str, text: str) -> None:
        ctx = self.ctx
        if self.cwd is None and not _is_abs(pattern):
            if "/" in pattern:
                return
            rx = glob_to_regex(pattern)
            hits = [p for k, p in ctx.frozen_names.items() if rx.fullmatch(k)]
        else:
            rel = ctx.root.rel(pattern, self.cwd or ctx.root.text)
            if not rel:
                return
            rx = glob_to_regex(rel)
            hits = [p for p in ctx.frozen.values() if rx.fullmatch(p)]
        if hits:
            self.deny(f"`{text}`: the glob {pattern} matches the frozen test file {hits[0]}; "
                      f"{_RESTORE_HINT}")


# evaluate ------------------------------------------------------------------------------

def _evaluate(cfg, actions: list, cwd: str | None) -> Decision:
    ctx = _Context(cfg, cwd)
    out = _Collector()
    for action in actions:
        if isinstance(action, WriteAction):
            for path in action.paths:
                rel = ctx.root.rel(path, ctx.cwd)
                if rel is not None:
                    out.add(ctx.write(rel))
        elif isinstance(action, ReadAction):
            for path in action.paths:
                rel = ctx.root.rel(path, ctx.cwd)
                if rel is not None:
                    out.add(ctx.read(rel))
        elif isinstance(action, ShellAction):
            _Shell(ctx, out).run(action.command)
        else:
            raise TypeError(f"not a guard action: {action!r}")
    return out.decision()


def _degraded(cfg, actions: list, cwd: str | None, message: str) -> Decision:
    """Fail closed for test and kit files, open for the rest (R003-27, R003-29)."""
    reason = (f"agentkit guard error ({message}): writes to test files are refused until the "
              "guard is fixed")
    try:
        if cfg is not None:
            root = Path(cfg.root)
        else:
            from .config import find_root
            root = find_root(Path(cwd) if cwd else None)
        globs: list[str] = []
        if cfg is not None:
            try:
                globs = list(cfg.frozen_globs)
            except Exception:  # noqa: BLE001
                globs = []
        if not globs:
            globs = _shipped_frozen_globs()
        lock, log, specs = _DEFAULT_LOCK, _DEFAULT_UNFREEZE_LOG, _DEFAULT_SPECS
        logs = [_DEFAULT_CHAOS_LOG]
        if cfg is not None:
            try:
                lock, log, specs = cfg.lock_rel, cfg.unfreeze_log_rel, cfg.path("specs")
            except Exception:  # noqa: BLE001
                pass
            logs = _chaos_logs(cfg)
        protected = [*globs, lock, log, _CONFIG_NAME, ".agentkit/**", *logs,
                     specs.rstrip("/") + "/*/reviews/**"]
        r = _Root(root) if root is not None else None
    except Exception:  # noqa: BLE001 - nothing can be classified
        r, protected = None, []
    base = r.text if r is not None else ""
    start = _join(base, cwd) if (cwd and r is not None) else base
    denied = False
    allowed = False
    for action in actions:
        if isinstance(action, WriteAction) and r is not None:
            for path in action.paths:
                rel = r.rel(path, start)
                if rel and glob_match(rel, protected):
                    denied = True
                else:
                    allowed = True
        else:
            allowed = True
    if allowed:
        print(f"agentkit guard error (allowing): {message}", file=sys.stderr)
    return Decision(DENY, [reason]) if denied else Decision(ALLOW, [])


def evaluate(cfg, actions: list, cwd: str | None = None) -> Decision:
    """Judge neutral actions (R003-01, R003-02). `cfg` is None when the configuration did not
    load; the guard then runs in degraded mode (R003-29)."""
    if cfg is None:
        return _degraded(None, actions, cwd, f"{_CONFIG_NAME} did not load")
    try:
        return _evaluate(cfg, actions, cwd)
    except Exception as exc:  # noqa: BLE001 - degraded mode (R003-27)
        return _degraded(cfg, actions, cwd, str(exc) or type(exc).__name__)
