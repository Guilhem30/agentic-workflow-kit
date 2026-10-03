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

_PREFIX_WORDS = {"sudo", "env", "command", "builtin", "exec", "nohup", "time", "xargs",
                 "nice", "timeout", "coproc"}
# Shell keywords that start a segment without being the command (`if x; then rm y; fi`).
_KEYWORDS = {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "}"}
# Options of prefix words that take a value (`sudo -u bob rm x`).
_PREFIX_VALUE_OPTIONS = {"sudo": {"-u", "-g", "-C", "-h", "-p", "-r", "-t", "-U", "--user",
                                  "--group", "--host", "--prompt", "--close-from"},
                         "env": {"-u", "-C", "-S", "--unset", "--chdir", "--split-string"},
                         "xargs": {"-I", "-n", "-P", "-d", "-L", "-s", "-a", "-E", "-i",
                                   "--max-args", "--max-procs", "--delimiter", "--max-lines",
                                   "--max-chars", "--arg-file", "--eof", "--replace"},
                         "time": {"-f", "-o", "--format", "--output"},
                         "exec": {"-a"},
                         "nice": {"-n", "--adjustment"},
                         "timeout": {"-s", "-k", "--signal", "--kill-after"}}
# Launchers that take a leading non-option argument before the command (`timeout 10 rm x`).
_PREFIX_WITH_ARGUMENT = {"timeout"}
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_OPERATORS = {";", "&&", "||", "|", "&", "(", ")", "|&", ";;", "&;"}
_PUNCT_RUN = re.compile(r"&>>|&>|>>|>\||>&|<<<|<<|<&|&&|\|\||\|&|;;|[;&|()<>]")
_NULL_TARGETS = {"/dev/null", "nul", "$null"}
_UNKNOWN_DIR = re.compile(r"[$%~`]")

_POSIX_WRITERS = {"rm", "rmdir", "mv", "cp", "tee", "truncate", "dd", "touch", "ln", "install",
                  "unlink", "shred", "chmod", "chown", "patch"}
_CMD_WRITERS = {"del", "erase", "rd", "ren", "rename", "move", "copy", "xcopy", "robocopy"}
_PS_WRITERS = {"set-content", "add-content", "out-file", "remove-item", "move-item", "copy-item",
               "new-item", "clear-content", "rename-item",
               "sc", "ac", "ri", "mi", "cpi", "ni", "rni", "clc"}
_WRITERS = _POSIX_WRITERS | _CMD_WRITERS | _PS_WRITERS
_COPIERS = {"cp", "mv", "install", "ln", "copy", "move", "xcopy", "robocopy", "copy-item", "cpi",
            "move-item", "mi"}
_DESTRUCTIVE = {"rm", "rmdir", "rd", "del", "erase", "remove-item", "ri", "mv", "move",
                "move-item", "mi", "shred"}
_GIT_PATH_COMMANDS = {"checkout", "restore", "rm", "mv", "apply", "am", "update-index"}
_GIT_NO_VERIFY = {"commit", "push", "merge", "rebase", "am", "cherry-pick", "revert"}
_GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
_INTERPRETERS = re.compile(r"^(python[0-9.]*|py|node|deno|bun|ruby|perl|php|pwsh|powershell|"
                           r"bash|sh|zsh)$")
_SHELLS = {"bash", "sh", "zsh", "pwsh", "powershell"}
# Interpreter options whose value is the next word (`python -W ignore -c …`).
_VALUE_OPTIONS = {"python": {"-W", "-X", "--check-hash-based-pycs"},
                  "node": {"-r", "--require", "--import", "-C", "--conditions", "--loader",
                           "--input-type"},
                  "ruby": {"-r", "-I", "-C", "-E", "-F"},
                  "perl": {"-I", "-M", "-m", "-x", "-C"},
                  "php": {"-d", "-c", "-z"},
                  "shell": {"-o", "+o", "-O", "+O", "--rcfile", "--init-file"}}


def _family(name: str) -> str:
    if name.startswith("python") or name == "py":
        return "python"
    if name in ("node", "deno", "bun"):
        return "node"
    if name in ("pwsh", "powershell"):
        return "pwsh"
    if name in ("bash", "sh", "zsh"):
        return "shell"
    return name


