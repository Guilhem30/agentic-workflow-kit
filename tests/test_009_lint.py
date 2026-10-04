"""Spec 009: `agentkit lint-instructions`."""
from __future__ import annotations

import unittest

from tests.support import RepoTestCase, run_cli


def lines(n: int, word: str = "line") -> str:
    return "".join(f"{word} number {i:04d} of this file\n" for i in range(n))


def skill(name: str | None = "demo", description: str | None = "Does a demo thing.", body: str = "Body.\n") -> str:
    fm = []
    if name is not None:
        fm.append(f"name: {name}")
    if description is not None:
        fm.append(f"description: {description}")
    return "---\n" + "\n".join(fm) + "\n---\n" + body


class LintCase(RepoTestCase):
    USE_GIT = False

    def lint(self):
        from agentkit.lint_instructions import lint
        return lint(self.cfg())

    def budgets(self, body: str) -> None:
        self.write("agentkit.toml", f'[kit]\nprofile = "fixture"\n\n[budgets]\n{body}\n')

    def errors_about(self, report, needle):
        return [e for e in report.errors if needle in e]

    def skill_errors(self, report, dirname="demo"):
        return [e for e in report.errors if "SKILL.md" in e or dirname in e]


class TestInputs(LintCase):
    def test_R009_01_checked_files(self):
        self.write("AGENTS.md", lines(151))
        self.write("CLAUDE.md", "@AGENTS.md\n" + lines(41, "claude"))
        self.write(".claude/rules/deep/r.md", "---\npaths: [\"src/**\"]\n---\n" + lines(81, "rule"))
        self.write(".agents/skills/demo/SKILL.md", skill(body=lines(501, "skill")))
        report = self.lint()
        for f in ("AGENTS.md", "CLAUDE.md", "r.md", "SKILL.md"):
            self.assertTrue(self.errors_about(report, f), (f, report.errors))

    def test_R009_01_generated_copies_not_checked(self):
        self.write(".claude/skills/demo/SKILL.md", skill(name="Wrong Name", body=lines(600)))
        self.write("docs/other.md", lines(1000))
        report = self.lint()
        self.assertEqual(report.errors, [])

    def test_R009_01_configured_skills_path(self):
        self.write("agentkit.toml", '[kit]\nprofile = "fixture"\n\n[paths]\nskills = "my/skills"\n')
        self.write("my/skills/demo/SKILL.md", skill(name="other"))
        self.assertTrue(self.skill_errors(self.lint()))

    def test_R009_02_default_budgets(self):
        self.write("AGENTS.md", lines(150))
        self.write("CLAUDE.md", "@AGENTS.md\n" + lines(39, "claude"))
        self.write(".claude/rules/r.md", "---\npaths: [\"src/**\"]\n---\n" + lines(77, "rule"))
        self.write(".agents/skills/demo/SKILL.md", skill(body=lines(496, "skill")))
        self.assertEqual(self.lint().errors, [])

    def test_R009_02_configured_budgets(self):
        self.budgets("agents_md_lines = 10\nclaude_md_lines = 2\nrule_md_lines = 6\nskill_md_lines = 8")
        self.write("AGENTS.md", lines(10))
        self.write("CLAUDE.md", "@AGENTS.md\nx\n")
        self.write(".claude/rules/r.md", "---\npaths: [\"src/**\"]\n---\n" + lines(3, "rule"))
        self.write(".agents/skills/demo/SKILL.md", skill(body=lines(4, "skill")))
        self.assertEqual(self.lint().errors, [])
        self.write("AGENTS.md", lines(11))
        self.write("CLAUDE.md", "@AGENTS.md\nx\ny\n")
        self.write(".claude/rules/r.md", "---\npaths: [\"src/**\"]\n---\n" + lines(4, "rule"))
        self.write(".agents/skills/demo/SKILL.md", skill(body=lines(5, "skill")))
        report = self.lint()
        for f in ("AGENTS.md", "CLAUDE.md", "r.md", "SKILL.md"):
            self.assertTrue([e for e in report.errors if f in e and (f != "AGENTS.md" or "CLAUDE" not in e)],
                            (f, report.errors))


