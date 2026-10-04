"""Spec 011: Agent Skills (R011-14 to R011-16, R011-18)."""
from __future__ import annotations

import re

from tests.content_fixtures import (INSTALL_KEYS, SKILL_NAMES, SKILLS, ContentCase, body,
                                    placeholders)

STANDARD_KEYS = {"name", "description", "license", "compatibility", "allowed-tools", "metadata"}
AGENTKIT_EXTRAS = {"agentkit-tier", "agentkit-effort", "agentkit-user-only", "agentkit-args"}
LAUNCHER = "{{python}} .agentkit/bin/agentkit"


class SkillCase(ContentCase):
    def skill(self, name: str) -> dict:
        return self.meta(SKILLS / name / "SKILL.md")

    def text(self, name: str) -> str:
        return self.read(SKILLS / name / "SKILL.md")

    def metadata(self, name: str) -> dict:
        md = self.skill(name).get("metadata")
        self.assertIsInstance(md, dict, f"{name}: metadata mapping")
        return md


class TestSkillFiles(SkillCase):
    def test_R011_14_skills_present_with_standard_front_matter(self):
        for name in SKILL_NAMES:
            with self.subTest(skill=name):
                fm = self.skill(name)
                self.assertEqual(fm.get("name"), name)
                self.assertIsInstance(fm.get("description"), str)
                self.assertTrue(fm["description"].strip())
                self.assertLessEqual(len(fm["description"]), 200)
                self.assertLessEqual(set(fm), STANDARD_KEYS)

    def test_R011_14_agentkit_extras_under_metadata(self):
        for name in SKILL_NAMES:
            with self.subTest(skill=name):
                md = self.metadata(name)
                extras = {k for k in md if k.startswith("agentkit-")}
                self.assertLessEqual(extras, AGENTKIT_EXTRAS)
                for key, value in md.items():
                    self.assertIsInstance(value, str, f"metadata.{key} is a string")

    def test_R011_14_every_skill_directory_named_after_its_skill(self):
        for path in SKILLS.glob("*/SKILL.md"):
            with self.subTest(skill=path.parent.name):
                self.assertEqual(self.meta(path).get("name"), path.parent.name)


class TestUserOnly(SkillCase):
    def test_R011_15_freeze_is_user_only(self):
        self.assertEqual(self.metadata("freeze").get("agentkit-user-only"), "true")

    def test_R011_15_freeze_stops_unless_tests_approved(self):
        text = body(self.text("freeze"))
        self.assertIn("tests-approved", text)
        self.assertRegex(text.lower(), r"\bstop")

    def test_R011_15_autopilot_is_user_only(self):
        self.assertEqual(self.metadata("autopilot").get("agentkit-user-only"), "true")


class TestTiers(SkillCase):
    def test_R011_16_tier_and_effort(self):
        expected = {"kickoff": ("strong", "high"), "feature": ("strong", "high"),
                    "spec": ("strong", "high"), "write-tests": ("strong", "high"),
                    "implement": ("standard", "medium"), "autopilot": ("standard", "medium"),
                    "freeze": ("fast", "low"), "handoff": ("fast", "low")}
        for name, (tier, effort) in expected.items():
            with self.subTest(skill=name):
                md = self.metadata(name)
                self.assertEqual((md.get("agentkit-tier"), md.get("agentkit-effort")),
                                 (tier, effort))


class TestCommands(SkillCase):
    def skill_files(self):
        for name in SKILL_NAMES:
            self.text(name)
        return sorted(p for p in SKILLS.rglob("*.md") if p.is_file())

    def test_R011_18_commands_through_launcher(self):
        for path in self.skill_files():
            rel = path.relative_to(SKILLS).as_posix()
            with self.subTest(file=rel):
                text = self.read(path)
                self.assertNotRegex(text, r"-m\s+agentkit\b", "no `python -m agentkit`")
                for m in re.finditer(r"\.agentkit/bin/agentkit\b", text):
                    self.assertTrue(text[:m.start()].endswith("{{python}} "),
                                    f"launcher without {{{{python}}}} at offset {m.start()}")

    def test_R011_18_command_skills_use_launcher(self):
        # freeze (lock freeze), write-tests (trace), implement (test), handoff (handoff) and
        # autopilot (autopilot) all run agentkit commands.
        for name in ("freeze", "write-tests", "implement", "handoff", "autopilot"):
            with self.subTest(skill=name):
                self.assertIn(LAUNCHER, self.text(name))

    def test_R011_18_placeholders_are_install_keys(self):
        for path in self.skill_files():
            with self.subTest(file=path.relative_to(SKILLS).as_posix()):
                self.assertLessEqual(placeholders(self.read(path)), INSTALL_KEYS)
