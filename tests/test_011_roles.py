"""Spec 011: role prompts (R011-09 to R011-11, R011-13)."""
from __future__ import annotations

from pathlib import Path

from tests.content_fixtures import ROLE_NAMES, ROLES, ContentCase
from tests.support import RepoTestCase

REVIEWERS = ("spec-reviewer", "test-auditor", "impl-reviewer")


class TestRoleFiles(ContentCase):
    def test_R011_09_roles_and_front_matter(self):
        for name in ROLE_NAMES:
            with self.subTest(role=name):
                fm = self.meta(ROLES / f"{name}.md")
                self.assertEqual(fm.get("name"), name)
                self.assertIsInstance(fm.get("description"), str)
                self.assertTrue(fm["description"].strip())
                self.assertIn(fm.get("tier"), ("strong", "standard", "fast"))
                self.assertIn(fm.get("effort"), ("low", "medium", "high"))
                self.assertIsInstance(fm.get("tools"), list)
                self.assertLessEqual(set(fm["tools"]), {"read", "edit", "shell"})

    def test_R011_09_every_role_file_named_after_its_name(self):
        paths = sorted(ROLES.glob("*.md"))
        self.assertLessEqual({f"{n}.md" for n in ROLE_NAMES}, {p.name for p in paths})
        for path in paths:
            with self.subTest(role=path.name):
                self.assertEqual(self.meta(path).get("name"), path.stem)

    def test_R011_10_tiers(self):
        expected = {"spec-writer": "strong", "spec-reviewer": "strong", "test-writer": "strong",
                    "test-auditor": "strong", "implementer": "standard",
                    "impl-reviewer": "standard", "summarizer": "fast"}
        for name, tier in expected.items():
            with self.subTest(role=name):
                self.assertEqual(self.meta(ROLES / f"{name}.md").get("tier"), tier)

    def test_R011_11_reviewers_cannot_edit(self):
        for name in REVIEWERS:
            with self.subTest(role=name):
                tools = self.meta(ROLES / f"{name}.md").get("tools")
                self.assertIsInstance(tools, list)
                self.assertNotIn("edit", tools)


class TestRolesFunction(RepoTestCase):
    USE_GIT = False

    def roles(self):
        from agentkit.roles import roles
        return {name: Path(p).resolve() for name, p in roles(self.cfg()).items()}

    def role(self, rel: str, name: str) -> Path:
        return self.write(rel, f"---\nname: {name}\ndescription: Project role.\ntier: fast\n"
                               f"effort: low\ntools: [read]\n---\nProject body.\n").resolve()

    def test_R011_13_kit_roles_without_project_roles(self):
        found = self.roles()
        self.assertLessEqual(set(ROLE_NAMES), set(found))
        for name in found:
            self.assertEqual(found[name], (ROLES / f"{name}.md").resolve())
        for name in ROLE_NAMES:
            self.assertEqual(found[name], (ROLES / f"{name}.md").resolve())

    def test_R011_13_project_role_overrides_kit_role(self):
        mine = self.role("roles/summarizer.md", "summarizer")
        found = self.roles()
        self.assertEqual(found["summarizer"], mine)
        self.assertEqual(found["implementer"], (ROLES / "implementer.md").resolve())
        self.assertLessEqual(set(ROLE_NAMES), set(found))

    def test_R011_13_project_role_with_new_name_added(self):
        mine = self.role("roles/security-reviewer.md", "security-reviewer")
        found = self.roles()
        self.assertEqual(found["security-reviewer"], mine)
        self.assertLessEqual(set(ROLE_NAMES), set(found))

    def test_R011_13_name_is_the_file_name(self):
        mine = self.role("roles/sec-check.md", "something-else")
        found = self.roles()
        self.assertEqual(found.get("sec-check"), mine)
        self.assertNotIn("something-else", found)

    def test_R011_13_only_md_files_are_roles(self):
        self.write("roles/notes.txt", "not a role\n")
        self.assertNotIn("notes", self.roles())

    def test_R011_13_configured_roles_path(self):
        self.write("agentkit.toml", '[kit]\nprofile = "fixture"\n\n[paths]\nroles = "my/roles"\n')
        mine = self.role("my/roles/test-auditor.md", "test-auditor")
        self.role("roles/summarizer.md", "summarizer")
        found = self.roles()
        self.assertEqual(found["test-auditor"], mine)
        self.assertEqual(found["summarizer"], (ROLES / "summarizer.md").resolve())
