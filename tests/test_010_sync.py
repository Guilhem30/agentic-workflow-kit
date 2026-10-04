"""Spec 010: rendering, sync and sync --check (R010-03 rendering, R010-18 to R010-20)."""
from __future__ import annotations

import shutil
import unittest

from agentkit.install import render
from tests.install_fixtures import InstallCase, snapshot


class TestRender(unittest.TestCase):
    def test_R010_03_render_replaces_known_keys(self):
        self.assertEqual(render("run {{python}} -m x in {{specs}}/",
                                {"python": "py -3.12", "specs": "work/specs"}),
                         "run py -3.12 -m x in work/specs/")

    def test_R010_03_render_leaves_unknown_and_spaced_keys(self):
        text = "base: ${{ github.base_ref }} {{nope}} {{ python }} $CI_COMMIT_SHA"
        self.assertEqual(render(text, {"python": "py"}), text)


class SyncCase(InstallCase):
    def setUp(self):
        super().setUp()
        self.fake = self.fake_adapters()
        self.write_config(adapters='["claude-code"]')
        self.api_install()

    def sync(self, *extra: str) -> tuple[int, str]:
        return self.cli_in(self.target, "sync", *extra)

    def derived(self, name: str):
        return self.target / ".claude" / "skills" / name / "SKILL.md"

    def drop_skill(self, name: str) -> None:
        shutil.rmtree(self.target / ".agents" / "skills" / name)


class TestSync(SyncCase):
    def test_R010_18_regenerates_derived_files(self):
        expected = self.derived("spec").read_bytes()
        self.write(self.derived("spec"), "hand edit\n")
        self.write(self.target / ".agents/skills/extra/SKILL.md", "---\nname: extra\n---\n")
        code, out = self.sync()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.derived("spec").read_bytes(), expected)
        self.assertEqual(self.derived("extra").read_bytes(),
                         b"<!-- generated -->\n---\nname: extra\n---\n")

    def test_R010_19_removes_file_derived_by_an_earlier_sync(self):
        self.write(self.target / ".agents/skills/extra/SKILL.md", "---\nname: extra\n---\n")
        self.sync()
        self.drop_skill("extra")
        code, out = self.sync()
        self.assertEqual(code, 0, out)
        self.assertFalse((self.target / ".claude/skills/extra").exists())

    def test_R010_18_only_configured_adapters(self):
        self.fake.derived_calls.clear()
        self.sync()
        self.assertEqual(set(self.fake.derived_calls), {"claude-code"})

    def test_R010_19_removes_unproduced_unchanged_file(self):
        self.drop_skill("handoff")
        code, out = self.sync()
        self.assertEqual(code, 0, out)
        self.assertFalse((self.target / ".claude/skills/handoff").exists())
        self.assertTrue(self.derived("spec").is_file())

    def test_R010_19_keeps_files_it_did_not_generate(self):
        mine = self.write(self.target / ".claude/skills/mine/SKILL.md", "my own skill\n")
        self.sync()
        self.assertEqual(mine.read_text(encoding="utf-8"), "my own skill\n")

    def test_R010_19_keeps_changed_file(self):
        self.write(self.derived("handoff"), "my own notes\n")
        self.drop_skill("handoff")
        self.sync()
        self.assertEqual(self.derived("handoff").read_text(encoding="utf-8"), "my own notes\n")


class TestSyncCheck(SyncCase):
    def test_R010_20_clean_exits_0(self):
        code, out = self.sync("--check")
        self.assertEqual(code, 0, out)

    def test_R010_20_lists_drift_writes_nothing(self):
        self.write(self.derived("spec"), "hand edit\n")          # different
        self.derived("implement").unlink()                       # missing
        self.drop_skill("handoff")                               # stale
        before = snapshot(self.target)
        code, out = self.sync("--check")
        self.assertEqual(code, 1, out)
        for rel in (".claude/skills/spec/SKILL.md", ".claude/skills/implement/SKILL.md",
                    ".claude/skills/handoff/SKILL.md"):
            with self.subTest(file=rel):
                self.assertIn(rel, out)
        self.assertEqual(snapshot(self.target), before)


if __name__ == "__main__":
    unittest.main()
