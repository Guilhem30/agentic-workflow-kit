"""Spec 010: managed files and the 3-way rule, executable hooks, the manifest and update
(R010-12, R010-13, R010-16, R010-17)."""
from __future__ import annotations

import os
import re
import stat
import unittest

from tests.install_fixtures import (COMMIT_MSG, FIRST_INSTALL, FIXTURE_VERSION, PRE_COMMIT_V1,
                                    PRE_COMMIT_V2, InstallCase, all_strings, manifest_entry)

HOOK = ".githooks/pre-commit"
NEW = ".githooks/pre-commit.agentkit-new"
MINE = "#!/bin/sh\n# customised by the project\nexit 0\n"


class ManagedCase(InstallCase):
    """An installed target (no adapters) and a kit of its own that the test may change."""

    def setUp(self):
        super().setUp()
        self.kit = self.own_kit()
        self.fake_adapters()
        self.write_config()
        self.api_install()

    def new_kit_hook(self, content: str = PRE_COMMIT_V2) -> None:
        self.write(self.kit / "githooks" / "pre-commit", content)

    def update(self, *extra: str) -> tuple[int, str]:
        return self.cli_in(self.target, "update", "--kit", str(self.kit), *extra)

    def hook(self) -> str:
        return self.text(HOOK)


class TestThreeWay(ManagedCase):
    def test_R010_12_missing_and_never_installed_is_written(self):
        self.assertEqual(self.hook(), PRE_COMMIT_V1)
        self.assertEqual(self.text(".githooks/commit-msg"), COMMIT_MSG)

    def test_R010_12_same_content_unchanged(self):
        code, out = self.update()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.hook(), PRE_COMMIT_V1)
        self.assertFalse((self.target / NEW).exists())

    def test_R010_12_not_customised_is_overwritten(self):
        self.new_kit_hook()
        code, out = self.update()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.hook(), PRE_COMMIT_V2)
        self.assertFalse((self.target / NEW).exists())

    def test_R010_12_customised_gets_conflict_file(self):
        self.write(self.target / HOOK, MINE)
        self.new_kit_hook()
        code, out = self.update()
        self.assertEqual(code, 1, out)
        self.assertEqual(self.hook(), MINE)
        self.assertEqual(self.text(NEW), PRE_COMMIT_V2)
        self.assertIn(HOOK, out)

    def test_R010_12_customised_conflicts_even_if_kit_unchanged(self):
        self.write(self.target / HOOK, MINE)
        code, out = self.update()
        self.assertEqual(code, 1, out)
        self.assertEqual(self.hook(), MINE)
        self.assertEqual(self.text(NEW), PRE_COMMIT_V1)

    def test_R010_12_force_overwrites_customised(self):
        self.write(self.target / HOOK, MINE)
        self.new_kit_hook()
        code, out = self.update("--force")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.hook(), PRE_COMMIT_V2)
        self.assertFalse((self.target / NEW).exists())

    def test_R010_12_deleted_by_user_is_skipped(self):
        (self.target / ".githooks" / "commit-msg").unlink()
        code, out = self.update()
        self.assertFalse((self.target / ".githooks" / "commit-msg").exists())
        self.assertFalse((self.target / ".githooks" / "commit-msg.agentkit-new").exists())
        self.assertIn(".githooks/commit-msg", out)

    def test_R010_12_deleted_by_user_restored_with_force(self):
        (self.target / ".githooks" / "commit-msg").unlink()
        self.update("--force")
        self.assertEqual(self.text(".githooks/commit-msg"), COMMIT_MSG)


