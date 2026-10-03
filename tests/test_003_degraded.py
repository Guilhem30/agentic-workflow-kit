"""Spec 003: degraded mode and robustness (R003-27, R003-29 to R003-31)."""
from __future__ import annotations

import os
import subprocess
import unittest
from unittest import mock

from agentkit import guard
from tests.guard_fixtures import ALLOW, DENY, GuardCase, ReadAction, ShellAction, WriteAction

PREFIX = "agentkit guard error ("
SUFFIX = "): writes to test files are refused until the guard is fixed"
ALLOWING = "agentkit guard error (allowing): "


class DegradedCase(GuardCase):
    """A valid configuration with a corrupt lock: the guard fails after the payload became
    actions. The fixture profile's frozen_globs are tests/**, **/src/test/** and fixtures/**."""

    def setUp(self) -> None:
        super().setUp()
        self.lock_file.write_bytes(b"{ this is not json\n")

    def assert_degraded_deny(self, *paths: str, cfg="load") -> None:
        for path in paths:
            with self.subTest(path=path):
                decision = self.decide(WriteAction([path]), cfg=cfg, normal=False)
                self.assertIsInstance(decision, guard.Decision)
                self.assertEqual(decision.verdict, DENY)
                self.assertTrue(decision.reason.startswith(PREFIX), decision.reason)
                self.assertTrue(decision.reason.endswith(SUFFIX), decision.reason)

    def assert_denied_either_way(self, *paths: str) -> None:
        """Kit files are denied without reading the lock (R003-09), so a guard that reads the
        lock lazily may answer in normal mode; both modes deny."""
        for path in paths:
            with self.subTest(path=path):
                decision = self.decide(WriteAction([path]), normal=False)
                self.assertEqual(decision.verdict, DENY)

    def assert_degraded_allow(self, *actions, cfg="load") -> None:
        for action in actions:
            with self.subTest(action=action):
                decision = self.decide(action, cfg=cfg, normal=False)
                self.assertEqual(decision.verdict, ALLOW)
                self.assertIn(ALLOWING, self.stderr)
                self.assertGreater(len(self.stderr.split(ALLOWING, 1)[1].strip()), 0)


class DegradedModeTests(DegradedCase):

    def test_R003_27_test_files_denied(self):
        self.assert_degraded_deny("core/src/test/FooTest.kt", "tests/test_x.py",
                                  "fixtures/data.json")

    def test_R003_27_kit_files_denied(self):
        self.assert_denied_either_way("tests.lock.json", "tests.unfreeze-log.md", "agentkit.toml",
                                      ".agentkit/bin/agentkit", "chaos-log.jsonl",
                                      "specs/003-guard/reviews/r.md")

    def test_R003_27_configured_chaos_log_denied(self):
        self.configure('[chaos]\nenabled = true\nlog = "meta/chaos.jsonl"\n')
        self.assert_denied_either_way("meta/chaos.jsonl")

    def test_R003_27_configured_kit_paths_denied(self):
        self.configure('[paths]\nlock = "meta/lock.json"\nunfreeze_log = "meta/unfreeze.md"\n'
                       'specs = "doc/specs"\n')
        self.write("meta/lock.json", "{ not json\n")
        self.assert_denied_either_way("meta/lock.json", "meta/unfreeze.md",
                                      "doc/specs/003-x/reviews/r.md")

    def test_R003_27_paths_still_resolve(self):
        self.assert_degraded_deny(str(self.root / "core/src/test/FooTest.kt"))
        decision = self.decide(WriteAction(["FooTest.kt"]), cwd=self.root / "core/src/test",
                               normal=False)
        self.assertEqual(decision.verdict, DENY)

    def test_R003_27_everything_else_allowed_with_a_warning(self):
        # Writes inside the repository need the frozen list, so the corrupt lock bites.
        self.assert_degraded_allow(WriteAction(["core/src/main/Foo.kt"]),
                                   ShellAction("rm core/src/test/FooTest.kt"),
                                   WriteAction([".github/workflows/ci.yml"]))

    def test_R003_27_mixed_actions(self):
        decision = self.decide(WriteAction(["core/src/main/Foo.kt"]),
                               WriteAction(["core/src/test/FooTest.kt"]),
                               ShellAction("ls"), normal=False)
        self.assertEqual(decision.verdict, DENY)
        self.assertTrue(all(r.startswith(PREFIX) for r in decision.reasons), decision.reasons)

    def test_R003_29_profile_globs_when_the_configuration_loads(self):
        self.write(".agentkit/profiles/fixture.toml", 'frozen_globs = ["spec/**"]\n')
        self.assert_degraded_deny("spec/foo_spec.rb")
        self.assert_degraded_allow(WriteAction(["tests/test_x.py"]))

    def test_R003_29_no_git(self):
        with mock.patch.object(subprocess, "run") as run, \
                mock.patch.object(subprocess, "Popen") as popen:
            self.assert_degraded_deny("core/src/test/FooTest.kt")
            self.assert_degraded_allow(ShellAction("rm core/src/test/FooTest.kt"))
        run.assert_not_called()
        popen.assert_not_called()

    def test_R003_30_degraded_deny_is_a_normal_decision(self):
        decision = self.decide(WriteAction(["tests/test_x.py"]), normal=False)
        self.assertIsInstance(decision, guard.Decision)
        self.assertEqual(decision.verdict, DENY)
        self.assertEqual(decision.reason, "; ".join(decision.reasons))

    def test_R003_30_degraded_allow_warns_on_stderr(self):
        decision = self.decide(WriteAction(["core/src/main/Foo.kt"]), normal=False)
        self.assertEqual(decision.verdict, ALLOW)
        self.assertIn(ALLOWING, self.stderr)


