"""Small cross-platform helpers shared by every command."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

_GITBASH_DRIVE = re.compile(r"^/([a-zA-Z])(/|$)")
_glob_cache: dict[str, re.Pattern] = {}


def normalize_bytes(data: bytes) -> bytes:
    """CRLF -> LF so hashes are stable across checkouts with different autocrlf settings."""
    return data.replace(b"\r\n", b"\n")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(normalize_bytes(data)).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_text_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def glob_to_regex(pattern: str) -> re.Pattern:
    """gitignore-like glob: `**/` any dirs, `**` anything, `*` and `?` stay inside one segment.

    Matching is case-insensitive (protection must hold on case-insensitive filesystems).
    """
    cached = _glob_cache.get(pattern)
    if cached is not None:
        return cached
    p = pattern.replace("\\", "/")
    out = []
    i = 0
    while i < len(p):
        c = p[i]
        if p.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif p.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c == "[":
            j = p.find("]", i + 1)
            if j == -1:
                out.append(re.escape(c))
                i += 1
            else:
                body = p[i + 1 : j].replace("\\", "\\\\")
                if body.startswith("!"):
                    body = "^" + body[1:]
                out.append("[" + body + "]")
                i = j + 1
        else:
            out.append(re.escape(c))
            i += 1
    rx = re.compile("^" + "".join(out) + "$", re.IGNORECASE)
    _glob_cache[pattern] = rx
    return rx


def glob_match(path: str, patterns) -> bool:
    path = path.replace("\\", "/")
    return any(glob_to_regex(pat).match(path) for pat in patterns)


def to_native(path_str: str) -> str:
    """Turn Git-Bash style `/c/Users/x` into `C:/Users/x` on Windows; strip quotes."""
    s = path_str.strip().strip("'\"")
    if os.name == "nt":
        m = _GITBASH_DRIVE.match(s)
        if m:
            s = m.group(1).upper() + ":/" + s[m.end() :]
    return s


def rel_to_root(path_str: str, root: Path, cwd: Path | None = None) -> str | None:
    """Repo-relative POSIX path, or None when the path lies outside the root."""
    if not path_str:
        return None
    s = to_native(path_str)
    base = str(cwd or root)
    absolute = os.path.abspath(os.path.join(base, s))
    try:
        rel = os.path.relpath(absolute, str(root))
    except ValueError:  # different drive on Windows
        return None
    rel = rel.replace("\\", "/")
    if rel == ".":
        return ""
    if rel.startswith("../") or rel == "..":
        return None
    return rel


def run(cmd, cwd: Path, check: bool = False, shell: bool = False, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        shell=shell,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=check,
        env=env,
    )


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return run(["git", *args], cwd=root)


def git_bytes(root: Path, *args: str) -> bytes | None:
    """Raw stdout of a git command, or None on failure."""
    try:
        proc = subprocess.run(["git", *args], cwd=str(root), capture_output=True)
    except OSError:
        return None
    return proc.stdout if proc.returncode == 0 else None


def is_git_repo(root: Path) -> bool:
    try:
        return git(root, "rev-parse", "--is-inside-work-tree").stdout.strip() == "true"
    except OSError:
        return False


def list_repo_files(root: Path, exclude_globs=()) -> list[str]:
    """Tracked + untracked-not-ignored files (git), else a filesystem walk."""
    files: list[str] = []
    if is_git_repo(root):
        out = git_bytes(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
        if out is not None:
            seen = set()
            for raw in out.split(b"\0"):
                if not raw:
                    continue
                rel = raw.decode("utf-8", "replace")
                if rel in seen or not (root / rel).is_file():
                    continue
                seen.add(rel)
                files.append(rel)
    else:
        skip_dirs = {".git", "node_modules", "__pycache__", ".gradle"}
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            for name in filenames:
                rel = os.path.relpath(os.path.join(dirpath, name), root).replace("\\", "/")
                files.append(rel)
    if exclude_globs:
        files = [f for f in files if not glob_match(f, exclude_globs)]
    return sorted(files)


def parse_front_matter(text: str) -> tuple[dict, str]:
    """Minimal `---` front matter parser: `key: value` and `key: [a, b]` lines, plus one-level maps."""
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    data: dict = {}
    current_map: dict | None = None
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")) and current_map is not None:
            k, _, v = line.strip().partition(":")
            current_map[k.strip()] = _scalar(v.strip())
            continue
        k, _, v = line.partition(":")
        k, v = k.strip(), v.strip()
        if v == "":
            current_map = {}
            data[k] = current_map
        else:
            current_map = None
            data[k] = _scalar(v)
    body = "\n".join(lines[end + 1 :])
    if text.endswith("\n"):
        body += "\n"
    return data, body


def _scalar(v: str):
    if v.startswith("[") and v.endswith("]"):
        return [_scalar(x.strip()) for x in v[1:-1].split(",") if x.strip()]
    if len(v) >= 2 and v[0] == v[-1] == '"':
        return v[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if len(v) >= 2 and v[0] == v[-1] == "'":
        return v[1:-1]
    return v


def dump_front_matter(data: dict) -> str:
    lines = ["---"]
    for k, v in data.items():
        if isinstance(v, dict):
            lines.append(f"{k}:")
            for k2, v2 in v.items():
                lines.append(f"  {k2}: {_dump_scalar(v2)}")
        else:
            lines.append(f"{k}: {_dump_scalar(v)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _dump_scalar(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, list):
        return "[" + ", ".join(_dump_scalar(x) for x in v) + "]"
    s = str(v)
    if s == "" or s[0] in "[{&*!|>%@`'\"" or ": " in s or s.endswith(":") or " #" in s:
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s