class TestNotInManifest(InstallCase):
    def test_R010_12_existing_file_not_in_manifest_conflicts(self):
        self.fake_adapters()
        self.write_config()
        self.write(self.target / HOOK, MINE)
        report = self.api_install()
        self.assertEqual(self.text(HOOK), MINE)
        self.assertEqual(self.text(NEW), PRE_COMMIT_V1)
        self.assertIn(HOOK, report.conflicts)

    def test_R010_12_identical_file_not_in_manifest_unchanged(self):
        self.fake_adapters()
        self.write_config()
        self.write(self.target / HOOK, PRE_COMMIT_V1)
        report = self.api_install()
        self.assertNotIn(HOOK, report.conflicts)
        self.assertFalse((self.target / NEW).exists())
        self.assertEqual(self.text(HOOK), PRE_COMMIT_V1)

    def test_R010_12_force_overwrites_file_not_in_manifest(self):
        self.fake_adapters()
        self.write_config()
        self.write(self.target / HOOK, MINE)
        self.api_install(force=True)
        self.assertEqual(self.text(HOOK), PRE_COMMIT_V1)
        self.assertFalse((self.target / NEW).exists())


@unittest.skipIf(os.name == "nt", "no executable bit on Windows")
class TestExecutable(ManagedCase):
    def test_R010_13_hooks_are_executable(self):
        for rel in (HOOK, ".githooks/commit-msg"):
            with self.subTest(file=rel):
                self.assertTrue((self.target / rel).stat().st_mode & stat.S_IXUSR)

    def test_R010_13_still_executable_after_update(self):
        self.new_kit_hook()
        self.update()
        self.assertTrue((self.target / HOOK).stat().st_mode & stat.S_IXUSR)


class TestManifest(InstallCase):
    HEX = re.compile(r"^(?:sha256:)?([0-9a-f]{64})$")

    def hashes(self, entry: dict) -> list[str]:
        return [m.group(1) for v in entry.values()
                if isinstance(v, str) and (m := self.HEX.match(v))]

    def test_R010_16_records_kit_version(self):
        self.cli_install(*FIRST_INSTALL)
        self.assertIn(FIXTURE_VERSION, all_strings(self.manifest()))

    def test_R010_16_records_version_of_installed_kit(self):
        self.fake_adapters()
        self.write_config()
        self.api_install(kit=self.own_kit(version="8.8.8-src"))
        self.assertIn("8.8.8-src", all_strings(self.manifest()))

    def test_R010_16_records_hash_and_mode(self):
        self.fake_adapters()
        self.write_config(adapters='["claude-code"]')
        self.api_install()
        manifest = self.manifest()
        cases = {HOOK: "managed", ".agents/skills/spec/SKILL.md": "managed",
                 "AGENTS.md": "block", ".gitignore": "block",
                 ".claude/skills/spec/SKILL.md": "derived"}
        for rel, mode in cases.items():
            with self.subTest(file=rel):
                entry = manifest_entry(manifest, rel)
                self.assertIsNotNone(entry, f"{rel} not in manifest")
                self.assertIn(mode, entry.values())
                self.assertTrue(self.hashes(entry), entry)
                if mode != "block":
                    self.assertIn(self.sha256(self.target / rel), self.hashes(entry))


class TestUpdate(ManagedCase):
    def test_R010_17_update_uses_given_kit_and_keeps_config(self):
        before = (self.target / "agentkit.toml").read_bytes()
        self.new_kit_hook()
        code, out = self.update()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.hook(), PRE_COMMIT_V2)
        self.assertEqual((self.target / ".agentkit/githooks/pre-commit").read_text(
            encoding="utf-8"), PRE_COMMIT_V2)
        self.assertEqual((self.target / "agentkit.toml").read_bytes(), before)

    def test_R010_17_default_kit_is_installed_copy(self):
        self.write(self.target / ".agentkit" / "githooks" / "pre-commit", PRE_COMMIT_V2)
        code, out = self.cli_in(self.target, "update")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.hook(), PRE_COMMIT_V2)

    def test_R010_17_exit_1_on_conflicts(self):
        self.write(self.target / HOOK, MINE)
        self.new_kit_hook()
        code, _ = self.update()
        self.assertEqual(code, 1)
        code, _ = self.cli_in(self.target, "update", "--kit", str(self.kit), "--force")
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