def _inline(name: str, word: str) -> tuple[str | None, bool] | None:
    """When `word` starts an inline script for `name`: (script attached to the flag or None,
    whether the script is every following word). None otherwise."""
    family = _family(name)
    low = word.lower()
    if family == "python":
        m = re.fullmatch(r"-[A-Za-z]*c(.*)", word, re.S)
    elif family == "node":
        if name == "deno" and word == "eval":
            return None, True
        if low in ("-e", "--eval", "-p", "--print"):
            return None, False
        m = re.fullmatch(r"(?:--eval|--print)=(.*)|-[ep](.+)", word, re.S)
        if m:
            return next(g for g in m.groups() if g is not None), False
        return None
    elif family in ("perl", "ruby"):
        flags = "eE" if family == "perl" else "e"
        m = re.fullmatch(rf"-[a-zA-Z]*?[{flags}](.*)", word, re.S) if not word.startswith(
            ("-I", "-M", "-C", "-r", "-E" if family == "ruby" else "-I")) else None
    elif family == "php":
        m = re.fullmatch(r"-r(.*)", word, re.S)
    elif family == "pwsh":
        if low == "-c" or (len(low) >= 4 and "-command".startswith(low)) \
                or low == "-commandwithargs":
            return None, True
        return None
    else:  # POSIX shells: -c, alone or in a cluster such as -ec
        if re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", word) and not word.startswith("--"):
            return None, False
        return None
    if not m:
        return None
    return (m.group(1) or None), False


_NESTING_LIMIT = 4


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


def _absolute(path: str) -> str:
    return _join("" if os.name == "nt" else "/", path)


class _Root:
    def __init__(self, root: Path) -> None:
        self.text = _absolute(str(root)).rstrip("/") or "/"
        self.key = self.text.casefold()

    def rel(self, path: str, cwd: str) -> str | None:
        """The repo-relative path ("" for the root), or None outside the repository (R003-04)."""
        if not path:
            return None
        full = _join(cwd, path)
        rel = self._strip(full)
        if rel is None and os.path.isabs(full):
            try:
                rel = self._strip(_absolute(os.path.realpath(full)))
            except (OSError, ValueError):
                rel = None
        return rel

    def is_ancestor(self, full: str) -> bool:
        key = (full.rstrip("/") or "/").casefold()
        return key == "/" or self.key.startswith(key + "/")

    def _strip(self, full: str) -> str | None:
        # Slice by the original root's length: casefold can change it (ß → ss).
        full = full.rstrip("/") or "/"
        n = len(self.text)
        if full[:n].casefold() != self.key:
            return None
        if len(full) == n:
            return ""
        if self.text == "/":
            return full[1:]
        return full[n + 1:] if full[n] == "/" else None


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
        self.deny_globs = [".agentkit", ".agentkit/**", *_strings(guard.get("deny_globs"))]
        # Directories whose removal takes kit files with them (R003-09).
        kit_paths = [cfg.lock_rel, cfg.unfreeze_log_rel, *self.chaos_logs]
        self.protected_dirs = {".agentkit", specs.casefold()}
        for path in kit_paths:
            parts = path.casefold().split("/")
            self.protected_dirs.update("/".join(parts[:i]) for i in range(1, len(parts)))
        self.protected_dir_globs = [f"{specs}/*", f"{specs}/*/reviews"]
        self.kit_names = sorted({*self.kit_files, *(log.casefold() for log in self.chaos_logs)})
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

    def holds_protected(self, rel: str) -> str | None:
        """What a removal of the directory `rel` would take with it (R003-09, R003-23)."""
        key = rel.casefold()
        if key in self.frozen_dirs:
            return "frozen test files"
        if key in self.protected_dirs or glob_match(rel, self.protected_dir_globs):
            return "files protected by agentkit"
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
        raw = list(lex)
    except ValueError:
        found = re.findall(r"[0-9]*(?:&>>|&>|>>|>\||>&|>)|<<<|<<|<&|&&|\|\||\|&|;;|[;&|()<]|"
                           r"[^\s;&|()<>]+", text)
        return [t if t in _OPERATORS or _is_redirect(t) else t.strip("'\"")
                for t in found if t.strip("'\"")]
    out: list[str] = []
    for tok in raw:
        if tok and all(c in "();<>|&" for c in tok):
            out += _PUNCT_RUN.findall(tok)  # `&&(` and `);>` are several operators
        else:
            out.append(tok)
    return out


