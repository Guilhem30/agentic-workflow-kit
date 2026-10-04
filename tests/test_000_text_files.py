"""Spec 000: every text file agentkit writes is UTF-8 with LF line endings (R000-07).

The commands run in a child Python whose locale encoding is not UTF-8 (`-X utf8=0`, and the C
locale on POSIX; the ANSI code page on Windows), so a file opened without an explicit encoding,
or in text mode with platform newlines, shows up. The arguments reach `cli.main` as JSON with
ASCII escapes, because the C locale cannot decode a non-ASCII command line. Console output
stays UTF-8 through PYTHONIOENCODING: only files are under test."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests.process_fixtures import KIT_ROOT, PY, clean_env, run_python, written_files
from tests.support import FIXTURE_PROFILE, RepoTestCase

TITLE = "Café crème — naïve ✓"
NOTE = "résumé: ünïcode ✓ “quoted”"
NEXT = "écrire la suite → ok"

# Test output: UTF-8 text, CRLF and lone CR line endings, and one byte that is not UTF-8.
EMIT = ('import sys\n'
        'sys.stdout.buffer.write(b"caf\\xc3\\xa9 \\xe2\\x9c\\x93 MARK-1\\r\\nMARK-2\\rMARK-3\\r\\n'
        '\\xff MARK-4\\n")\n')


BINARY_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz", ".woff",
                   ".woff2", ".pyc")

DRIVER = "import json, sys; from agentkit.cli import main; sys.exit(main(json.loads(sys.argv[1])))"


def run_legacy(cwd: Path, *args: str):
    """agentkit <args> in a child Python with a non-UTF-8 locale encoding."""
    env = clean_env(PYTHONPATH=str(KIT_ROOT), LC_ALL="C", LANG="C", LC_CTYPE=None,
                    PYTHONCOERCECLOCALE="0", PYTHONIOENCODING="utf-8")
    return run_python(["-X", "utf8=0", "-c", DRIVER, json.dumps(list(args))], cwd, env)


class TextFileCase(RepoTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.write(".agentkit/profiles/fixture.toml",
                   FIXTURE_PROFILE
                   + 'test_globs = ["tests/**/*.py"]\nsource_globs = ["src/**/*.py"]\n'
                   + f"test_cmd = '{PY} emit.py'\n"
                   + "\n[codemap]\nsymbol_regexes = ['^def (?P<name>\\w+)']\n")
        self.write("emit.py", EMIT)
        self.write("src/mod.py", "def café():\n    return 1\n")
        self.write("src/crlf.py", b"def windows_style():\r\n    return 2\r\n")
        self.write("tests/test_050_x.py", "import unittest\n")
        self.commit_all()

    def kit(self, *args: str, expect: int | None = 0):
        before = written_files(self.root)
        proc = run_legacy(self.root, *args)
        if expect is not None:
            self.assertEqual(proc.returncode, expect, proc.stdout + proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        return written_files(self.root, before)

    def assertUtf8Lf(self, files: dict[str, bytes]) -> dict[str, str]:
        """Every file decodes as UTF-8 (no BOM) and has no CR; returns the decoded texts."""
        texts = {}
        for rel, data in files.items():
            with self.subTest(file=rel):
                self.assertFalse(data.startswith(b"\xef\xbb\xbf"), "BOM")
                self.assertNotIn(b"\r", data)
                texts[rel] = data.decode("utf-8")
        return texts


class SpecFileTests(TextFileCase):

    def test_R000_07_new_spec_files(self):
        files = self.kit("new-spec", "050", "unicode-check", "--title", TITLE)
        self.assertTrue(files)
        texts = self.assertUtf8Lf(files)
        self.assertIn(TITLE, texts["specs/050-unicode-check/spec.md"])

    def test_R000_07_status_change_keeps_utf8(self):
        self.kit("new-spec", "050", "unicode-check", "--title", TITLE)
        files = self.kit("spec-status", "050", "dropped")
        texts = self.assertUtf8Lf(files)
        self.assertIn(TITLE, texts["specs/050-unicode-check/spec.md"])

    def test_R000_07_handoff_snapshot(self):
        self.kit("new-spec", "050", "unicode-check", "--title", TITLE)
        files = self.kit("handoff", "050", "--note", NOTE, "--next", NEXT)
        texts = self.assertUtf8Lf(files)
        progress = texts["specs/050-unicode-check/progress.md"]
        self.assertIn(NOTE, progress)
        self.assertIn(NEXT, progress)


class GeneratedFileTests(TextFileCase):

    def test_R000_07_codemap(self):
        files = self.kit("codemap")
        texts = self.assertUtf8Lf(files)
        self.assertIn("café", texts["docs/CODEMAP.md"])
        self.assertIn("windows_style", texts["docs/CODEMAP.md"])

    def test_R000_07_lock_file(self):
        files = self.kit("lock", "freeze", "tests/test_050_x.py")
        self.assertIn("tests.lock.json", files)
        self.assertUtf8Lf(files)

    def test_R000_07_test_log(self):
        files = self.kit("test", expect=None)
        data = files[".agentkit/state/last-test.log"]
        self.assertNotIn(b"\r", data)
        log = data.decode("utf-8")
        self.assertIn("café ✓ MARK-1\n", log)
        for mark in ("MARK-2", "MARK-3", "MARK-4"):
            self.assertIn(mark, log)


class InstallTests(TextFileCase):

    def test_R000_07_installed_files(self):
        target = self.tmp / "target"
        target.mkdir()
        proc = run_legacy(self.tmp, "install", "--target", str(target), "--ci", "github",
                          "--ci-os", "linux,windows,macos", "--models", "kit", "--owner", "@owner")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        files = {rel: data for rel, data in written_files(target).items()
                 if not rel.lower().endswith(BINARY_SUFFIXES)}
        self.assertIn("agentkit.toml", files)
        self.assertIn(".agentkit/bin/agentkit", files)
        self.assertIn(".agentkit/bin/agentkit.cmd", files)
        texts = self.assertUtf8Lf(files)
        self.assertIn("@owner", texts[".github/CODEOWNERS"])


if __name__ == "__main__":
    unittest.main()