class NoConfigurationTests(DegradedCase):
    """cfg is None: agentkit.toml does not load (here: a syntax error)."""

    def setUp(self) -> None:
        super().setUp()
        self.write("agentkit.toml", "[kit\nprofile = \n")

    def test_R003_29_union_of_shipped_profiles(self):
        # The generic profile ships with the kit; its frozen_globs are tests/** and test/**.
        self.assert_degraded_deny("tests/test_x.py", "test/x_test.go", cfg=None)
        self.assert_degraded_allow(WriteAction(["src/main.py"]), ShellAction("rm tests/x.py"),
                                   cfg=None)

    def test_R003_29_kit_files_denied_without_configuration(self):
        self.assert_degraded_deny("agentkit.toml", "tests.lock.json", "chaos-log.jsonl",
                                  ".agentkit/profiles/fixture.toml",
                                  "specs/003-guard/reviews/r.md", cfg=None)

    def test_R003_27_reads_and_shell_allowed_with_a_warning(self):
        self.assert_degraded_allow(ReadAction(["core/src/test/FooTest.kt"]),
                                   ReadAction(["app/build/reports/x.html"]),
                                   ShellAction("./gradlew test"),
                                   ShellAction("git commit --no-verify -m x"),
                                   ShellAction("make"), cfg=None)

    def test_R003_27_paths_outside_the_repository_allowed(self):
        self.assert_degraded_allow(WriteAction([str(self.tmp / "elsewhere/tests/test_x.py")]),
                                   WriteAction(["../elsewhere/tests/test_x.py"]), cfg=None)

    def test_R003_29_root_from_the_working_directory(self):
        os.chdir(self.tmp)  # outside the repository: only the cwd argument leads to the root
        decision = self.decide(WriteAction(["x_test.py"]), cwd=self.root / "tests", cfg=None,
                               normal=False)
        self.assertEqual(decision.verdict, DENY)
        self.assertTrue(decision.reason.startswith(PREFIX))


class EmptyPayloadTests(GuardCase):
    """R003-31 at the evaluate() level: a payload that yields no actions is allowed. The stderr
    warning for a payload that does not parse belongs to the guard command (004)."""

    def test_R003_31_empty_action_list_allows(self):
        decision = self.decide()
        self.assertEqual(decision.verdict, ALLOW)
        self.assertEqual(decision.reasons, [])


if __name__ == "__main__":
    unittest.main()
