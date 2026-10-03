"""Spec 002: loading the lock, `lock verify` and `lock status`."""
from __future__ import annotations

import json

from agentkit.lock import LockError, load_lock, status, verify
from tests.support import RepoTestCase, run_cli


def kinds(violations):
    return sorted((v.path, v.kind) for v in violations)


class LoadLockTests(RepoTestCase):

    BAD = {
        "json": "{not json\n",
        "files": json.dumps({"version": 1, "algorithm": "sha256-lf"}) + "\n",
        "algorithm": json.dumps({"version": 1, "algorithm": "md5", "files": {}}) + "\n",
    }

    def test_R002_04_invalid_lock_raises(self):
        for problem, text in self.BAD.items():
            with self.subTest(problem=problem):
                self.lock_file.write_text(text, encoding="utf-8")
                with self.assertRaises(LockError) as ctx:
                    load_lock(self.cfg())
                self.assertIn(problem, str(ctx.exception).lower())

    def test_R002_04_lock_commands_exit_1_naming_the_problem(self):
        for problem, text in self.BAD.items():
            for command in ("verify", "status"):
                with self.subTest(problem=problem, command=command):
                    self.lock_file.write_text(text, encoding="utf-8")
                    code, out = run_cli("lock", command)
                    self.assertEqual(code, 1)
                    self.assertIn(problem, out.lower())

    def test_R002_05_missing_lock_is_empty(self):
        self.assertEqual(load_lock(self.cfg()).get("files"), {})
        self.assertEqual(verify(self.cfg()), [])
        code, _ = run_cli("lock", "verify")
        self.assertEqual(code, 0)

    def test_R002_05_empty_lock_file_is_empty(self):
        self.lock_file.write_bytes(b"")
        self.assertEqual(load_lock(self.cfg()).get("files"), {})
        self.assertEqual(verify(self.cfg()), [])


class VerifyTests(RepoTestCase):

    def setUp(self):
        super().setUp()
        for name in ("a", "b", "c"):
            self.write(f"tests/{name}.txt", f"{name}\n")
        self.write_lock(["tests/a.txt", "tests/b.txt", "tests/c.txt"])

    def test_R002_16_clean_tree(self):
        self.assertEqual(verify(self.cfg()), [])
        code, out = run_cli("lock", "verify")
        self.assertEqual(code, 0)
        self.assertRegex(out, r"\b3\b")

    def test_R002_16_reports_missing_and_modified(self):
        self.write("tests/b.txt", "changed\n")
        (self.root / "tests/c.txt").unlink()
        self.assertEqual(kinds(verify(self.cfg())),
                         [("tests/b.txt", "modified"), ("tests/c.txt", "missing")])
        code, out = run_cli("lock", "verify")
        self.assertEqual(code, 1)
        self.assertIn("tests/b.txt", out)
        self.assertIn("tests/c.txt", out)
        self.assertNotIn("tests/a.txt", out)

    def test_R002_03_line_ending_change_is_not_a_violation(self):
        self.write("tests/a.txt", b"a\r\n")
        self.assertEqual(verify(self.cfg()), [])


class StagedVerifyTests(RepoTestCase):

    def setUp(self):
        super().setUp()
        self.write("tests/a.txt", "v1\n")
        self.write_lock(["tests/a.txt"])
        self.commit_all()

    def test_R002_17_unstaged_change_is_ignored(self):
        self.write("tests/a.txt", "v2\n")
        self.assertEqual(verify(self.cfg(), staged=True), [])
        self.assertEqual(kinds(verify(self.cfg())), [("tests/a.txt", "modified")])

    def test_R002_17_staged_change_is_reported(self):
        self.write("tests/a.txt", "v2\n")
        self.git("add", "tests/a.txt")
        self.assertEqual(kinds(verify(self.cfg(), staged=True)), [("tests/a.txt", "modified")])
        code, _ = run_cli("lock", "verify", "--staged")
        self.assertEqual(code, 1)

    def test_R002_17_lock_is_read_from_the_index(self):
        self.write("tests/a.txt", "v2\n")
        self.git("add", "tests/a.txt")
        self.write_lock(["tests/a.txt"])  # worktree lock re-hashed, not staged
        self.assertEqual(kinds(verify(self.cfg(), staged=True)), [("tests/a.txt", "modified")])

    def test_R002_17_file_removed_from_index_is_missing(self):
        self.git("rm", "-q", "--cached", "tests/a.txt")
        self.assertEqual(kinds(verify(self.cfg(), staged=True)), [("tests/a.txt", "missing")])


class StatusTests(RepoTestCase):

    def setUp(self):
        super().setUp()
        self.write("tests/s1.txt")
        self.write("tests/s2.txt")
        self.write("tests/free.txt")
        self.write_lock({"tests/s1.txt": "004", "tests/s2.txt": "004", "tests/free.txt": None})
        self.write("tests/s2.txt", "modified\n")
        self.unfrozen = [f"tests/u{i:02d}.txt" for i in range(25)]
        for path in self.unfrozen:
            self.write(path)

    def test_R002_18_status_dict(self):
        s = status(self.cfg())
        frozen = s["frozen"] if isinstance(s["frozen"], int) else len(s["frozen"])
        self.assertEqual(frozen, 3)
        self.assertEqual(s["by_spec"].get("004"), 2)
        self.assertEqual(sorted(s["unfrozen_candidates"]), self.unfrozen)
        self.assertEqual(kinds(s["violations"]), [("tests/s2.txt", "modified")])

    def test_R002_18_status_command_caps_the_list(self):
        _, out = run_cli("lock", "status")
        listed = [u for u in self.unfrozen if u in out]
        self.assertLessEqual(len(listed), 20)
        self.assertGreater(len(listed), 0)
        self.assertRegex(out, r"\b25\b")
        self.assertRegex(out, r"\b3\b")
        self.assertIn("004", out)
        self.assertIn("tests/s2.txt", out)
