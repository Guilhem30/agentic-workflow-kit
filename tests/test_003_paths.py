"""Spec 003: actions, decisions and path classification (R003-01 to R003-12)."""
from __future__ import annotations

import os
import unittest
from pathlib import Path

from agentkit import guard
from tests.guard_fixtures import (ALLOW, ASK, DENY, FROZEN, GuardCase, ReadAction, ShellAction,
                                  WriteAction)


class ActionsAndDecisionTests(GuardCase):

    def test_R003_01_contract_names(self):
        self.assertEqual((guard.ALLOW, guard.ASK, guard.DENY), ("allow", "ask", "deny"))
        self.assertEqual(guard.WriteAction(["a"]).paths, ["a"])
        self.assertEqual(guard.ReadAction(["a"]).paths, ["a"])
        self.assertEqual(guard.ShellAction("ls").command, "ls")
        decision = guard.Decision("deny", ["one", "two"])
        self.assertEqual(decision.reason, "one; two")

    def test_R003_01_each_action_kind_is_judged(self):
        self.assertEqual(self.verdict(WriteAction([FROZEN])), DENY)
        self.assertEqual(self.verdict(ReadAction(["app/build/reports/x.html"])), DENY)
        self.assertEqual(self.verdict(ShellAction(f"rm {FROZEN}")), DENY)
        decision = self.decide(WriteAction(["app/src/main/Foo.kt"]), ReadAction([FROZEN]),
                               ShellAction("ls -la"))
        self.assertEqual(decision.verdict, ALLOW)
        self.assertEqual(decision.reasons, [])

    def test_R003_01_a_write_action_with_several_paths(self):
        self.assertEqual(self.verdict(WriteAction(["app/src/main/Foo.kt", FROZEN])), DENY)

    def test_R003_02_most_severe_verdict_wins(self):
        ask = WriteAction([".github/workflows/ci.yml"])
        deny = WriteAction([FROZEN])
        allow = WriteAction(["docs/notes.md"])
        self.assertEqual(self.decide(allow, ask).verdict, ASK)
        for order in ((allow, ask, deny), (deny, ask, allow), (ask, deny)):
            with self.subTest(order=order):
                decision = self.decide(*order)
                self.assertEqual(decision.verdict, DENY)
                self.assertEqual(len(decision.reasons), 2)
                self.assertTrue(any(".github/workflows/ci.yml" in r for r in decision.reasons))
                self.assertTrue(any(FROZEN in r for r in decision.reasons))

    def test_R003_02_reasons_are_deduplicated(self):
        decision = self.decide(WriteAction([FROZEN]), WriteAction([FROZEN]))
        self.assertEqual(decision.verdict, DENY)
        self.assertEqual(len(decision.reasons), 1)
        self.assertEqual(len(decision.reasons), len(set(decision.reasons)))

    def test_R003_02_allowed_actions_add_no_reason(self):
        decision = self.decide(WriteAction(["docs/notes.md"]), WriteAction([FROZEN]))
        self.assertEqual(len(decision.reasons), 1)
        self.assertEqual(decision.reason, decision.reasons[0])

    def test_R003_03_deny_reason_names_path_and_remedy(self):
        decision = self.decide(WriteAction([FROZEN]))
        self.assertIn(FROZEN, decision.reason)
        self.assert_remedy(decision.reason)

    def test_R003_03_ask_reason_names_path_and_remedy(self):
        decision = self.decide(WriteAction([".github/workflows/ci.yml"]))
        self.assertEqual(decision.verdict, ASK)
        self.assertIn(".github/workflows/ci.yml", decision.reason)
        self.assert_remedy(decision.reason)

    def test_R003_03_shell_reason_names_command_or_path_and_remedy(self):
        for command, needle in ((f"rm {FROZEN}", FROZEN),
                                ("git commit --no-verify -m x", "--no-verify"),
                                ("agentkit lock unfreeze x --reason y", "unfreeze")):
            with self.subTest(command=command):
                decision = self.decide(ShellAction(command))
                self.assertEqual(decision.verdict, DENY)
                self.assertIn(needle, decision.reason)
                self.assert_remedy(decision.reason)