class TestErrors(LintCase):
    def test_R009_03_line_budget_message(self):
        self.write("AGENTS.md", lines(151))
        report = self.lint()
        err = self.errors_about(report, "AGENTS.md")
        self.assertEqual(len(err), 1, report.errors)
        self.assertIn("151", err[0])
        self.assertIn("150", err[0])

    def test_R009_04_claude_md_must_import(self):
        self.write("AGENTS.md", lines(5))
        self.write("CLAUDE.md", "Some notes for Claude only.\n")
        self.assertTrue(self.errors_about(self.lint(), "CLAUDE.md"))
        self.write("CLAUDE.md", "@AGENTS.md\n\nSome notes for Claude only.\n")
        self.assertEqual(self.lint().errors, [])

    def test_R009_04_claude_md_alone_is_fine(self):
        self.write("CLAUDE.md", "Some notes for Claude only.\n")
        self.assertEqual(self.lint().errors, [])

    def test_R009_05_skill_name(self):
        cases = {
            "missing": skill(name=None),
            "differs": skill(name="other"),
            "pattern": skill(name="Demo_Skill"),
        }
        for label, text in cases.items():
            with self.subTest(label=label):
                d = "Demo_Skill" if label == "pattern" else "demo"
                self.write(f".agents/skills/{d}/SKILL.md", text)
                self.assertTrue(self.skill_errors(self.lint(), d), label)
                (self.root / f".agents/skills/{d}/SKILL.md").unlink()
        for name in ("a" * 65, "-lead", "trail-", "two--dashes"):
            with self.subTest(name=name):
                self.write(f".agents/skills/{name}/SKILL.md", skill(name=name))
                self.assertTrue(self.skill_errors(self.lint(), name), name)
                (self.root / f".agents/skills/{name}/SKILL.md").unlink()

    def test_R009_05_valid_names(self):
        for name in ("demo", "write-tests", "a1-b2", "x" * 64):
            self.write(f".agents/skills/{name}/SKILL.md", skill(name=name))
        self.assertEqual(self.lint().errors, [])

    def test_R009_06_skill_description(self):
        self.write(".agents/skills/demo/SKILL.md", skill(description=None))
        self.assertTrue(self.skill_errors(self.lint()))
        self.write(".agents/skills/demo/SKILL.md", skill(description="d" * 201))
        self.assertTrue(self.skill_errors(self.lint()))
        self.write(".agents/skills/demo/SKILL.md", skill(description="d" * 200))
        self.assertEqual(self.lint().errors, [])
        self.budgets("skill_description_chars = 50")
        self.write(".agents/skills/demo/SKILL.md", skill(description="d" * 51))
        self.assertTrue(self.skill_errors(self.lint()))

    BLOCK = ("Run the full suite before each commit.\n"
             "Never edit frozen files under any circumstances.\n"
             "Hand verbose work to a summarizer subagent.\n")

    def test_R009_07_duplicate_block(self):
        self.write("AGENTS.md", "# Rules\n\n" + self.BLOCK)
        self.write(".agents/skills/demo/SKILL.md", skill(body="Intro text for the skill body.\n" + self.BLOCK))
        report = self.lint()
        dup = [e for e in report.errors if "AGENTS.md" in e and "SKILL.md" in e]
        self.assertEqual(len(dup), 1, report.errors)
        self.assertIn("run the full suite before each commit", dup[0].lower())

    def test_R009_07_one_error_per_pair(self):
        other = ("Keep each session to one phase of one spec.\n"
                 "Write the progress file before clearing context.\n"
                 "Resume from the snapshot in the progress file.\n")
        self.write("AGENTS.md", self.BLOCK + "Something unrelated in between here.\n" + other)
        self.write(".agents/skills/demo/SKILL.md", skill(body=other + "A separator line for the body.\n" + self.BLOCK))
        report = self.lint()
        self.assertEqual(len([e for e in report.errors if "AGENTS.md" in e and "SKILL.md" in e]), 1,
                         report.errors)

    def test_R009_07_shorter_block_ok(self):
        two = "".join(self.BLOCK.splitlines(keepends=True)[:2])
        self.write("AGENTS.md", two)
        self.write(".agents/skills/demo/SKILL.md", skill(body=two))
        self.assertEqual(self.lint().errors, [])
        self.budgets("duplicate_min_lines = 2")
        report = self.lint()
        self.assertEqual(len([e for e in report.errors if "AGENTS.md" in e and "SKILL.md" in e]), 1,
                         report.errors)

    def test_R009_07_must_be_consecutive(self):
        a, b, c = self.BLOCK.splitlines(keepends=True)
        self.write("AGENTS.md", self.BLOCK)
        self.write(".agents/skills/demo/SKILL.md",
                   skill(body=a + b + "A completely different instruction sits here.\n" + c))
        self.assertEqual(self.lint().errors, [])

    def test_R009_07_generated_copy_not_a_duplicate(self):
        body = "Intro text for the skill body.\n" + self.BLOCK
        self.write(".agents/skills/demo/SKILL.md", skill(body=body))
        self.write(".claude/skills/demo/SKILL.md", skill(body=body))
        self.assertEqual(self.lint().errors, [])

    def test_R009_08_twelve_character_threshold(self):
        twelve = "abcdefghijkl\nmnopqrstuvwx\nyzabcdefghij\n"
        eleven = "abcdefghijk\nmnopqrstuvw\nyzabcdefghi\n"
        self.write("AGENTS.md", eleven)
        self.write(".agents/skills/demo/SKILL.md", skill(body=eleven))
        self.assertEqual(self.lint().errors, [])
        self.write("AGENTS.md", twelve)
        self.write(".agents/skills/demo/SKILL.md", skill(body=twelve))
        self.assertTrue([e for e in self.lint().errors if "AGENTS.md" in e and "SKILL.md" in e])

    def test_R009_07_same_file_repeat_ok(self):
        self.write("AGENTS.md", self.BLOCK + "\nAnother paragraph of guidance here.\n\n" + self.BLOCK)
        self.assertEqual(self.lint().errors, [])

    def test_R009_08_normalisation(self):
        self.write("AGENTS.md",
                   "- Run the full   suite before each commit.\n"
                   "\n"
                   "1. NEVER edit frozen files under any circumstances.\n"
                   "```\n"
                   "```\n"
                   "> Hand verbose work to a summarizer subagent.\n")
        self.write(".agents/skills/demo/SKILL.md", skill(body=
                   "## run the full suite before each commit.\n"
                   "* never edit frozen files   under any circumstances.\n"
                   "short\n"
                   "  hand verbose work to a summarizer subagent.\n"))
        report = self.lint()
        self.assertTrue([e for e in report.errors if "AGENTS.md" in e and "SKILL.md" in e],
                        report.errors)

    def test_R009_08_short_lines_and_front_matter_ignored(self):
        short = "Do this.\nDo that.\nThen go.\n"
        self.write("AGENTS.md", short)
        fm = ("---\npaths: [\"src/**\", \"lib/**\"]\nowner: the team lead person\n"
              "reviewer: the second team member\nsummary: shared front matter text\n---\n")
        self.write(".claude/rules/a.md", fm + short)
        self.write(".claude/rules/b.md", fm + "Unrelated rule text here.\n")
        self.assertEqual(self.lint().errors, [])


