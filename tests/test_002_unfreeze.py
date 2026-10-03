"""Spec 002: owner-only `lock unfreeze` and the unfreeze log."""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone

from agentkit.lock import LockError, human_check, unfreeze
from tests.support import AGENT_ENV_VARS, RepoTestCase, run_cli

NOW = datetime(2026, 10, 3, 12, 34, 56, tzinfo=timezone.utc)
LATER = datetime(2026, 10, 4, 8, 0, 0, tzinfo=timezone.utc)


def yes(prompt, expected):
    return True


class UnfreezeTests(RepoTestCase):

    def setUp(self):
        super().setUp()
        for path in ("tests/a.txt", "tests/b.txt", "tests/sub/c.txt", "tests/keep.txt"):
            self.write(path, path + "\n")
        self.write("tests/notfrozen.txt")
        self.write("docs/readme.md")
        self.write_lock(["tests/a.txt", "tests/b.txt", "tests/sub/c.txt", "tests/keep.txt"])
        self.lock_before = self.lock_file.read_bytes()

    def assert_nothing_changed(self):
        self.assertEqual(self.lock_file.read_bytes(), self.lock_before)
        self.assertFalse(self.log_file.exists())

    def test_R002_19_reason_too_short(self):
        for reason in ("", "abc", "    ", "\t\n  \n"):
            with self.subTest(reason=reason):
                with self.assertRaises(LockError):
                    unfreeze(self.cfg(), ["tests/a.txt"], reason, confirm=yes, user="Alice", now=NOW)
                self.assert_nothing_changed()

    def test_R002_19_reason_long_enough(self):
        self.assertEqual(unfreeze(self.cfg(), ["tests/a.txt"], "fixed", confirm=yes, user="Alice",
                                  now=NOW), ["tests/a.txt"])

    def test_R002_20_agent_variables_detected(self):
        self.assertIsNone(human_check())
        for name in AGENT_ENV_VARS:
            with self.subTest(var=name):
                os.environ[name] = "1"
                try:
                    reason = human_check()
                    self.assertIsNotNone(reason)
                    self.assertIn(name, reason)
                finally:
                    del os.environ[name]

    def test_R002_20_empty_variable_is_ignored(self):
        for name in AGENT_ENV_VARS:
            os.environ[name] = ""
        self.assertIsNone(human_check())

    def test_R002_20_command_refuses_in_agent_environment(self):
        os.environ["CLAUDECODE"] = "1"
        code, out = run_cli("lock", "unfreeze", "tests/a.txt", "--reason", "flaky fixture")
        self.assertEqual(code, 2)
        self.assertIn("CLAUDECODE", out)
        self.assert_nothing_changed()

    def test_R002_21_confirmation_shows_files_and_expects_count(self):
        asked = []
        def confirm(prompt, expected):
            asked.append((prompt, expected))
            return True
        unfreeze(self.cfg(), ["tests/a.txt", "tests/b.txt"], "flaky fixture", confirm=confirm,
                 user="Alice", now=NOW)
        self.assertEqual(len(asked), 1)
        prompt, expected = asked[0]
        self.assertEqual(expected, "unfreeze 2")
        self.assertIn("tests/a.txt", prompt)
        self.assertIn("tests/b.txt", prompt)

    def test_R002_21_count_covers_directory_contents(self):
        asked = []
        unfreeze(self.cfg(), ["tests/sub"], "flaky fixture",
                 confirm=lambda p, e: asked.append(e) or True, user="Alice", now=NOW)
        self.assertEqual(asked, ["unfreeze 1"])

    def test_R002_22_declined_confirmation_changes_nothing(self):
        with self.assertRaises(LockError):
            unfreeze(self.cfg(), ["tests/a.txt"], "flaky fixture", confirm=lambda p, e: False,
                     user="Alice", now=NOW)
        self.assert_nothing_changed()

    def test_R002_23_path_not_frozen(self):
        with self.assertRaises(LockError):
            unfreeze(self.cfg(), ["tests/a.txt", "tests/notfrozen.txt"], "flaky fixture",
                     confirm=yes, user="Alice", now=NOW)
        self.assert_nothing_changed()

    def test_R002_23_directory_without_frozen_files(self):
        with self.assertRaises(LockError):
            unfreeze(self.cfg(), ["docs"], "flaky fixture", confirm=yes, user="Alice", now=NOW)
        self.assert_nothing_changed()

    def test_R002_24_removes_entries_and_logs(self):
        removed = unfreeze(self.cfg(), ["tests/a.txt", "tests/b.txt"], "flaky fixture",
                           confirm=yes, user="Alice", now=NOW)
        self.assertEqual(sorted(removed), ["tests/a.txt", "tests/b.txt"])
        self.assertEqual(sorted(self.read_lock()["files"]), ["tests/keep.txt", "tests/sub/c.txt"])
        log = self.log_file.read_text(encoding="utf-8")
        self.assertIn("## 2026-10-03T12:34:56Z - Alice\n"
                      "reason: flaky fixture\n"
                      "- tests/a.txt\n"
                      "- tests/b.txt\n", log)

    def test_R002_24_directory_unfreezes_its_frozen_files(self):
        removed = unfreeze(self.cfg(), ["tests/sub"], "flaky fixture", confirm=yes, user="Alice",
                           now=NOW)
        self.assertEqual(removed, ["tests/sub/c.txt"])
        self.assertNotIn("tests/sub/c.txt", self.read_lock()["files"])

    def test_R002_24_defaults_to_git_user_and_current_time(self):
        unfreeze(self.cfg(), ["tests/a.txt"], "flaky fixture", confirm=yes)
        log = self.log_file.read_text(encoding="utf-8")
        self.assertRegex(log, r"(?m)^## \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ - Fixture Owner$")

    def test_R002_25_new_log_starts_with_append_only_header(self):
        unfreeze(self.cfg(), ["tests/a.txt"], "flaky fixture", confirm=yes, user="Alice", now=NOW)
        log = self.log_file.read_text(encoding="utf-8")
        header = log.split("\n## ", 1)[0]
        self.assertFalse(log.startswith("## "))
        self.assertRegex(header.lower(), r"append[- ]only")

    def test_R002_25_earlier_entries_kept_verbatim(self):
        unfreeze(self.cfg(), ["tests/a.txt"], "first reason", confirm=yes, user="Alice", now=NOW)
        first = self.log_file.read_bytes()
        unfreeze(self.cfg(), ["tests/b.txt"], "second reason", confirm=yes, user="Bob", now=LATER)
        second = self.log_file.read_bytes()
        self.assertTrue(second.startswith(first))
        self.assertIn(b"## 2026-10-04T08:00:00Z - Bob\n", second)

    def test_R002_25_existing_log_is_appended_to(self):
        existing = "# Unfreeze log\n\nAppend-only. Owner notes here.\n"
        self.write("tests.unfreeze-log.md", existing)
        unfreeze(self.cfg(), ["tests/a.txt"], "flaky fixture", confirm=yes, user="Alice", now=NOW)
        log = self.log_file.read_text(encoding="utf-8")
        self.assertTrue(log.startswith(existing))
        self.assertEqual(len(re.findall(r"(?m)^## ", log)), 1)
