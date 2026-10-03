"""Private git and file-walk helpers shared by lock (002) and trace (005)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

WALK_SKIP = {".git", "node_modules", "__pycache__", ".gradle"}


def run(root: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    """Run git with list arguments in the root; bytes output."""
    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, check=check)
    except FileNotFoundError:
        return subprocess.CompletedProcess(["git", *args], 127, b"", b"git not found")


def is_repo(root: Path) -> bool:
    proc = run(root, "rev-parse", "--is-inside-work-tree")
    return proc.returncode == 0 and proc.stdout.strip() == b"true"


def toplevel(root: Path) -> Path | None:
    proc = run(root, "rev-parse", "--show-toplevel")
    if proc.returncode != 0:
        return None
    return Path(proc.stdout.decode("utf-8").strip()).resolve()


def prefix(root: Path) -> str:
    """The root's path inside the git work tree ('' or 'sub/dir/')."""
    proc = run(root, "rev-parse", "--show-prefix")
    return proc.stdout.decode("utf-8").strip() if proc.returncode == 0 else ""


def resolve_commit(root: Path, ref: str) -> str | None:
    if not ref or ref.startswith("-"):
        return None  # never let a ref be read as an option
    proc = run(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("ascii").strip() or None


def show(root: Path, spec: str) -> bytes | None:
    """`git show <spec>` (for example `HEAD:path` or `:path`); None when absent."""
    proc = run(root, "show", spec)
    return proc.stdout if proc.returncode == 0 else None


def at_ref(root: Path, ref: str, rel: str, pre: str | None = None) -> bytes | None:
    """The file at a resolved commit. Pass `pre` (from prefix()) to save a git call per file."""
    return show(root, f"{ref}:{prefix(root) if pre is None else pre}{rel}")


def staged(root: Path, rel: str, pre: str | None = None) -> bytes | None:
    return show(root, f":{prefix(root) if pre is None else pre}{rel}")


def user_name(root: Path) -> str:
    proc = run(root, "config", "user.name")
    name = proc.stdout.decode("utf-8", "replace").strip() if proc.returncode == 0 else ""
    return name or "unknown"


def listed_files(root: Path) -> list[str] | None:
    """Tracked and untracked, non-ignored files (repo-relative, existing); None without git."""
    if not is_repo(root):
        return None
    proc = run(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if proc.returncode != 0:
        return None
    seen = set()
    out = []
    for raw in proc.stdout.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8", "surrogateescape")
        if rel not in seen and (root / rel).is_file():
            seen.add(rel)
            out.append(rel)
    return sorted(out)


def walk_files(root: Path) -> list[str]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in WALK_SKIP]
        for name in filenames:
            rel = (Path(dirpath) / name).relative_to(root).as_posix()
            out.append(rel)
    return sorted(out)


def repo_files(root: Path) -> list[str]:
    files = listed_files(root)
    return walk_files(root) if files is None else files