_Segment = tuple[list[str], list[str], str]


def _segments(tokens: list[str]) -> list[_Segment | str]:
    """Split at operators (R003-16). Items are (words, redirect targets, next operator)
    (R003-18), or "(" and ")" so that a subshell's `cd` does not leak out."""
    out: list[_Segment | str] = []
    words: list[str] = []
    targets: list[str] = []

    def flush(after: str = "") -> None:
        nonlocal words, targets
        if words or targets:
            out.append((words, targets, after))
        words, targets = [], []

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in _OPERATORS:
            flush(tok)
            if tok in ("(", ")"):
                out.append(tok)
        elif _is_redirect(tok):
            if words and words[-1].isdigit():
                words.pop()  # the N of `N >`
            if i + 1 < len(tokens) and tokens[i + 1] not in _OPERATORS \
                    and not _is_redirect(tokens[i + 1]):
                target = tokens[i + 1]
                dup = tok.endswith("&") and (target.isdigit() or target == "-")
                if ">" in tok and not dup:
                    targets.append(target)
                i += 1
        else:
            words.append(tok)
        i += 1
    flush()
    return out


def _is_redirect(tok: str) -> bool:
    return bool(re.fullmatch(r"[0-9]*(?:&>>|&>|>>|>\||>&|>|<<<|<<|<&|<)", tok))


def _command_name(word: str) -> str:
    name = word.rsplit("/", 1)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def _strip_prefix(words: list[str]) -> list[str]:
    """Skip assignments, prefix words with their options, and shell keywords (R003-16)."""
    i = 0
    while i < len(words):
        w = words[i]
        name = _command_name(w)
        if _ASSIGNMENT.match(w) or w in _KEYWORDS:
            i += 1
        elif w == "function":
            i += 2  # `function NAME { body; }`: the body follows
        elif name in _PREFIX_WORDS:
            i += 1
            takes_value = _PREFIX_VALUE_OPTIONS.get(name, set())
            while i < len(words) and words[i].startswith("-") and len(words[i]) > 1:
                i += 2 if words[i] in takes_value else 1
            if name in _PREFIX_WITH_ARGUMENT and i < len(words):
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


def _abbrev(word: str, option: str, shortest: int) -> bool:
    """`word` is `option` or an abbreviation of it that git or argparse would accept."""
    return len(word) >= shortest and option.startswith(word)


_BRACES = re.compile(r"\{([^{}]*,[^{}]*)\}")


def _braces(word: str, limit: int = 64) -> list[str]:
    """Simple brace expansion: `a/{b,c}.kt` → `a/b.kt`, `a/c.kt`."""
    out, todo = [], [word]
    while todo and len(out) + len(todo) <= limit:
        w = todo.pop()
        m = _BRACES.search(w)
        if not m:
            out.append(w)
            continue
        todo += [w[:m.start()] + alt + w[m.end():] for alt in m.group(1).split(",")]
    return out + todo


def _copy_args_posix(rest: list[str]) -> tuple[str | None, list[str], bool]:
    """cp/mv/install/ln and cmd.exe copiers: (target directory, sources, recursive)."""
    dest, sources, recursive = None, [], False
    i = 0
    while i < len(rest):
        w = rest[i]
        if w.startswith("--"):
            if w == "--target-directory" and i + 1 < len(rest):
                dest = rest[i + 1]
                i += 1
            elif w.startswith("--target-directory="):
                dest = w.split("=", 1)[1]
            elif w in ("--recursive", "--archive"):
                recursive = True
        elif w.startswith("-") and len(w) > 1:
            flags = w[1:]
            if "t" in flags:  # -t DIR, -tDIR, -vt DIR
                value = flags[flags.index("t") + 1:]
                if value:
                    dest = value
                elif i + 1 < len(rest):
                    dest = rest[i + 1]
                    i += 1
                flags = flags[:flags.index("t")]
            recursive = recursive or any(c in flags for c in "rRa")
        elif w.lower() in ("/s", "/e"):
            recursive = True
        else:
            sources.append(w)
        i += 1
    return dest, sources, recursive


