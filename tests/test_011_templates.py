"""Spec 011: templates (R011-03 to R011-08)."""
from __future__ import annotations

import re

from tests.content_fixtures import (DEFAULT_CTX, INSTALL_KEYS, INSTALL_TEMPLATES, ODD_CTX,
                                    SKILL_NAMES, SKILLS, SPEC_CTX, SPEC_FOLDER_TEMPLATES,
                                    SPEC_KEYS, TEMPLATES, ContentCase, body,
                                    front_matter, placeholders, render)
from tests.support import RepoTestCase


def section(text: str, heading: str) -> str:
    """The text under '## heading' up to the next '## ' heading."""
    m = re.search(rf"^## {re.escape(heading)}[ \t]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


class TestTemplateFiles(ContentCase):
    def test_R011_03_templates_present(self):
        for name in SPEC_FOLDER_TEMPLATES + INSTALL_TEMPLATES:
            with self.subTest(name=name):
                self.read(TEMPLATES / name)


class TestSpecTemplate(ContentCase):
    def spec(self) -> str:
        return render(self.read(TEMPLATES / "spec.md"), SPEC_CTX)

    def test_R011_04_front_matter(self):
        fm = front_matter(self.spec())
        self.assertEqual(fm.get("id"), "042")
        self.assertEqual(fm.get("title"), "Sample feature")
        self.assertEqual(fm.get("status"), "draft")

    def test_R011_04_sections(self):
        text = body(self.spec())
        headings = [m.group(1).strip() for m in re.finditer(r"^## (.+)$", text, re.M)]
        for name in ("Context", "Requirements (EARS)", "Public API contract",
                     "Examples and edge cases", "Out of scope", "Open questions"):
            with self.subTest(section=name):
                self.assertIn(name, headings)

    def test_R011_04_ears_patterns_and_manual_explained(self):
        req = section(body(self.spec()), "Requirements (EARS)")
        for word in ("shall", "When", "While", "If", "Where", "[manual]"):
            with self.subTest(word=word):
                self.assertIn(word, req)


class TestAgentsTemplate(ContentCase):
    def test_R011_05_project_sections_outside_block(self):
        text = self.agents_md(DEFAULT_CTX)
        block = self.block(text)
        outside = text.replace(block, "")
        self.assertRegex(outside, r"(?m)^#{1,6} \S", "a project heading outside the block")

    def test_R011_05_session_start(self):
        self.assertIn("session start", self.block(self.agents_md(DEFAULT_CTX)).lower())

    def test_R011_05_protected_files_use_configured_paths(self):
        block = self.block(self.agents_md(ODD_CTX))
        for needle in ("work/frozen.lock.json", "work/unfreeze-history.md", "agentkit.toml",
                       ".agentkit/", "work/chaos-audit.jsonl", "work/specs/*/reviews/",
                       "chaos clear"):
            with self.subTest(needle=needle):
                self.assertIn(needle, block)

    def test_R011_05_hard_rules_frozen_and_chaos_gates(self):
        block = self.block(self.agents_md(DEFAULT_CTX))
        self.assertIn("frozen", block.lower())
        self.assertIn("chaos approve", block)

    def test_R011_05_command_table_uses_launcher(self):
        block = self.block(self.agents_md(ODD_CTX))
        rows = [ln for ln in block.splitlines() if ln.strip().startswith("|")]
        self.assertTrue(any(re.match(r"^\s*\|(\s*:?-{3,}:?\s*\|)+\s*$", ln) for ln in rows),
                        "a Markdown table with a separator row")
        self.assertTrue(any("py -3.12 .agentkit/bin/agentkit" in ln for ln in rows),
                        "commands run through {{python}} .agentkit/bin/agentkit")

    def test_R011_05_token_discipline(self):
        self.assertIn("token", self.block(self.agents_md(DEFAULT_CTX)).lower())

    def test_R011_06_block_at_most_45_lines(self):
        for ctx in (DEFAULT_CTX, ODD_CTX):
            block = self.block(self.agents_md(ctx))
            self.assertLessEqual(len(block.splitlines()), 45)


class TestPlaceholders(ContentCase):
    def test_R011_07_spec_folder_templates_use_new_spec_keys(self):
        for name in SPEC_FOLDER_TEMPLATES:
            with self.subTest(name=name):
                text = self.read(TEMPLATES / name)
                self.assertLessEqual(placeholders(text), SPEC_KEYS)
                self.assertNotIn("{{", render(text, SPEC_CTX))

    def test_R011_07_install_templates_use_install_keys(self):
        for name in INSTALL_TEMPLATES:
            with self.subTest(name=name):
                text = self.read(TEMPLATES / name)
                self.assertLessEqual(placeholders(text), INSTALL_KEYS)
                for ctx in (DEFAULT_CTX, ODD_CTX):
                    self.assertNotIn("{{", render(text, ctx))

    def test_R011_07_other_template_files_use_install_keys(self):
        for path in TEMPLATES.rglob("*"):
            if path.is_file() and path.name not in SPEC_FOLDER_TEMPLATES:
                with self.subTest(path=path.name):
                    text = self.read(path)
                    self.assertLessEqual(placeholders(text), INSTALL_KEYS)
                    self.assertNotIn("{{", render(text, DEFAULT_CTX))


class TestLintsClean(RepoTestCase, ContentCase):
    USE_GIT = False

    def test_R011_08_rendered_agents_md_with_import_and_skills_passes_lint(self):
        self.write("AGENTS.md", self.agents_md(DEFAULT_CTX))
        self.write("CLAUDE.md", "@AGENTS.md\n")
        for name in SKILL_NAMES:
            src = SKILLS / name
            self.read(src / "SKILL.md")
            for path in sorted(p for p in src.rglob("*") if p.is_file()):
                rel = path.relative_to(SKILLS).as_posix()
                data = path.read_bytes()
                if path.suffix == ".md":
                    data = render(data.decode("utf-8"), DEFAULT_CTX).encode("utf-8")
                self.write(f".agents/skills/{rel}", data)
        from agentkit.lint_instructions import lint
        report = lint(self.cfg())
        self.assertEqual(report.errors, [])
        self.assertTrue(report.ok)
