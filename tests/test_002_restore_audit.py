"""Spec 002: `lock restore` and `lock audit`."""
from __future__ import annotations

import json

from agentkit.lock import audit, restore
from tests.support import LOG_HEADER, RepoTestCase, run_cli


class RestoreTests(RepoTestCase):

    def setUp(self):
        super().setUp()
        self.write("tests/a.txt", "a1\n")
        self.write("tests/b.txt", "b1\n")
        self.write_lock(["tests/a.txt", "tests/b.txt"])
        self.first = self.commit_all("freeze")

    def test_R002_26_restores_modified_and_missing(self):
        self.write("tests/a.txt", "hacked\n")
        (self.root / "tests/b.txt").unlink()
        restored, failed = restore(self.cfg())
        self.assertEqual(sorted(restored), ["tests/a.txt", "tests/b.txt"])
        self.assertEqual(failed, [])
        self.assertEqual((self.root / "tests/a.txt").read_bytes(), b"a1\n")
        self.assertEqual((self.root / "tests/b.txt").read_bytes(), b"b1\n")

    def test_R002_26_only_given_paths(self):
        self.write("tests/a.txt", "hacked\n")
        self.write("tests/b.txt", "hacked\n")
        restored, _ = restore(self.cfg(), paths=["tests/a.txt"])
        self.assertEqual(restored, ["tests/a.txt"])
        self.assertEqual((self.root / "tests/b.txt").read_bytes(), b"hacked\n")

    def test_R002_26_refuses_content_that_does_not_match_the_lock(self):
        self.write("tests/a.txt", "a2\n")
        self.commit_all("edit frozen file")  # HEAD content no longer matches the lock
        self.write("tests/a.txt", "a3\n")
        restored, failed = restore(self.cfg())
        self.assertEqual(restored, [])
        self.assertEqual(failed, ["tests/a.txt"])
        self.assertEqual((self.root / "tests/a.txt").read_bytes(), b"a3\n")
        code, out = run_cli("lock", "restore")
        self.assertEqual(code, 1)
        self.assertIn("tests/a.txt", out)

    def test_R002_26_ref_option(self):
        self.write("tests/a.txt", "a2\n")
        self.commit_all("edit frozen file")
        restored, failed = restore(self.cfg(), ref=self.first)
        self.assertEqual((restored, failed), (["tests/a.txt"], []))
        self.assertEqual((self.root / "tests/a.txt").read_bytes(), b"a1\n")

    def test_R002_26_command_succeeds_when_all_restored(self):
        self.write("tests/a.txt", "hacked\n")
        code, _ = run_cli("lock", "restore")
        self.assertEqual(code, 0)
        self.assertEqual((self.root / "tests/a.txt").read_bytes(), b"a1\n")


class AuditTests(RepoTestCase):

    OLD_ENTRY = "\n## 2026-01-01T00:00:00Z - Owner\nreason: old change\n- tests/a.txt\n"
    NEW_ENTRY = "\n## 2026-10-03T12:34:56Z - Owner\nreason: flaky fixture\n- tests/a.txt\n"

    def setUp(self):
        super().setUp()
        self.write("tests/a.txt", "a1\n")
        self.write("tests/b.txt", "b1\n")
        self.write_lock(["tests/a.txt", "tests/b.txt"])
        self.write("tests.unfreeze-log.md", LOG_HEADER)

    def drop_from_lock(self, path):
        data = self.read_lock()
        del data["files"][path]
        self.lock_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def append_log(self, text):
        with open(self.log_file, "a", encoding="utf-8", newline="") as f:
            f.write(text)

    def test_R002_27_removed_entry_without_log_entry(self):
        self.commit_all()
        self.drop_from_lock("tests/a.txt")
        problems = audit(self.cfg(), base="HEAD")
        self.assertTrue(problems)
        self.assertIn("tests/a.txt", "\n".join(problems))
        code, _ = run_cli("lock", "audit", "--base", "HEAD")
        self.assertEqual(code, 1)

    def test_R002_27_rehashed_entry(self):
        self.commit_all()
        self.write("tests/b.txt", "b2\n")
        self.write_lock(["tests/a.txt", "tests/b.txt"])
        problems = audit(self.cfg(), base="HEAD")
        self.assertIn("tests/b.txt", "\n".join(problems))

    def test_R002_27_removal_covered_by_new_log_entry(self):
        self.commit_all()
        self.drop_from_lock("tests/a.txt")
        self.append_log(self.NEW_ENTRY)
        self.assertEqual(audit(self.cfg(), base="HEAD"), [])
        code, _ = run_cli("lock", "audit", "--base", "HEAD")
        self.assertEqual(code, 0)

    def test_R002_27_log_entry_already_at_base_does_not_count(self):
        self.append_log(self.OLD_ENTRY)
        self.commit_all()
        self.drop_from_lock("tests/a.txt")
        self.assertTrue(audit(self.cfg(), base="HEAD"))

    def test_R002_27_new_log_entry_for_another_path_does_not_count(self):
        self.commit_all()
        self.drop_from_lock("tests/a.txt")
        self.append_log(self.NEW_ENTRY.replace("tests/a.txt", "tests/b.txt"))
        self.assertTrue(audit(self.cfg(), base="HEAD"))

    def test_R002_27_new_entries_are_fine(self):
        self.commit_all()
        self.write("tests/c.txt", "c1\n")
        self.write_lock(["tests/a.txt", "tests/b.txt", "tests/c.txt"])
        self.assertEqual(audit(self.cfg(), base="HEAD"), [])

    def test_R002_27_default_base_is_head(self):
        self.commit_all()
        self.drop_from_lock("tests/a.txt")
        self.assertTrue(audit(self.cfg()))

    def test_R002_28_rewritten_log(self):
        self.append_log(self.OLD_ENTRY)
        self.commit_all()
        self.log_file.write_text(LOG_HEADER + self.OLD_ENTRY.replace("old change", "edited"),
                                 encoding="utf-8")
        self.assertTrue(audit(self.cfg(), base="HEAD"))
        code, _ = run_cli("lock", "audit")
        self.assertEqual(code, 1)

    def test_R002_28_appended_log_is_fine(self):
        self.commit_all()
        self.append_log(self.NEW_ENTRY.replace("tests/a.txt", "tests/gone.txt"))
        self.assertEqual(audit(self.cfg(), base="HEAD"), [])

    def test_R002_29_base_without_commits(self):
        self.assertEqual(audit(self.cfg(), base="HEAD"), [])
        code, _ = run_cli("lock", "audit")
        self.assertEqual(code, 0)

    def test_R002_29_unknown_base_ref(self):
        self.commit_all()
        self.assertEqual(audit(self.cfg(), base="no-such-branch"), [])

    def test_R002_30_staged_reads_the_index(self):
        self.commit_all()
        self.drop_from_lock("tests/a.txt")  # worktree only
        self.assertEqual(audit(self.cfg(), base="HEAD", staged=True), [])
        self.git("add", "tests.lock.json")
        self.assertTrue(audit(self.cfg(), base="HEAD", staged=True))
        code, _ = run_cli("lock", "audit", "--staged")
        self.assertEqual(code, 1)

    def test_R002_30_staged_log_entry_is_used(self):
        self.commit_all()
        self.drop_from_lock("tests/a.txt")
        self.append_log(self.NEW_ENTRY)
        self.git("add", "tests.lock.json")
        self.assertTrue(audit(self.cfg(), base="HEAD", staged=True))  # log entry not staged
        self.git("add", "tests.unfreeze-log.md")
        self.assertEqual(audit(self.cfg(), base="HEAD", staged=True), [])