def _copy_args_cmd(name: str, rest: list[str]) -> tuple[str | None, list[str], bool]:
    """copy/move/xcopy/robocopy: /X[:v] switches anywhere; SRC then DEST; robocopy's later
    arguments are file names, which land in DEST."""
    positional = [w for w in rest if not re.fullmatch(r"/[A-Za-z]{1,8}(?::.*)?|/[0-9-]+", w)]
    if len(positional) < 2:
        return None, positional, False
    if name == "robocopy":
        return positional[1], positional[2:], False
    return positional[-1], positional[:-1], False


_PS_SOURCE_PARAMS = ("-path", "-literalpath")
_PS_VALUE_PARAMS = ("-filter", "-include", "-exclude", "-credential", "-fromsession",
                    "-tosession")


def _ps_param(word: str, names) -> str | None:
    """The PowerShell parameter `word` abbreviates, among `names`."""
    low = word.lower()
    hits = [n for n in names if len(low) >= 2 and n.startswith(low)]
    return hits[0] if len(hits) == 1 else None


def _copy_args_powershell(rest: list[str]) -> tuple[str | None, list[str], bool]:
    """Copy-Item/Move-Item: (destination, sources, recursive)."""
    dest, sources, recursive = None, [], False
    i = 0
    while i < len(rest):
        w = rest[i]
        if w.startswith("-") and len(w) > 1:
            name, _, attached = w.partition(":")
            if _ps_param(name, ("-destination",)):
                if attached:
                    dest = attached
                elif i + 1 < len(rest):
                    dest = rest[i + 1]
                    i += 1
            elif _ps_param(name, _PS_SOURCE_PARAMS):
                if attached:
                    sources.append(attached)
                elif i + 1 < len(rest):
                    sources.append(rest[i + 1])
                    i += 1
            elif _ps_param(name, _PS_VALUE_PARAMS):
                i += 0 if attached else 1
            elif _ps_param(name, ("-recurse",)):
                recursive = True
        else:
            sources.append(w)
        i += 1
    return dest, sources, recursive


def _unknown_dir(target: str) -> bool:
    return target == "-" or bool(_UNKNOWN_DIR.search(target)) or "$(" in target