class TestReport(LintCase):
    def test_R009_09_rule_without_paths_warns(self):
        self.write(".claude/rules/always.md", "Always loaded rule text.\n")
        self.write(".claude/rules/scoped.md", "---\npaths: [\"src/**\"]\n---\nScoped rule text.\n")
        self.write(".claude/rules/other.md", "---\ndescription: no paths here\n---\nOther rule text.\n")
        report = self.lint()
        self.assertTrue([w for w in report.warnings if "always.md" in w])
        self.assertTrue([w for w in report.warnings if "other.md" in w])
        self.assertFalse([w for w in report.warnings if "scoped.md" in w])
        self.assertEqual(report.errors, [])

    def test_R009_10_estimate_tokens(self):
        from agentkit.lint_instructions import estimate_tokens
        self.assertEqual(estimate_tokens(""), 0)
        self.assertEqual(estimate_tokens("a"), 1)
        self.assertEqual(estimate_tokens("abcd"), 1)
        self.assertEqual(estimate_tokens("abcde"), 2)
        self.assertEqual(estimate_tokens("x" * 4001), 1001)
        self.assertEqual(estimate_tokens("éééé"), 1)

    def test_R009_10_always_loaded_sum(self):
        agents = "A" * 399 + "\n"           # 400 chars
        claude = "@AGENTS.md\n" + "c" * 88 + "\n"  # 100 chars
        rule = "r" * 199 + "\n"              # 200 chars, no paths: counted
        scoped = "---\npaths: [\"src/**\"]\n---\n" + "s" * 1000 + "\n"  # not counted
        desc = "d" * 194                     # "demo: " + 194 = 200 chars
        self.write("AGENTS.md", agents)
        self.write("CLAUDE.md", claude)
        self.write(".claude/rules/r.md", rule)
        self.write(".claude/rules/s.md", scoped)
        self.write(".agents/skills/demo/SKILL.md", skill(description=desc, body="b" * 5000 + "\n"))
        self.assertEqual(self.lint().always_loaded_tokens, (400 + 100 + 200 + 200) // 4)

    def test_R009_11_over_budget_warns_only(self):
        self.budgets("always_loaded_tokens = 10")
        self.write("AGENTS.md", "x" * 400 + "\n")
        report = self.lint()
        self.assertEqual(report.errors, [])
        self.assertTrue(report.ok)
        self.assertTrue(report.warnings)

    def test_R009_11_at_budget_no_warning(self):
        self.budgets("always_loaded_tokens = 100")
        self.write("AGENTS.md", "A" * 399 + "\n")  # exactly 100 tokens
        report = self.lint()
        self.assertEqual(report.always_loaded_tokens, 100)
        self.assertEqual(report.warnings, [])
        self.write("AGENTS.md", "A" * 400 + "\n")  # 101 tokens
        self.assertTrue(self.lint().warnings)

    def test_R009_12_last_line_ok(self):
        self.write("AGENTS.md", "A" * 399 + "\n")
        code, out = run_cli("lint-instructions")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines()[-1],
                         "lint-instructions: OK (always-loaded instructions ~100 tokens)")

    def test_R009_12_last_line_failed(self):
        self.write("AGENTS.md", lines(151))
        code, out = run_cli("lint-instructions")
        self.assertEqual(code, 1)
        self.assertRegex(out.splitlines()[-1],
                         r"^lint-instructions: FAILED \(always-loaded instructions ~\d+ tokens\)$")
        self.assertIn("AGENTS.md", out)

    def test_R009_12_ok_property(self):
        from agentkit.lint_instructions import LintReport
        self.assertTrue(LintReport([], ["w"], 5).ok)
        self.assertFalse(LintReport(["e"], [], 5).ok)


if __name__ == "__main__":
    unittest.main()