class PathResolutionTests(GuardCase):

    def test_R003_04_absolute_paths_inside_the_root(self):
        self.assertEqual(self.verdict(WriteAction([str(self.root / FROZEN)])), DENY)

    def test_R003_04_relative_to_the_given_cwd(self):
        self.assert_writes(DENY, "FooTest.kt", "./FooTest.kt", cwd=self.root / "app/src/test")
        self.assert_writes(DENY, "../test/FooTest.kt", cwd=self.root / "app/src/main")
        self.assert_writes(ALLOW, "FooTest.kt", cwd=self.root / "app/src/main")

    def test_R003_04_default_cwd_is_the_root(self):
        os.chdir(self.root / "app")
        self.assertEqual(self.verdict(WriteAction([FROZEN])), DENY)
        self.assertEqual(self.verdict(WriteAction(["src/test/FooTest.kt"])), ALLOW)

    def test_R003_04_dot_segments_are_normalised(self):
        self.assert_writes(DENY, "app/src/main/../test/FooTest.kt", "app//src/./test/FooTest.kt")

    def test_R003_04_paths_outside_the_repository_are_ignored(self):
        outside = self.tmp / "elsewhere" / "tests.lock.json"
        self.assert_writes(ALLOW, str(outside), "../elsewhere/agentkit.toml",
                           str(self.tmp / "app/src/test/FooTest.kt"))

    @unittest.skipUnless(os.name == "nt", "Git-Bash drive paths exist only on Windows")
    def test_R003_05_git_bash_drive_paths(self):
        drive, rest = os.path.splitdrive(str(self.root / FROZEN))
        bash_path = "/" + drive.rstrip(":").lower() + rest.replace("\\", "/")
        self.assertEqual(self.verdict(WriteAction([bash_path])), DENY)
        self.assertEqual(self.sh(f"rm {bash_path}"), DENY)

    @unittest.skipIf(os.name == "nt", "POSIX check")
    def test_R003_05_posix_paths_are_not_rewritten(self):
        # On POSIX, /c/... is an ordinary absolute path outside the repository.
        self.assertEqual(self.verdict(WriteAction(["/c/" + FROZEN])), ALLOW)

    def test_R003_06_frozen_paths_compare_case_insensitively(self):
        self.assert_writes(DENY, FROZEN.upper(), "App/Src/Test/footest.kt")

    def test_R003_06_protected_globs_compare_case_insensitively(self):
        self.assert_writes(DENY, "TESTS.LOCK.JSON", "AgentKit.TOML", ".AGENTKIT/profiles/x.toml",
                           "Chaos-Log.JSONL", "SPECS/012-x/REVIEWS/r.md")
        self.assert_writes(ASK, ".GITHUB/WORKFLOWS/ci.yml", ".Claude/Settings.json")