class _Shell:
    def __init__(self, ctx: _Context, out: _Collector, cwd: str | None, depth: int = 0) -> None:
        self.ctx = ctx
        self.out = out
        self.cwd: str | None = cwd
        self.stack: list[str | None] = []
        self.depth = depth

    def run(self, command: str) -> None:
        tokens = _tokens(command)
        self._forbidden_kit(command, tokens)
        subshells: list[str | None] = []
        for item in _segments(tokens):
            if item == "(":
                subshells.append(self.cwd)
                continue
            if item == ")":
                if subshells:
                    self.cwd = subshells.pop()
                continue
            words, targets, after = item
            for target in targets:
                if target.casefold() not in _NULL_TARGETS:
                    self.write_arg(target, False, f"redirection > {target}")
            if any("core.hookspath" in w.lower() for w in words) and any(
                    _command_name(w) == "git" for w in words):
                self.deny(f"`{' '.join(words)}` changes core.hooksPath and would bypass the "
                          f"hooks; {_OWNER_HINT}")
            self._split_string(words)
            words = _strip_prefix(words)
            if words:
                self.segment(words, " ".join(words))
                if _command_name(words[0]) in _CD and after in ("||", "|", "&", "|&"):
                    self.cwd = None  # the change may or may not have taken effect

    def deny(self, reason: str) -> None:
        self.out.add((DENY, reason))

    def _split_string(self, words: list[str]) -> None:
        """`env -S 'cmd args'` runs its value as a command line."""
        if not any(_command_name(w) == "env" for w in words):
            return
        for i, w in enumerate(words[:-1]):
            if w in ("-S", "--split-string"):
                self.nested(words[i + 1])

    def nested(self, script: str) -> None:
        """Analyse a script run by a shell (`bash -c`, `eval`) as a command of its own."""
        if self.depth < _NESTING_LIMIT and script.strip():
            _Shell(self.ctx, self.out, self.cwd, self.depth + 1).run(script)

    # R003-13 ---------------------------------------------------------------------------
    def _forbidden_kit(self, command: str, tokens: list[str]) -> None:
        """R003-13 on the whole text, quotes and all, so that a command hidden in a string
        (`python -c "os.system('agentkit lock unfreeze …')"`) counts too."""
        text = re.sub(r"\s+", " ", re.sub(r"['\"`\\]", "", command)).lower()
        if "agentkit" not in text:
            return
        words = text.split()
        if re.search(r"\block unfreeze\b", text):
            self.deny(f"`{command}`: lock unfreeze is for the owner only; {_OWNER_HINT}")
        if re.search(r"\block freeze\b", text) and any(_abbrev(t, "--force", 3) for t in words):
            self.deny(f"`{command}`: a forced freeze is for the owner only; {_OWNER_HINT}")
        if re.search(r"\bchaos clear\b", text):
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
        elif name == "eval":
            self.nested(" ".join(rest))
        elif name == "cmd" and any(w.lower() in ("/c", "/k") for w in rest):
            at = next(i for i, w in enumerate(rest) if w.lower() in ("/c", "/k"))
            self.nested(" ".join(rest[at + 1:]))
        elif name == "su":
            for i, w in enumerate(rest):
                if w in ("-c", "--command") and i + 1 < len(rest):
                    self.nested(rest[i + 1])
                elif w.startswith("--command="):
                    self.nested(w.split("=", 1)[1])
        elif name in ("sed", "perl") and any(self._in_place(name, w) for w in rest):
            for arg in _args(rest):
                self.write_arg(arg, False, text)
        elif name == "find":
            self.find(rest, text)
        elif name in _WRITERS:
            for arg in _args(rest):
                self.write_arg(arg, name in _DESTRUCTIVE, text)
            if name in _COPIERS:
                self.copy_into(name, rest, text)
        if _INTERPRETERS.match(name):
            self.interpreter(name, rest, text)

    def change_dir(self, name: str, rest: list[str]) -> None:
        targets = [w for w in rest if not (w.startswith("-") and w != "-")
                   and w.lower() != "/d"]
        if name == "pushd":
            self.stack.append(self.cwd)
        target = targets[0] if targets else None
        if self.cwd is None or target is None or _unknown_dir(target):
            self.cwd = None  # R003-32
        else:
            self.cwd = _join(self.cwd, target)

    @staticmethod
    def _in_place(name: str, word: str) -> bool:
        if word.startswith("--"):
            return name == "sed" and word.startswith("--in-place")
        if name == "perl":
            return bool(re.match(r"^-[a-z]*i", word))  # not -I or -M
        return bool(re.match(r"^-[A-Za-z]*i", word))

    def find(self, rest: list[str], text: str) -> None:
        actions = {"-delete", "-exec", "-execdir", "-ok", "-okdir"}
        if not actions & set(rest):
            return
        destructive = "-delete" in rest
        for i, w in enumerate(rest):
            if w in ("-exec", "-execdir", "-ok", "-okdir"):
                cmd = []
                for x in rest[i + 1:]:
                    if x in (";", "+"):
                        break
                    cmd.append(x)
                cmd = [x for x in cmd if x != "{}"]
                if cmd:
                    sub = _command_name(cmd[0])
                    if sub in _WRITERS or (sub in ("sed", "perl") and any(
                            self._in_place(sub, x) for x in cmd[1:])):
                        destructive = True  # it writes to every file found
                    self.segment(cmd, " ".join(cmd))
        starts = []
        for w in rest:
            if w.startswith("-") or w in ("(", "!"):
                break
            starts.append(w)
        for arg in starts or ["."]:
            self.write_arg(arg, destructive, text)

    def git(self, rest: list[str], text: str) -> None:
        cwd = self.cwd
        i = 0
        while i < len(rest) and rest[i].startswith("-"):
            target = None
            if rest[i] in ("-C", "--work-tree") and i + 1 < len(rest):
                target = rest[i + 1]
            elif rest[i].startswith("--work-tree="):
                target = rest[i].split("=", 1)[1]
            if target is not None:
                cwd = None if cwd is None or _unknown_dir(target) else _join(cwd, target)
            i += 2 if rest[i] in _GIT_VALUE_OPTIONS else 1
        if i >= len(rest):
            return
        sub, args = rest[i], rest[i + 1:]
        if sub in _GIT_NO_VERIFY and any(_abbrev(a, "--no-verify", 6) for a in args):
            self.deny(f"`{text}` uses --no-verify and skips the git hooks; run it without "
                      f"--no-verify, or ask the owner")
        if sub == "commit" and any(self._short_n(w) for w in args):
            self.deny(f"`{text}` uses -n (--no-verify) and skips the git hooks; run it without "
                      f"-n, or ask the owner")
        if sub == "update-index" and ({"--assume-unchanged", "--skip-worktree"} & set(args)):
            self.deny(f"`{text}` hides changes from git; {_OWNER_HINT}")
        if sub in _GIT_PATH_COMMANDS:
            saved, self.cwd = self.cwd, cwd
            try:
                for arg in _args(args):
                    self.write_arg(arg, sub in ("rm", "mv"), text)
            finally:
                self.cwd = saved

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
        """R003-21: options before the script or module name, including their values."""
        values = _VALUE_OPTIONS.get(_family(name), set())
        i = 0
        while i < len(rest):
            w = rest[i]
            found = _inline(name, w)
            if found is not None:
                attached, whole = found
                if attached is not None:
                    script = attached
                elif whole:
                    script = " ".join(rest[i + 1:])
                else:
                    script = rest[i + 1] if i + 1 < len(rest) else ""
                self.inline_script(script, text)
                if name in _SHELLS:
                    self.nested(script)
                return
            if _family(name) == "pwsh":
                if w.lower() in ("-file", "-f"):
                    return
                i += 1
                continue  # PowerShell options come in any order: look at every word
            if w == "-m" or not w.startswith(("-", "+")):
                return  # a module or a script file: the rest are its arguments
            i += 2 if w in values else 1

    def inline_script(self, script: str, text: str) -> None:
        low = script.replace("\\", "/").casefold()
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
        expanded = _braces(arg.strip())
        if len(expanded) > 1:
            for one in expanded:
                self.write_arg(one, destructive, text)
            return
        arg = arg.strip()
        if not arg or arg.casefold() in _NULL_TARGETS:
            return
        ctx = self.ctx
        p = _norm(arg)
        if any(c in p for c in "*?["):
            self.glob_arg(p, destructive, text)
            return
        if self.cwd is None and not _is_abs(p):
            if "/" not in p and p.casefold() in ctx.frozen_names:
                self.deny(f"`{text}` may touch the frozen test file "
                          f"{ctx.frozen_names[p.casefold()]} (working directory unknown); "
                          f"{_RESTORE_HINT}")
            return
        rel = ctx.root.rel(p, self.cwd or ctx.root.text)
        if rel is None:
            if destructive and ctx.root.is_ancestor(_join(self.cwd or ctx.root.text, p)):
                self.deny(f"`{text}` would remove the repository with its frozen test files; "
                          f"{_RESTORE_HINT}")
            return
        found = ctx.write(rel)
        if found is not None:
            verdict, reason = found
            self.out.add((verdict, f"{reason} (in `{text}`)"))
        if destructive:
            held = ctx.holds_protected(rel)
            if held:
                shown = rel or "the repository root"
                self.deny(f"`{text}` would remove {shown}, which contains {held}; "
                          f"{_RESTORE_HINT}")

    def copy_into(self, name: str, rest: list[str], text: str) -> None:
        """`cp SRC… DIR`, `cp -t DIR SRC…`, `Copy-Item SRC -Destination DIR`: the file that
        lands in DIR is a write too."""
        if name in _PS_WRITERS or any(
                _ps_param(w.partition(":")[0], ("-destination", *_PS_SOURCE_PARAMS))
                for w in rest if w.startswith("-")):  # `cp` and `copy` alias Copy-Item
            dest, sources, recursive = _copy_args_powershell(rest)
        elif name in ("xcopy", "robocopy", "copy", "move"):
            dest, sources, recursive = _copy_args_cmd(name, rest)
        else:
            dest, sources, recursive = _copy_args_posix(rest)
        if dest is None and len(sources) >= 2:
            dest = sources.pop()
        if dest is None:
            return
        if name in ("xcopy", "robocopy"):
            recursive = True  # they copy a directory's contents into the destination
            if self.cwd is not None or _is_abs(_norm(dest)):
                dest_rel = self.ctx.root.rel(dest, self.cwd or self.ctx.root.text)
                if dest_rel is not None and self.ctx.holds_protected(dest_rel):
                    self.deny(f"`{text}` copies into {dest_rel or 'the repository root'}, "
                              f"which contains {self.ctx.holds_protected(dest_rel)}; "
                              f"{_RESTORE_HINT}")
        if self.cwd is None and not _is_abs(_norm(dest)):
            for src in sources:  # unknown directory: only basenames can be compared (R003-24)
                name = _norm(src).rstrip("/").rsplit("/", 1)[-1]
                if name.casefold() in self.ctx.frozen_names:
                    self.deny(f"`{text}` may overwrite the frozen test file "
                              f"{self.ctx.frozen_names[name.casefold()]} (working directory "
                              f"unknown); {_RESTORE_HINT}")
            return
        full = _join(self.cwd, dest)
        rel = self.ctx.root.rel(full, self.cwd)
        if rel is None:
            return
        is_dir = dest.endswith("/") or (Path(self.ctx.root.text) / rel).is_dir()
        if not is_dir:
            return
        for src in sources:
            name = _norm(src).rstrip("/").rsplit("/", 1)[-1]
            if name and any(c in name for c in "*?["):
                self.glob_into(rel, name, text)
            elif name:
                landed = f"{full}/{name}"
                self.write_arg(landed, False, text)
                landed_rel = self.ctx.root.rel(landed, self.cwd)
                if recursive and landed_rel is not None and self.ctx.holds_protected(landed_rel):
                    self.deny(f"`{text}` would copy over {landed_rel}, which contains "
                              f"{self.ctx.holds_protected(landed_rel)}; {_RESTORE_HINT}")

    def glob_into(self, dest_rel: str, name: str, text: str) -> None:
        """A glob source copied into `dest_rel`: deny when it could land on a frozen file."""
        rx = glob_to_regex(name)
        prefix = (dest_rel.casefold() + "/") if dest_rel else ""
        for key, path in self.ctx.frozen.items():
            if key.startswith(prefix):
                first = key[len(prefix):].split("/", 1)[0]
                if rx.fullmatch(first):
                    self.deny(f"`{text}`: the glob {name} copied into "
                              f"{dest_rel or 'the repository root'} may overwrite {path}; "
                              f"{_RESTORE_HINT}")
                    return

    def glob_arg(self, pattern: str, destructive: bool, text: str) -> None:
        ctx = self.ctx
        if self.cwd is None and not _is_abs(pattern):
            if "/" in pattern:
                return
            rx = glob_to_regex(pattern)
            hits = [p for k, p in ctx.frozen_names.items() if rx.fullmatch(k)]
            hits += [k for k in ctx.kit_names if "/" not in k and rx.fullmatch(k)]
        else:
            rel = ctx.root.rel(pattern, self.cwd or ctx.root.text)
            if not rel:
                return
            rx = glob_to_regex(rel)
            hits = [p for p in ctx.frozen.values() if rx.fullmatch(p)]
            hits += [k for k in ctx.kit_names if rx.fullmatch(k)]
            if destructive:
                hits += [d for d in (*ctx.frozen_dirs, *ctx.protected_dirs)
                         if d and rx.fullmatch(d)]
                if glob_match(rel, ctx.protected_dir_globs):
                    hits.append(rel)
        if hits:
            self.deny(f"`{text}`: the glob {pattern} matches {hits[0]}, which is frozen or "
                      f"protected; {_RESTORE_HINT}")


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
            _Shell(ctx, out, ctx.cwd).run(action.command)
        else:
            raise TypeError(f"not a guard action: {action!r}")
    return out.decision()


def _valid_glob(pattern) -> bool:
    try:
        glob_to_regex(pattern)
    except (re.error, TypeError):
        return False
    return True


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
        protected = [g for g in (*globs, lock, log, _CONFIG_NAME, ".agentkit", ".agentkit/**",
                                 *logs, specs.rstrip("/") + "/*/reviews/**") if _valid_glob(g)]
        r = _Root(root) if root is not None else None
    except Exception:  # noqa: BLE001 - nothing can be classified
        r, protected = None, []
    base = r.text if r is not None else ""
    start = _join(base, cwd) if (cwd and r is not None) else base
    denied = False
    allowed = False
    for action in actions:
        if isinstance(action, WriteAction) and r is not None:
            paths = action.paths if isinstance(action.paths, list) else []
            if not paths:
                allowed = True
            for path in paths:
                try:
                    rel = r.rel(path, start)
                except Exception:  # noqa: BLE001 - an unreadable path is not a test file
                    rel = None
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
