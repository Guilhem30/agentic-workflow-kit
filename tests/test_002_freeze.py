"""Spec 002: lock file format and `lock freeze`."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

from agentkit.lock import LockError, OwnerCheckError, freeze
from tests.support import RepoTestCase, rid, run_cli, sha256_lf

NOW = datetime(2026, 10, 3, 12, 34, 56, tzinfo=timezone.utc)


class LockFormatTests(RepoTestCase):

    def test_R002_01_lock_structure(self):
        self.write("tests/unit/a.txt", "a\n")
        freeze(self.cfg(), paths=["tests/unit/a.txt"])
        data = self.read_lock()
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["algorithm"], "sha256-lf")
        self.assertEqual(data["files"], {"tests/unit/a.txt": {"sha256": sha256_lf(b"a\n")}})

    def test_R002_02_deterministic_output(self):
        for name in ("tests/z.txt", "tests/a.txt", "tests/m/b.txt"):
            self.write(name, name + "\n")
        freeze(self.cfg(), paths=["tests/z.txt", "tests/a.txt", "tests/m/b.txt"])
        raw = self.lock_file.read_bytes()
        self.assertNotIn(b"\r", raw)
        data = json.loads(raw)
        self.assertEqual(list(data["files"]), sorted(data["files"]))
        self.assertEqual(raw.decode("utf-8"), json.dumps(data, indent=2) + "\n")

    def test_R002_02_same_files_same_bytes_whatever_the_order(self):
        for name in ("tests/z.txt", "tests/a.txt"):
            self.write(name, name + "\n")
        freeze(self.cfg(), paths=["tests/z.txt"])
        freeze(self.cfg(), paths=["tests/a.txt"])
        first = self.lock_file.read_bytes()
        self.lock_file.unlink()
        freeze(self.cfg(), paths=["tests/a.txt", "tests/z.txt"])
        self.assertEqual(self.lock_file.read_bytes(), first)

    def test_R002_03_crlf_and_lf_hash_the_same(self):
        self.write("tests/crlf.txt", b"a\r\nb\r\n")
        self.write("tests/lf.txt", b"a\nb\n")
        self.write("tests/cr.txt", b"a\rb")
        freeze(self.cfg(), paths=["tests/crlf.txt", "tests/lf.txt", "tests/cr.txt"])
        files = self.read_lock()["files"]
        lf_hash = hashlib.sha256(b"a\nb\n").hexdigest()
        self.assertEqual(files["tests/crlf.txt"]["sha256"], lf_hash)
        self.assertEqual(files["tests/lf.txt"]["sha256"], lf_hash)
        self.assertEqual(files["tests/cr.txt"]["sha256"], hashlib.sha256(b"a\rb").hexdigest())


class FreezePathsTests(RepoTestCase):

    def test_R002_06_freeze_given_files(self):
        self.write("tests/a.txt")
        self.write("docs/notes.md")
        result = freeze(self.cfg(), paths=["tests/a.txt", "docs/notes.md"])
        self.assertEqual(sorted(result.added), ["docs/notes.md", "tests/a.txt"])
        self.assertEqual(sorted(self.read_lock()["files"]), ["docs/notes.md", "tests/a.txt"])

    def test_R002_06_directory_freezes_matching_files_only(self):
        self.write("core/model/src/test/kotlin/EngineTest.kt")
        self.write("core/model/src/test/golden/ring.txt")
        self.write("core/model/src/main/Engine.kt")
        self.write("core/model/build/out.kt")
        result = freeze(self.cfg(), paths=["core/model"])
        expected = ["core/model/src/test/golden/ring.txt", "core/model/src/test/kotlin/EngineTest.kt"]
        self.assertEqual(sorted(result.added), expected)
        self.assertEqual(sorted(self.read_lock()["files"]), expected)

    def test_R002_06_directory_with_trailing_slash(self):
        self.write("core/model/src/test/kotlin/EngineTest.kt")
        result = freeze(self.cfg(), paths=["core/model/src/test/"])
        self.assertEqual(result.added, ["core/model/src/test/kotlin/EngineTest.kt"])

    def test_R002_06_directory_skips_build_output_and_ignored_files(self):
        self.write(".gitignore", "core/model/src/test/tmp/\n")
        self.write("core/model/src/test/kotlin/EngineTest.kt")
        self.write("core/model/src/test/build/Generated.kt")
        self.write("core/model/src/test/tmp/scratch.kt")
        result = freeze(self.cfg(), paths=["core/model/src/test"])
        self.assertEqual(result.added, ["core/model/src/test/kotlin/EngineTest.kt"])

    def test_R002_10_already_frozen_same_hash_is_unchanged(self):
        self.write("tests/a.txt")
        freeze(self.cfg(), paths=["tests/a.txt"])
        before = self.lock_file.read_bytes()
        result = freeze(self.cfg(), paths=["tests/a.txt"])
        self.assertEqual(result.added, [])
        self.assertEqual(result.unchanged, ["tests/a.txt"])
        self.assertEqual(result.errors, [])
        self.assertEqual(self.lock_file.read_bytes(), before)


class FreezeErrorTests(RepoTestCase):

    def setUp(self):
        super().setUp()
        self.write("tests/good.txt")
        self.write("tests/a.txt", "v1\n")
        self.write("tests.unfreeze-log.md", "# log\n")
        self.write_lock(["tests/a.txt"])
        self.outside = self.write(self.tmp / "outside.txt")

    def assert_rejected(self, bad, needle):
        before = self.snapshot(self.lock_file)
        result = freeze(self.cfg(), paths=["tests/good.txt", bad])
        self.assertTrue(result.errors)
        self.assertIn(needle, "\n".join(result.errors))
        self.assertEqual(self.snapshot(self.lock_file), before)

    def test_R002_11_modified_frozen_file(self):
        self.write("tests/a.txt", "v2\n")
        self.assert_rejected("tests/a.txt", "tests/a.txt")

    def test_R002_11_the_lock_itself(self):
        self.assert_rejected("tests.lock.json", "tests.lock.json")

    def test_R002_11_the_unfreeze_log(self):
        self.assert_rejected("tests.unfreeze-log.md", "tests.unfreeze-log.md")

    def test_R002_11_outside_the_repository(self):
        self.assert_rejected(str(self.outside), "outside.txt")

    def test_R002_11_missing_file(self):
        self.assert_rejected("tests/nope.txt", "nope.txt")

    def test_R002_11_lists_every_problem_and_writes_nothing(self):
        self.write("tests/a.txt", "v2\n")
        before = self.snapshot(self.lock_file)
        bad = ["tests/a.txt", "tests.lock.json", "tests.unfreeze-log.md", str(self.outside),
               "tests/nope.txt"]
        result = freeze(self.cfg(), paths=["tests/good.txt", *bad])
        joined = "\n".join(result.errors)
        self.assertGreaterEqual(len(result.errors), 5)
        for needle in ("tests/a.txt", "tests.lock.json", "tests.unfreeze-log.md", "outside.txt",
                       "nope.txt"):
            with self.subTest(needle=needle):
                self.assertIn(needle, joined)
        self.assertEqual(self.snapshot(self.lock_file), before)

    def test_R002_11_command_exits_1(self):
        before = self.snapshot(self.lock_file)
        code, out = run_cli("lock", "freeze", "tests/good.txt", "tests/nope.txt")
        self.assertEqual(code, 1)
        self.assertIn("nope.txt", out)
        self.assertEqual(self.snapshot(self.lock_file), before)

    def test_R002_14_freeze_without_target_exits_2(self):
        before = self.snapshot(self.lock_file)
        code, _ = run_cli("lock", "freeze")
        self.assertEqual(code, 2)
        self.assertEqual(self.snapshot(self.lock_file), before)


class FreezeSpecTests(RepoTestCase):
    """The --spec / --all candidate rules, on a git repository with tracked, untracked and
    ignored files."""

    def setUp(self):
        super().setUp()
        own, other = rid("004", "02"), rid("005", "01")
        self.write_spec("004", "tests-approved", slug="rules")
        self.write(".gitignore", "tests/ignored/\n")
        self.write("fixtures/004-rules/a.json", "{}\n")          # path segment NNN-*, tracked
        self.commit_all()
        self.write("rules/src/test/R004EngineTest.kt", f"// {own}\n")  # contains an ID, untracked
        self.write("fixtures/004/b.json", "{}\n")                 # path segment NNN
        self.write("tests/underscore.txt", "def test_" + rid("004", "03", "_") + "_x(): pass\n")
        self.write("fixtures/0040/x.json", "{}\n")                # not a segment match
        self.write("tests/other.txt", f"{other}\n")               # another spec
        self.write("tests/plain.txt", "no id\n")                   # no spec
        self.write("tests/ignored/x.txt", f"{own}\n")             # git-ignored
        self.write("tests/build/gen.txt", f"{own}\n")             # build output
        self.write("docs/r.md", f"{own}\n")                       # not in frozen_globs
        self.write("tests/already.txt", f"{own}\n")
        self.write_lock(["tests/already.txt"])

    SPEC_004 = ["fixtures/004-rules/a.json", "fixtures/004/b.json",
                "rules/src/test/R004EngineTest.kt", "tests/underscore.txt"]

    def test_R002_07_spec_candidates(self):
        result = freeze(self.cfg(), spec="004")
        self.assertEqual(sorted(result.added), self.SPEC_004)
        self.assertEqual(sorted(self.read_lock()["files"]), sorted(self.SPEC_004 + ["tests/already.txt"]))

    def test_R002_08_all_candidates(self):
        result = freeze(self.cfg(), all_candidates=True)
        expected = sorted(self.SPEC_004 + ["fixtures/0040/x.json", "tests/other.txt",
                                           "tests/plain.txt"])
        self.assertEqual(sorted(result.added), expected)

    def test_R002_09_spec_recorded_on_new_entries(self):
        freeze(self.cfg(), spec="004")
        files = self.read_lock()["files"]
        for path in self.SPEC_004:
            with self.subTest(path=path):
                self.assertEqual(files[path]["spec"], "004")
                self.assertEqual(files[path]["sha256"], sha256_lf((self.root / path).read_bytes()))

    def test_R002_09_no_spec_key_without_spec_option(self):
        freeze(self.cfg(), paths=["tests/plain.txt"])
        self.assertNotIn("spec", self.read_lock()["files"]["tests/plain.txt"])

    def test_R002_12_refuses_unless_tests_approved(self):
        for status in ("approved", "frozen"):
            with self.subTest(status=status):
                self.write_spec("004", status, slug="rules")
                before = self.snapshot(self.lock_file)
                code, out = run_cli("lock", "freeze", "--spec", "004")
                self.assertEqual(code, 1)
                self.assertRegex(out, rf"(?<!tests-)\b{status}\b")
                self.assertEqual(self.snapshot(self.lock_file), before)
                self.assertEqual(self.spec_status("004", slug="rules"), status)

    def test_R002_12_unknown_spec(self):
        before = self.snapshot(self.lock_file)
        code, out = run_cli("lock", "freeze", "--spec", "999")
        self.assertEqual(code, 1)
        self.assertIn("999", out)
        self.assertEqual(self.snapshot(self.lock_file), before)

    def test_R002_12_api_raises(self):
        self.write_spec("004", "approved", slug="rules")
        before = self.snapshot(self.lock_file)
        with self.assertRaises(LockError) as ctx:
            freeze(self.cfg(), spec="004")
        self.assertNotIsInstance(ctx.exception, OwnerCheckError)
        self.assertEqual(self.snapshot(self.lock_file), before)

    def test_R002_13_api_sets_status_frozen(self):
        freeze(self.cfg(), spec="004")
        self.assertEqual(self.spec_status("004", slug="rules"), "frozen")

    def test_R002_13_success_sets_status_frozen(self):
        spec_file = self.root / "specs/004-rules/spec.md"
        before = spec_file.read_text(encoding="utf-8")
        code, _ = run_cli("lock", "freeze", "--spec", "004")
        self.assertEqual(code, 0)
        self.assertEqual(self.spec_status("004", slug="rules"), "frozen")
        self.assertEqual(spec_file.read_text(encoding="utf-8"),
                         before.replace("status: tests-approved", "status: frozen"))
        self.assertIn("tests/underscore.txt", self.read_lock()["files"])

    def test_R002_31_force_refused_in_agent_environment(self):
        self.write_spec("004", "approved", slug="rules")
        os.environ["AGENTKIT_AGENT"] = "1"
        before = self.snapshot(self.lock_file)
        code, out = run_cli("lock", "freeze", "--spec", "004", "--force")
        self.assertEqual(code, 2)
        self.assertIn("AGENTKIT_AGENT", out)
        self.assertEqual(self.snapshot(self.lock_file), before)
        self.assertEqual(self.spec_status("004", slug="rules"), "approved")

    def test_R002_31_api_checks_agent_environment_itself(self):
        self.write_spec("004", "approved", slug="rules")
        os.environ["CODEX_SANDBOX"] = "seatbelt"
        asked = []
        before = self.snapshot(self.lock_file)
        with self.assertRaises(OwnerCheckError) as ctx:
            freeze(self.cfg(), spec="004", force=True,
                   confirm=lambda p, e: asked.append(e) or True, user="Alice", now=NOW)
        self.assertIn("CODEX_SANDBOX", str(ctx.exception))
        self.assertEqual(asked, [])
        self.assertEqual(self.snapshot(self.lock_file), before)

    def test_R002_31_force_requires_exact_confirmation(self):
        self.write_spec("004", "approved", slug="rules")
        asked = []
        before = self.snapshot(self.lock_file)
        try:
            freeze(self.cfg(), spec="004", force=True,
                   confirm=lambda prompt, expected: asked.append(expected) or False)
        except LockError:
            pass
        self.assertEqual(asked, ["force freeze 004"])
        self.assertEqual(self.snapshot(self.lock_file), before)
        self.assertFalse(self.log_file.exists())

    def test_R002_31_force_bypasses_status_when_confirmed(self):
        self.write_spec("004", "approved", slug="rules")
        result = freeze(self.cfg(), spec="004", force=True, confirm=lambda p, e: True,
                        user="Alice", now=NOW)
        self.assertEqual(sorted(result.added), self.SPEC_004)

    def test_R002_32_forced_freeze_is_logged(self):
        self.write_spec("004", "approved", slug="rules")
        freeze(self.cfg(), spec="004", force=True, confirm=lambda p, e: True, user="Alice", now=NOW)
        log = self.log_file.read_text(encoding="utf-8")
        entry = ("\n\n## 2026-10-03T12:34:56Z - Alice\n"
                 "forced freeze of spec 004 (status was approved)\n"
                 + "".join(f"- {p}\n" for p in self.SPEC_004))
        self.assertIn(entry, log)


class NonGitTests(RepoTestCase):
    USE_GIT = False
    REST = "[profile]\nbuild_output_globs = []\n"

    def test_R002_15_walk_skips_tool_directories(self):
        self.write("tests/a.txt")
        for skipped in (".git", "node_modules", "__pycache__", ".gradle"):
            self.write(f"tests/{skipped}/x.txt")
        result = freeze(self.cfg(), all_candidates=True)
        self.assertEqual(result.added, ["tests/a.txt"])
