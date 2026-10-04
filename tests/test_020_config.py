"""Spec 020: the `[chaos]` table, chaos off, specs outside chaos mode, git and base commit."""
from __future__ import annotations

import os

from agentkit import chaos
from agentkit.config import ConfigError
from tests.chaos_fixtures import CHAOS_ON, FAIL, NOW, SPEC_PASS, ChaosCase
from tests.support import rid, run_cli

DEFAULT_GLOBS = ["specs/000-*/**", "AGENTS.md", "CLAUDE.md", "docs/adr/**", "agentkit.toml",
                 "roles/**"]


class SettingsTests(ChaosCase):

    def settings_for(self, table: str):
        self.write("agentkit.toml", f'[kit]\nprofile = "fixture"\n\n{table}')
        return chaos.settings(self.cfg())

    def test_R020_01_defaults(self):
        s = self.settings_for(CHAOS_ON)
        self.assertIs(s.enabled, True)
        self.assertEqual(s.specs, [])
        self.assertEqual(s.max_rejections, 2)
        self.assertEqual(s.log_rel, "chaos-log.jsonl")
        self.assertEqual(s.log_path.resolve(), self.root / "chaos-log.jsonl")
        self.assertEqual(s.escalate_globs, DEFAULT_GLOBS)
        self.assertEqual(chaos.DEFAULT_LOG, "chaos-log.jsonl")

    def test_R020_01_no_table_is_off(self):
        s = self.settings_for("")
        self.assertIs(s.enabled, False)
        self.assertFalse(s.applies("012"))

    def test_R020_01_all_keys(self):
        s = self.settings_for('[chaos]\nenabled = true\nspecs = ["012", "999"]\nmax_rejections = 3\n'
                              'log = "meta/chaos.jsonl"\nescalate_globs = ["x/**"]\nfuture = 1\n')
        self.assertEqual(s.specs, ["012", "999"])
        self.assertEqual(s.max_rejections, 3)
        self.assertEqual(s.log_rel, "meta/chaos.jsonl")
        self.assertEqual(s.log_path.resolve(), self.root / "meta" / "chaos.jsonl")
        self.assertEqual(s.escalate_globs, ["x/**"])

    def test_R020_01_placeholders_follow_paths_table(self):
        s = self.settings_for('[paths]\nspecs = "doc/specs"\nroles = "team/roles"\n\n' + CHAOS_ON)
        self.assertEqual(s.escalate_globs, ["doc/specs/000-*/**", "AGENTS.md", "CLAUDE.md",
                                            "docs/adr/**", "agentkit.toml", "team/roles/**"])
        s = self.settings_for('[paths]\nspecs = "doc/specs"\nroles = "team/roles"\n\n'
                              '[chaos]\nenabled = true\nescalate_globs = ["{specs}/9*/**", "{roles}/x"]\n')
        self.assertEqual(s.escalate_globs, ["doc/specs/9*/**", "team/roles/x"])

    def test_R020_01_specs_list_selects_specs(self):
        s = self.settings_for('[chaos]\nenabled = true\nspecs = ["012", "999"]\n')
        self.assertTrue(s.applies("012"))
        self.assertFalse(s.applies("013"))
        s = self.settings_for(CHAOS_ON)
        self.assertTrue(s.applies("012"))
        self.assertTrue(s.applies("013"))
        self.assertFalse(s.applies("000"))
        s = self.settings_for('[chaos]\nenabled = false\n')
        self.assertFalse(s.applies("012"))

    def test_R020_02_bad_values_name_the_key(self):
        cases = [
            ("chaos.enabled", 'enabled = "yes"'),
            ("chaos.specs", 'enabled = true\nspecs = "012"'),
            ("chaos.specs", 'enabled = true\nspecs = ["12"]'),
            ("chaos.max_rejections", 'enabled = true\nmax_rejections = 0'),
            ("chaos.max_rejections", 'enabled = true\nmax_rejections = "2"'),
            ("chaos.max_rejections", 'enabled = true\nmax_rejections = true'),
            ("chaos.log", 'enabled = true\nlog = 1'),
            ("chaos.log", 'enabled = true\nlog = "/tmp/chaos.jsonl"'),
            ("chaos.log", 'enabled = true\nlog = "../chaos.jsonl"'),
            ("chaos.log", 'enabled = true\nlog = "meta/../../chaos.jsonl"'),
            ("chaos.escalate_globs", 'enabled = true\nescalate_globs = "x"'),
            ("chaos.escalate_globs", 'enabled = true\nescalate_globs = [1]'),
        ]
        for key, body in cases:
            with self.subTest(case=body):
                with self.assertRaises(ConfigError) as ctx:
                    self.settings_for(f"[chaos]\n{body}\n")
                self.assertIn(key, str(ctx.exception))
                code, out = run_cli("chaos", "approve", "012", "approved", "--review",
                                    self.review(SPEC_PASS))
                self.assertEqual(code, 2)
                self.assertIn(key, out)
                self.assertFalse(self.chaos_log.exists())

    def test_R020_03_spec_000_never_listed(self):
        with self.assertRaises(ConfigError) as ctx:
            self.settings_for('[chaos]\nenabled = true\nspecs = ["012", "000"]\n')
        self.assertIn("chaos.specs", str(ctx.exception))