class WritePathTests(GuardCase):
    FROZEN_EXTRA = (".agentkit/state/frozen.txt",)

    def test_R003_07_write_to_frozen_path_denied(self):
        decision = self.decide(WriteAction([FROZEN]))
        self.assertEqual(decision.verdict, DENY)
        self.assertIn(FROZEN, decision.reason)

    def test_R003_07_unfrozen_file_in_a_test_folder_allowed(self):
        self.assert_writes(ALLOW, "app/src/test/NewTest.kt", "app/src/main/Foo.kt")

    def test_R003_08_state_directory_allowed(self):
        self.assert_writes(ALLOW, ".agentkit/state/last-test.log", ".agentkit/state/a/b.json")

    def test_R003_08_allow_globs(self):
        self.configure('[guard]\nallow_globs = [".agentkit/cache/**"]\n')
        self.assert_writes(ALLOW, ".agentkit/cache/x.bin")
        self.assert_writes(DENY, ".agentkit/profiles/x.toml")

    def test_R003_08_frozen_wins_over_allow(self):
        self.assert_writes(DENY, ".agentkit/state/frozen.txt")
        self.configure('[guard]\nallow_globs = ["app/**"]\n')
        self.assert_writes(DENY, FROZEN)

    def test_R003_09_protected_files_denied(self):
        self.assert_writes(DENY, "tests.lock.json", "tests.unfreeze-log.md", "agentkit.toml",
                           ".agentkit/profiles/fixture.toml", ".agentkit/bin/agentkit",
                           "chaos-log.jsonl", "specs/012-x/reviews/1-approved-spec-reviewer.md")

    def test_R003_09_reasons_name_the_protected_path(self):
        for path in ("tests.lock.json", "agentkit.toml", ".agentkit/bin/agentkit"):
            with self.subTest(path=path):
                decision = self.decide(WriteAction([path]))
                self.assertIn(path, decision.reason)
                self.assert_remedy(decision.reason)

    def test_R003_09_configured_lock_and_log_paths(self):
        self.configure('[paths]\nlock = "meta/lock.json"\nunfreeze_log = "meta/unfreeze.md"\n')
        (self.root / "tests.lock.json").replace(self.root / "meta-lock.tmp")
        (self.root / "meta").mkdir()
        (self.root / "meta-lock.tmp").replace(self.root / "meta/lock.json")
        self.assert_writes(DENY, "meta/lock.json", "meta/unfreeze.md", FROZEN)

    def test_R003_09_deny_globs(self):
        self.configure('[guard]\ndeny_globs = ["secrets/**", "*.pem"]\n')
        self.assert_writes(DENY, "secrets/key.txt", "server.pem")
        self.assert_writes(ALLOW, "docs/notes.md")

    def test_R003_09_reviews_under_any_spec_folder(self):
        self.assert_writes(DENY, "specs/003-guard/reviews/x.md", "specs/a/reviews/b/c.md")
        self.assert_writes(ALLOW, "specs/003-guard/plan.md", "specs/003-guard/reviews.md")

    def test_R003_09_chaos_log_protected_with_chaos_off(self):
        self.configure("[chaos]\nenabled = false\n")
        self.assert_writes(DENY, "chaos-log.jsonl", "specs/003-guard/reviews/x.md")

    def test_R003_10_enforcement_configuration_asks(self):
        self.assert_writes(ASK, ".claude/settings.json", ".codex/hooks.json", ".codex/config.toml",
                           ".opencode/plugins/agentkit.ts", "opencode.json", ".pi/extensions/x.ts",
                           ".githooks/pre-commit", ".github/workflows/ci.yml", ".gitlab-ci.yml",
                           "CODEOWNERS", ".github/CODEOWNERS")

    def test_R003_10_ask_globs(self):
        self.configure('[guard]\nask_globs = ["infra/**"]\n')
        self.assert_writes(ASK, "infra/main.tf")

    def test_R003_10_neighbours_are_not_ask(self):
        self.assert_writes(ALLOW, ".claude/settings.local.json.bak", ".github/dependabot.yml",
                           "docs/CODEOWNERS.md", ".codex/notes.md")


class ReadPathTests(GuardCase):

    def test_R003_11_build_output_read_denied_with_hint(self):
        for path in ("app/build/reports/x.html", "web/node_modules/a/index.js",
                     "agentkit/__pycache__/x.pyc", "dist/app.js"):
            with self.subTest(path=path):
                decision = self.decide(ReadAction([path]))
                self.assertEqual(decision.verdict, DENY)
                self.assertIn(path, decision.reason)
                self.assertIn("agentkit test", decision.reason)

    def test_R003_11_follows_the_profile_globs(self):
        self.write(".agentkit/profiles/fixture.toml",
                   'frozen_globs = ["**/src/test/**"]\nbuild_output_globs = ["out/**"]\n')
        self.assertEqual(self.verdict(ReadAction(["out/report.txt"])), DENY)
        self.assertEqual(self.verdict(ReadAction(["app/build/x.html"])), ALLOW)

    def test_R003_11_switch_off(self):
        self.configure("[guard]\ndeny_build_output_reads = false\n")
        self.assertEqual(self.verdict(ReadAction(["app/build/reports/x.html"])), ALLOW)

    def test_R003_12_other_reads_allowed(self):
        decision = self.decide(ReadAction([FROZEN, "tests.lock.json", "agentkit.toml",
                                           ".github/workflows/ci.yml", "chaos-log.jsonl",
                                           "app/src/main/Foo.kt"]))
        self.assertEqual(decision.verdict, ALLOW)
        self.assertEqual(decision.reasons, [])


if __name__ == "__main__":
    unittest.main()
