"""Spec 008: `agentkit codemap`."""
from __future__ import annotations

import os
import unittest

from tests.support import FIXTURE_PROFILE, RepoTestCase, run_cli

PROFILE = (FIXTURE_PROFILE
           + 'source_globs = ["**/*.py"]\n'
           + 'build_output_globs = ["**/build/**"]\n'
           + "\n[codemap]\n"
           + "symbol_regexes = ['^def (?P<name>\\w+)', '^(class) (\\w+)']\n")

SRC_A = "def alpha():\n    return 1\n\n\nclass Beta:\n    def inner(self):\n        pass\n\n\ndef gamma():\n    pass\n"


class CodemapCase(RepoTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write(".agentkit/profiles/fixture.toml", PROFILE)

    @property
    def map_file(self):
        return self.root / "docs" / "CODEMAP.md"

    def build(self):
        from agentkit.codemap import build
        return build(self.cfg())

    def write_map(self):
        from agentkit.codemap import write
        return write(self.cfg())

    def entries(self, text=None):
        return [l for l in (text or self.build()).splitlines() if l.startswith("- ")]

    def headings(self, text=None):
        return [l for l in (text or self.build()).splitlines() if l.startswith("## ")]

    def commit(self):
        self.commit_all("files")


class TestContent(CodemapCase):
    def test_R008_01_selected_files(self):
        self.write("pkg/a.py", SRC_A)
        self.write("pkg/b.py", "def b():\n    pass\n")
        self.write("pkg/build/gen.py", "def bogus_sym():\n    pass\n")
        self.write(".agentkit/tool.py", "def hidden():\n    pass\n")
        self.write("docs/notes.md", "def not_source():\n")
        self.commit()
        text = self.build()
        self.assertIn("- a.py: alpha, Beta, gamma", self.entries(text))
        self.assertIn("- b.py: b", self.entries(text))
        entries = "\n".join(self.entries(text))
        for absent in ("gen.py", "bogus_sym", "tool.py", "hidden", "notes.md"):
            self.assertNotIn(absent, entries)

    def test_R008_01_ignored_files_skipped(self):
        self.write(".gitignore", "venv/\n")
        self.write("venv/lib/site.py", "def ignored_sym():\n    pass\n")
        self.write("kept.py", "def kept():\n    pass\n")
        self.commit()
        self.write("untracked.py", "def fresh():\n    pass\n")
        entries = self.entries()
        self.assertIn("- kept.py: kept", entries)
        self.assertIn("- untracked.py: fresh", entries)
        self.assertNotIn("ignored_sym", "\n".join(entries))

    def test_R008_02_name_group_not_last(self):
        self.write(".agentkit/profiles/fixture.toml", PROFILE.replace(
            "symbol_regexes = [", "symbol_regexes = ['^(?P<name>\\w+) = (lambda)', "))
        self.write("m.py", "handler = lambda x: x\n")
        self.commit()
        self.assertEqual(self.entries(), ["- m.py: handler"])

    def test_R008_02_name_group_last_group_once_in_order(self):
        self.write("m.py", "class Z:\n    pass\ndef y():\n    pass\ndef y():\n    pass\nclass Z:\n    pass\ndef x():\n    pass\n")
        self.commit()
        self.assertEqual(self.entries(), ["- m.py: Z, y, x"])

    def test_R008_02_nested_not_listed(self):
        self.write("m.py", SRC_A)
        self.commit()
        self.assertNotIn("inner", self.build())

    def test_R008_03_groups_and_lines(self):
        self.write("top.py", "def t():\n    pass\n")
        self.write("pkg/sub/empty.py", "x = 1\n")
        self.write("pkg/sub/full.py", "def f():\n    pass\n")
        self.commit()
        lines = self.build().splitlines()
        self.assertIn("## .", lines)
        self.assertIn("## pkg/sub", lines)
        i = lines.index("## pkg/sub")
        group = []
        for line in lines[i + 1:]:
            if line.startswith("## "):
                break
            if line.strip():
                group.append(line)
        self.assertEqual(group, ["- empty.py", "- full.py: f"])
        j = lines.index("## .")
        self.assertIn("- top.py: t", lines[j + 1:j + 3])

    def test_R008_04_long_entry_cut(self):
        names = [f"function_number_{i:03d}" for i in range(40)]
        self.write("long.py", "".join(f"def {n}():\n    pass\n" for n in names))
        self.commit()
        full = "- long.py: " + ", ".join(names)
        line = next(l for l in self.entries() if l.startswith("- long.py"))
        self.assertEqual(len(line), 240)
        self.assertEqual(line, full[:237] + "...")

    def test_R008_04_entry_of_240_kept(self):
        name = "f" * (240 - len("- e.py: "))
        self.write("e.py", f"def {name}():\n    pass\n")
        self.commit()
        self.assertIn(f"- e.py: {name}", self.entries())

    def test_R008_05_generated_header(self):
        self.write("a.py", "def a():\n    pass\n")
        self.commit()
        lines = self.build().splitlines()
        self.assertTrue(lines[0].startswith("#"))
        head = "\n".join(lines[:4])
        self.assertIn("agentkit codemap", head)
        self.assertIn("edit", head.lower())

    def test_R008_06_sorted_lf_single_newline(self):
        for rel in ("b/a.py", "a/z.py", "ab/c.py", "a/b.py"):
            self.write(rel, "def f():\n    pass\n")
        self.commit()
        text = self.build()
        self.assertEqual(text, self.build())
        self.assertNotIn("\r", text)
        self.assertTrue(text.endswith("\n") and not text.endswith("\n\n"))
        self.assertEqual([h for h in self.headings(text) if h in ("## a", "## ab", "## b")],
                         ["## a", "## ab", "## b"])
        self.assertEqual(self.headings(text)[-3:], ["## a", "## ab", "## b"])
        lines = text.splitlines()
        self.assertLess(lines.index("- b.py: f"), lines.index("- z.py: f"))


class TestWriteAndCheck(CodemapCase):
    def setUp(self) -> None:
        super().setUp()
        self.write("pkg/a.py", SRC_A)
        self.write("pkg/b.py", "def b():\n    pass\n")
        self.commit()

    def test_R008_07_writes_then_leaves_unchanged_file(self):
        code, _ = run_cli("codemap")
        self.assertEqual(code, 0)
        data = self.map_file.read_bytes()
        self.assertNotIn(b"\r", data)
        self.assertEqual(data, self.build().encode("utf-8"))
        os.utime(self.map_file, ns=(1_000_000_000, 1_000_000_000))
        run_cli("codemap")
        self.assertEqual(self.map_file.stat().st_mtime_ns, 1_000_000_000)
        self.write("pkg/c.py", "def c():\n    pass\n")
        run_cli("codemap")
        self.assertIn("- c.py: c", self.map_file.read_text(encoding="utf-8"))

    def test_R008_07_configured_path(self):
        self.write("agentkit.toml", '[kit]\nprofile = "fixture"\n\n[paths]\ncodemap = "MAP.md"\n')
        self.write_map()
        self.assertTrue((self.root / "MAP.md").is_file())
        self.assertFalse(self.map_file.exists())

    def test_R008_08_check_missing(self):
        code, _ = run_cli("codemap", "--check")
        self.assertEqual(code, 1)
        self.assertFalse(self.map_file.exists())

    def test_R008_08_check_differs_and_matches(self):
        self.write_map()
        code, _ = run_cli("codemap", "--check")
        self.assertEqual(code, 0)
        self.write("pkg/b.py", "def b():\n    pass\ndef b2():\n    pass\n")
        before = self.map_file.read_bytes()
        code, _ = run_cli("codemap", "--check")
        self.assertEqual(code, 1)
        self.assertEqual(self.map_file.read_bytes(), before)

    def test_R008_09_body_and_comment_edits_pass(self):
        self.write_map()
        self.write("pkg/a.py", SRC_A.replace("return 1", "# a comment\n    return 2"))
        code, _ = run_cli("codemap", "--check")
        self.assertEqual(code, 0)

    def test_R008_10_message_and_changed_files(self):
        self.write_map()
        self.write("pkg/b.py", "def renamed():\n    pass\n")
        code, out = run_cli("codemap", "--check")
        self.assertEqual(code, 1)
        self.assertIn("run `agentkit codemap`", out)
        self.assertIn("b.py", out)
        self.assertNotIn("a.py", out)

    def test_R008_10_at_most_10_files(self):
        self.write_map()
        for i in range(12):
            self.write(f"many/m{i:02d}.py", f"def m{i}():\n    pass\n")
        code, out = run_cli("codemap", "--check")
        self.assertEqual(code, 1)
        listed = [i for i in range(12) if f"m{i:02d}.py" in out]
        self.assertGreaterEqual(len(listed), 1)
        self.assertLessEqual(len(listed), 10)


class TestNoSources(CodemapCase):
    def test_R008_11_no_source_globs(self):
        self.write(".agentkit/profiles/fixture.toml", FIXTURE_PROFILE)
        code, _ = run_cli("codemap", "--check")
        self.assertEqual(code, 0)
        self.assertFalse(self.map_file.exists())


if __name__ == "__main__":
    unittest.main()