class ChaosOffTests(ChaosCase):
    REST = "[chaos]\nenabled = false\n"

    def test_R020_04_approve_and_unfreeze_exit_2(self):
        code, out = run_cli("chaos", "approve", "012", "approved", "--review", self.review(SPEC_PASS))
        self.assertEqual(code, 2)
        self.assertIn("owner", out.lower())
        code, out = run_cli("chaos", "unfreeze", "tests/x.py", "--reason", "wrong fixture",
                            "--auditor-review", self.review(SPEC_PASS),
                            "--impl-review", self.review(SPEC_PASS, name="i"))
        self.assertEqual(code, 2)
        self.assertIn("owner", out.lower())
        self.assertFalse(self.chaos_log.exists())
        self.assertEqual(self.spec_status("012"), "draft")

    def test_R020_04_api_raises_usage_error(self):
        with self.assertRaises(chaos.ChaosUsageError):
            chaos.approve(self.cfg(), "012", "approved", review=self.review(SPEC_PASS),
                          user="Alice", now=NOW)

    def test_R020_04_no_table_exit_2(self):
        self.write("agentkit.toml", '[kit]\nprofile = "fixture"\n')
        code, _ = run_cli("chaos", "approve", "012", "approved", "--review", self.review(SPEC_PASS))
        self.assertEqual(code, 2)

    def test_R020_36_gate_commands_unchanged_when_off(self):
        self.agent()
        code, _ = run_cli("spec-status", "012", "approved")
        self.assertEqual(code, 0)
        self.assertEqual(self.spec_status("012"), "approved")
        self.spec("012", "tests-approved")
        self.write("tests/test_x.py", f"# {rid('012', '01')}\n")
        code, _ = run_cli("lock", "freeze", "--spec", "012")
        self.assertEqual(code, 0)
        self.assertEqual(self.spec_status("012"), "frozen")
        self.assertEqual(chaos.status_suffix(self.cfg()), "")

    def test_R020_36_no_table_status_suffix_empty(self):
        self.write("agentkit.toml", '[kit]\nprofile = "fixture"\n')
        self.assertEqual(chaos.status_suffix(self.cfg()), "")


class NotUnderChaosTests(ChaosCase):
    REST = '[chaos]\nenabled = true\nspecs = ["012"]\n'
    SPECS = {"012": "draft", "013": "draft"}

    def test_R020_05_spec_not_listed(self):
        code, out = run_cli("chaos", "approve", "013", "approved", "--review", self.review(SPEC_PASS))
        self.assertEqual(code, 1)
        self.assertIn("not under chaos mode", out)
        self.assertEqual(self.spec_status("013"), "draft")
        self.assertFalse(self.chaos_log.exists())

    def test_R020_05_spec_000(self):
        self.write("agentkit.toml", '[kit]\nprofile = "fixture"\n\n' + CHAOS_ON)
        self.spec("000", "draft", slug="vision")
        self.commit_all("vision")
        code, out = run_cli("chaos", "approve", "000", "approved", "--review", self.review(SPEC_PASS))
        self.assertEqual(code, 1)
        self.assertIn("not under chaos mode", out)
        self.assertEqual(self.spec_status("000", slug="vision"), "draft")

    def test_R020_05_unfreeze_of_a_spec_not_listed(self):
        self.spec("013", "frozen")
        self.write("tests/test_013.py", "x\n")
        self.write_lock({"tests/test_013.py": "013"})
        self.commit_all("freeze 013")
        code, out = run_cli("chaos", "unfreeze", "tests/test_013.py", "--reason", "wrong fixture",
                            "--auditor-review", self.review("verdict: unfreeze justified"),
                            "--impl-review", self.review("verdict: unfreeze justified", name="i"))
        self.assertEqual(code, 1)
        self.assertIn("not under chaos mode", out)
        self.assertIn("tests/test_013.py", self.read_lock()["files"])


class GitTests(ChaosCase):
    USE_GIT = False

    def test_R020_06_no_git_exit_2(self):
        code, _ = run_cli("chaos", "approve", "012", "approved", "--review", self.review(SPEC_PASS))
        self.assertEqual(code, 2)
        code, _ = run_cli("chaos", "unfreeze", "tests/x.py", "--reason", "wrong fixture",
                          "--auditor-review", self.review(SPEC_PASS),
                          "--impl-review", self.review(SPEC_PASS, name="i"))
        self.assertEqual(code, 2)
        code, _ = run_cli("chaos", "clear", "--all", "--note", "looked at it")
        self.assertEqual(code, 2)
        self.assertFalse(self.chaos_log.exists())

    def test_R020_06_api_raises_usage_error(self):
        with self.assertRaises(chaos.ChaosUsageError):
            chaos.approve(self.cfg(), "012", "approved", review=self.review(SPEC_PASS))
        with self.assertRaises(chaos.ChaosUsageError):
            chaos.clear(self.cfg(), all_open=True, note="looked at it", confirm=lambda p, e: True)


class BaseCommitTests(ChaosCase):

    def test_R020_06_no_commit_touching_config(self):
        # A fresh repository whose only commit does not contain agentkit.toml.
        self.git("checkout", "-q", "--orphan", "other")
        self.git("rm", "-rq", "--cached", ".")
        self.write("README.md", "readme\n")
        self.git("add", "README.md")
        self.git("commit", "-q", "--no-verify", "-m", "readme only")
        code, out = run_cli("chaos", "approve", "012", "approved", "--review", self.review(SPEC_PASS))
        self.assertEqual(code, 2)
        self.assertIn("agentkit.toml", out)
        self.assertFalse(self.chaos_log.exists())

    def test_R020_06_no_commit_at_all(self):
        self.git("checkout", "-q", "--orphan", "empty")
        self.git("rm", "-rq", "--cached", ".")
        code, _ = run_cli("chaos", "approve", "012", "approved", "--review", self.review(FAIL))
        self.assertEqual(code, 2)
        self.assertFalse(self.chaos_log.exists())
