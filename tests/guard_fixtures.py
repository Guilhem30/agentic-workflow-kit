"""Fixtures for the guard tests of spec 003 (R003-01 to R003-32). This file belongs to spec 003;
IDs of other specs are built with rid().
"""
from __future__ import annotations

import contextlib
import io
from pathlib import Path

from agentkit import guard
from agentkit.guard import ALLOW, ASK, DENY, ReadAction, ShellAction, WriteAction
from tests.support import RepoTestCase

FROZEN = "app/src/test/FooTest.kt"
REMEDIES = ("owner", "agentkit lock restore")
DEGRADED = "agentkit guard error"

__all__ = ["ALLOW", "ASK", "DENY", "FROZEN", "GuardCase", "ReadAction", "ShellAction",
           "WriteAction"]


class GuardCase(RepoTestCase):
    """A project whose lock freezes app/src/test/FooTest.kt (plus FROZEN_EXTRA). No git: the
    guard never runs it (R003-28)."""

    USE_GIT = False
    FROZEN_EXTRA: tuple[str, ...] = ()

    def setUp(self) -> None:
        super().setUp()
        self.write("app/src/main/Foo.kt", "class Foo\n")
        self.write("tools/build.sh", "echo build\n")
        self.write("docs/notes.md", "notes\n")
        frozen = (FROZEN, *self.FROZEN_EXTRA)
        for rel in frozen:
            self.write(rel, f"// frozen {rel}\n")
        self.write_lock(frozen)
        self.stderr = ""

    def configure(self, rest: str) -> None:
        """Rewrite agentkit.toml with extra tables after [kit]."""
        self.write("agentkit.toml", f'[kit]\nprofile = "fixture"\n\n{rest}')

    def decide(self, *actions, cwd: str | Path | None = None, cfg="load",
               normal: bool = True) -> guard.Decision:
        """evaluate() with stderr captured into self.stderr. With normal=True, a fallback to
        degraded mode (R003-27) fails the test, so an allow cannot come from a crash."""
        config = self.cfg() if cfg == "load" else cfg
        where = None if cwd is None else str(cwd)
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            decision = guard.evaluate(config, list(actions), cwd=where)
        self.stderr = buf.getvalue()
        if normal:
            self.assertNotIn(DEGRADED, self.stderr)
            self.assertFalse(any(r.startswith(DEGRADED) for r in decision.reasons),
                             decision.reasons)
        return decision

    def verdict(self, *actions, cwd=None) -> str:
        return self.decide(*actions, cwd=cwd).verdict

    def sh(self, command: str, cwd=None) -> str:
        return self.verdict(ShellAction(command), cwd=cwd)

    def assert_shell(self, expected: str, *commands: str, cwd=None) -> None:
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(self.sh(command, cwd=cwd), expected)

    def assert_writes(self, expected: str, *paths: str, cwd=None) -> None:
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.verdict(WriteAction([path]), cwd=cwd), expected)

    def assert_remedy(self, reason: str) -> None:
        low = reason.lower()
        self.assertTrue(any(r in low for r in REMEDIES),
                        f"reason does not say what to do instead: {reason!r}")
