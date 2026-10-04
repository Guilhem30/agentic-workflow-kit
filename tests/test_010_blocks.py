"""Spec 010: block files and their markers (R010-14, R010-15)."""
from __future__ import annotations

import unittest

from agentkit.install import Planned
from tests.install_fixtures import BEGIN, END, InstallCase, block_region

CLAUDE_BLOCK = b"@AGENTS.md\n- fixture Claude-only note\n"


class BlockCase(InstallCase):
    def setUp(self):
        super().setUp()
        self.fake = self.fake_adapters()
        self.write_config(adapters='["claude-code"]')

    def kit_region(self) -> str:
        """The AGENTS.md block region of a fresh install with the same config."""
        fresh = self.tmp / "fresh"
        fresh.mkdir()
        self.write_config(root=fresh, adapters='["claude-code"]')
        self.api_install(root=fresh)
        return block_region(self.text("AGENTS.md", root=fresh))

    def claude(self, initial: bytes | None = None) -> None:
        self.fake.kit["claude-code"] = [Planned(path="CLAUDE.md", content=CLAUDE_BLOCK,
                                                mode="block", initial=initial,
                                                placement="top")]


class TestMarkers(BlockCase):
    def test_R010_14_markdown_markers(self):
        self.api_install()
        lines = self.text("AGENTS.md").splitlines()
        self.assertEqual(lines.count(BEGIN), 1)
        self.assertEqual(lines.count(END), 1)

    def test_R010_14_hash_markers(self):
        self.api_install(owner="@alice")
        for rel in (".gitignore", ".github/CODEOWNERS"):
            with self.subTest(file=rel):
                lines = self.text(rel).splitlines()
                self.assertEqual(sum(l.startswith("# agentkit:begin") for l in lines), 1)
                self.assertEqual(sum(l.startswith("# agentkit:end") for l in lines), 1)


class TestPlacement(BlockCase):
    def test_R010_15_missing_file_gets_whole_template(self):
        self.api_install()
        text = self.text("AGENTS.md")
        self.assertTrue(text.startswith("# "), text[:80])
        self.assertLess(text.index("## Product"), text.index(BEGIN))
        self.assertTrue(block_region(text).strip())

    def test_R010_15_markers_present_only_region_replaced(self):
        self.write(self.target / "AGENTS.md",
                   f"# Mine\n\nintro kept\n\n{BEGIN}\nstale block text\n{END}\n\nafter kept\n")
        self.api_install()
        text = self.text("AGENTS.md")
        self.assertTrue(text.startswith("# Mine\n\nintro kept\n\n"), text[:80])
        self.assertTrue(text.endswith("\n\nafter kept\n"), text[-80:])
        self.assertNotIn("stale block text", text)
        self.assertEqual(block_region(text), self.kit_region())

    def test_R010_15_no_markers_block_added_at_end(self):
        self.write(self.target / "AGENTS.md", "# Mine\n\nall of this is kept\n")
        self.api_install()
        text = self.text("AGENTS.md")
        self.assertTrue(text.startswith("# Mine\n\nall of this is kept\n"), text[:80])
        self.assertLess(text.index("all of this is kept"), text.index(BEGIN))
        self.assertTrue(text.rstrip("\n").endswith(END), text[-80:])
        self.assertEqual(block_region(text), self.kit_region())

    def test_R010_15_no_markers_top_placement(self):
        self.claude()
        self.write(self.target / "CLAUDE.md", "# My Claude notes\n")
        self.api_install()
        text = self.text("CLAUDE.md")
        self.assertTrue(text.startswith(BEGIN + "\n"), text[:80])
        self.assertEqual(block_region(text), CLAUDE_BLOCK.decode())
        self.assertLess(text.index(END), text.index("# My Claude notes"))

    def test_R010_15_missing_file_initial_written(self):
        initial = f"{BEGIN}\n{CLAUDE_BLOCK.decode()}{END}\n\n# Project notes\n".encode()
        self.claude(initial=initial)
        self.api_install()
        self.assertEqual((self.target / "CLAUDE.md").read_bytes(), initial)

    def test_R010_15_missing_file_without_initial_gets_markers_around_content(self):
        self.claude()
        self.api_install()
        text = self.text("CLAUDE.md")
        self.assertEqual(block_region(text), CLAUDE_BLOCK.decode())

    def test_R010_15_gitignore_region_replaced(self):
        fresh = self.tmp / "fresh"
        fresh.mkdir()
        self.write_config(root=fresh, adapters='["claude-code"]')
        self.api_install(root=fresh)
        fresh_lines = self.text(".gitignore", root=fresh).splitlines()
        begin = next(l for l in fresh_lines if l.startswith("# agentkit:begin"))
        end = next(l for l in fresh_lines if l.startswith("# agentkit:end"))
        self.write(self.target / ".gitignore", f"build/\n{begin}\nstale-entry/\n{end}\ndist/\n")
        self.api_install()
        lines = self.text(".gitignore").splitlines()
        self.assertEqual(lines[0], "build/")
        self.assertEqual(lines[-1], "dist/")
        self.assertNotIn("stale-entry/", lines)
        self.assertIn(".agentkit/state/", lines)


if __name__ == "__main__":
    unittest.main()
