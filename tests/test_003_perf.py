"""Spec 003: decision time (R003-28)."""
from __future__ import annotations

import subprocess
import time
import unittest
from unittest import mock

from tests.guard_fixtures import (DENY, FROZEN, GuardCase, ReadAction, ShellAction,
                                  WriteAction)

LIMIT_SECONDS = 0.3


class PerformanceTests(GuardCase):
    """5,000 files, 1,000 of them frozen."""

    def setUp(self) -> None:
        super().setUp()
        frozen = [FROZEN]
        for i in range(1, 1000):
            rel = f"mod{i % 50}/src/test/T{i}Test.kt"
            self.write(rel, f"// {i}\n")
            frozen.append(rel)
        for i in range(4000):
            self.write(f"mod{i % 50}/src/main/C{i}.kt", f"// {i}\n")
        self.write_lock(frozen)

    def test_R003_28_decides_within_300_ms_without_git(self):
        cfg = self.cfg()
        actions = [
            WriteAction([FROZEN, "mod7/src/main/C7.kt", ".github/workflows/ci.yml"]),
            ReadAction(["mod3/build/out.txt", "mod3/src/test/T3Test.kt"]),
            ShellAction("cd mod9/src && rm -rf test; cd $X && rm T9Test.kt; "
                        "sed -i s/a/b/ mod1/src/test/*.kt; python -c \"open('T42Test.kt')\"; "
                        "git commit -m ok | tee log.txt > /dev/null"),
        ]
        from agentkit import guard
        best = None
        with mock.patch.object(subprocess, "run", side_effect=AssertionError("git called")), \
                mock.patch.object(subprocess, "Popen", side_effect=AssertionError("git called")):
            for _ in range(3):
                start = time.perf_counter()
                decision = guard.evaluate(cfg, actions, cwd=str(self.root))
                elapsed = time.perf_counter() - start
                best = elapsed if best is None else min(best, elapsed)
        self.assertEqual(decision.verdict, DENY)
        self.assertLess(best, LIMIT_SECONDS)


if __name__ == "__main__":
    unittest.main()
