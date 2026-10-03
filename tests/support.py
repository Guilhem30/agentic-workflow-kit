"""Shared fixtures: temporary directories, git repositories, lock files and CLI capture.

Requirement IDs that belong to other specs are built with rid() so that this file and the test
files do not themselves "belong" to those specs when the kit freezes its own tests (R002-07).
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

AGENT_ENV_VARS = ("AGENTKIT_AGENT", "CLAUDECODE", "CODEX_SANDBOX", "CODEX_THREAD_ID",
                  "OPENCODE", "PI_CODING_AGENT")

FIXTURE_PROFILE = 'frozen_globs = ["tests/**", "**/src/test/**", "fixtures/**"]\n'

LOG_HEADER = "# Unfreeze log\n\nAppend-only: earlier entries are never rewritten.\n"


def rid(spec: str, req: str, sep: str = "-") -> str:
    return "R" + spec + sep + req


def sha256_lf(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _rmtree(path: Path) -> None:
    def fix(func, p, *_):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=fix)
    else:
        shutil.rmtree(path, onerror=fix)


def run_cli(*argv: str) -> tuple[int, str]:
    """Run agentkit in-process; return (exit code, stdout+stderr)."""
    from agentkit import cli
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            code = cli.main(list(argv))
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    return code, buf.getvalue()


class TempDirTestCase(unittest.TestCase):
    """A clean temporary directory, a clean environment (no agent variables, no AGENTKIT_ROOT)
    and the original working directory restored afterwards."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="agentkit-test-")).resolve()
        self.addCleanup(_rmtree, self.tmp)
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        for name in AGENT_ENV_VARS + ("AGENTKIT_ROOT",):
            os.environ.pop(name, None)
        self.addCleanup(os.chdir, os.getcwd())

    # files -----------------------------------------------------------------------------
    def write(self, path: Path | str, content: str | bytes = "x\n", base: Path | None = None) -> Path:
        p = Path(path) if Path(path).is_absolute() else (base or self.base) / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
        return p

    @property
    def base(self) -> Path:
        return self.tmp

    def project(self, where: Path | str, kit: str = 'profile = "fixture"', rest: str = "",
                profile_body: str = FIXTURE_PROFILE, profile_name: str = "fixture") -> Path:
        """Write agentkit.toml and a profile under .agentkit/profiles; return the root."""
        root = Path(where) if Path(where).is_absolute() else self.tmp / where
        root.mkdir(parents=True, exist_ok=True)
        self.write(root / "agentkit.toml", f"[kit]\n{kit}\n\n{rest}")
        if profile_name:
            self.write(root / ".agentkit" / "profiles" / f"{profile_name}.toml", profile_body)
        return root

    # git -------------------------------------------------------------------------------
    def git(self, *args: str, cwd: Path | None = None) -> str:
        proc = subprocess.run(["git", *args], cwd=cwd or self.base, capture_output=True,
                              text=True, check=True)
        return proc.stdout.strip()

    def init_git(self, root: Path) -> None:
        self.git("-c", "init.defaultBranch=main", "init", "-q", cwd=root)
        for key, value in (("user.name", "Fixture Owner"), ("user.email", "owner@example.invalid"),
                           ("core.autocrlf", "false"), ("commit.gpgsign", "false")):
            self.git("config", key, value, cwd=root)

    def commit_all(self, message: str = "fixture") -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "--no-verify", "-m", message)
        return self.git("rev-parse", "HEAD")


class RepoTestCase(TempDirTestCase):
    """A project root at <tmp>/repo (a git repository unless USE_GIT is False), used as cwd."""

    USE_GIT = True
    KIT = 'profile = "fixture"'
    REST = ""

    def setUp(self) -> None:
        super().setUp()
        self.root = self.project(self.tmp / "repo", kit=self.KIT, rest=self.REST)
        if self.USE_GIT:
            self.init_git(self.root)
        os.chdir(self.root)

    @property
    def base(self) -> Path:
        return self.root

    def cfg(self):
        from agentkit.config import load_config
        return load_config(root=self.root)

    @property
    def lock_file(self) -> Path:
        return self.root / "tests.lock.json"

    @property
    def log_file(self) -> Path:
        return self.root / "tests.unfreeze-log.md"

    def snapshot(self, path: Path) -> bytes | None:
        return path.read_bytes() if path.exists() else None

    def write_lock(self, entries, extra: dict | None = None) -> None:
        """entries: {path: spec-or-None} or an iterable of paths; hashes come from the worktree."""
        if not isinstance(entries, dict):
            entries = {p: None for p in entries}
        files = {}
        for rel in sorted(entries):
            entry = {"sha256": sha256_lf((self.root / rel).read_bytes())}
            if entries[rel]:
                entry["spec"] = entries[rel]
            files[rel] = entry
        data = {"version": 1, "algorithm": "sha256-lf", "files": files}
        data.update(extra or {})
        self.lock_file.write_bytes((json.dumps(data, indent=2) + "\n").encode())

    def read_lock(self) -> dict:
        return json.loads(self.lock_file.read_text(encoding="utf-8"))

    def write_spec(self, num: str, status: str, slug: str = "fixture") -> Path:
        return self.write(f"specs/{num}-{slug}/spec.md",
                          f'---\nid: "{num}"\ntitle: Fixture {num}\nstatus: {status}\n---\n\n'
                          f"# {num} Fixture\n\nBody stays untouched.\n")

    def spec_status(self, num: str, slug: str = "fixture") -> str:
        text = (self.root / f"specs/{num}-{slug}/spec.md").read_text(encoding="utf-8")
        return re.search(r"^status:\s*(\S+)", text, re.M).group(1)
