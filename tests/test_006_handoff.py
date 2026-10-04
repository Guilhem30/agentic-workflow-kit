"""Spec 006: `agentkit handoff`."""
from __future__ import annotations

import os
import re
import unittest
from datetime import datetime, timedelta, timezone

from tests.support import RepoTestCase, run_cli

BEGIN = "<!-- agentkit:snapshot:begin -->"
END = "<!-- agentkit:snapshot:end -->"
NOW = datetime(2026, 10, 3, 12, 34, 56, tzinfo=timezone.utc)
TASKS = "# tasks\n\n- [x] T1 done thing\n- [ ] T2 write the parser\n- [ ] T3 other\n"


class HandoffCase(RepoTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write("specs/012-fixture/spec.md",
                   '---\nid: "012"\ntitle: Fixture\nstatus: frozen\n---\n\n# 012\n')
        self.write("specs/012-fixture/tasks.md", TASKS)

    @property
    def progress(self):
        return self.root / "specs/012-fixture/progress.md"

    def snap(self, **kw):
        from agentkit.handoff import snapshot
        kw.setdefault("now", NOW)
        return snapshot(self.cfg(), "012", **kw)

    def block_lines(self, text):
        return [l for l in text.splitlines() if l.strip() and l.strip() not in (BEGIN, END)]


class TestWrite(HandoffCase):
    def test_R006_09_replaces_block_keeps_rest(self):
        head = "# 012 progress\n\nHand-written notes.\n\n"
        tail = "\nAfter the block.\n"
        self.write(self.progress, f"{head}{BEGIN}\nold snapshot\n{END}\n{tail}")
        code, _ = run_cli("handoff", "012", "--next", "go on")
        self.assertEqual(code, 0)
        text = self.progress.read_text(encoding="utf-8")
        self.assertTrue(text.startswith(head), text)
        self.assertTrue(text.endswith(tail), text)
        self.assertNotIn("old snapshot", text)
        self.assertEqual(text.count(BEGIN), 1)
        self.assertEqual(text.count(END), 1)
        self.assertIn("**Next:** go on", text)

    def test_R006_09_appends_block(self):
        self.write(self.progress, "# 012 progress\n\n- a note\n")
        run_cli("handoff", "012")
        text = self.progress.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# 012 progress\n\n- a note\n"))
        self.assertLess(text.index("- a note"), text.index(BEGIN))
        self.assertLess(text.index(BEGIN), text.index(END))

    def test_R006_09_creates_progress_when_missing(self):
        code, _ = run_cli("handoff", "012")
        self.assertEqual(code, 0)
        text = self.progress.read_text(encoding="utf-8")
        self.assertIn(BEGIN, text)
        self.assertIn(END, text)

    def test_R006_09_twice_changes_only_the_block(self):
        self.write(self.progress, f"# p\n\nnotes\n\n{BEGIN}\nx\n{END}\n\ntrailer\n")
        run_cli("handoff", "012", "--next", "next-AAA")
        once = self.progress.read_text(encoding="utf-8")
        run_cli("handoff", "012", "--next", "next-BBB")
        twice = self.progress.read_text(encoding="utf-8")
        strip = lambda t: re.sub(re.escape(BEGIN) + ".*?" + re.escape(END), "", t, flags=re.S)
        self.assertEqual(strip(once), strip(twice))
        self.assertIn("**Next:** next-BBB", twice)
        self.assertNotIn("next-AAA", twice)


class TestContent(HandoffCase):
    def test_R006_10_timestamp_phase_tasks(self):
        text = self.snap()
        self.assertIn("2026-10-03", text)
        self.assertIn("12:34", text)
        self.assertIn("frozen", text)
        self.assertIn("Tasks: 1/3 done", text)
        tasks_line = next(l for l in text.splitlines() if "Tasks: 1/3 done" in l)
        self.assertIn("T2 write the parser", tasks_line)

    def test_R006_10_timestamp_in_utc(self):
        local = NOW.astimezone(timezone(timedelta(hours=2)))  # 14:34 at UTC+2
        text = self.snap(now=local)
        self.assertIn("12:34", text)
        self.assertNotIn("14:34", text)

    def test_R006_10_last_test_summary_first_9_lines(self):
        self.write(".agentkit/state/last-test.txt",
                   "".join(f"summary line {i}\n" for i in range(1, 11)))
        text = self.snap()
        for i in range(1, 10):
            self.assertIn(f"summary line {i}\n", text + "\n")
        self.assertNotIn("summary line 10", text)

    def test_R006_10_no_test_summary(self):
        text = self.snap()
        self.assertNotIn("summary line", text)

    def test_R006_10_git_branch_and_uncommitted(self):
        self.write("one.txt", "a\n")
        self.write("two.txt", "b\n")
        self.commit_all("base")
        self.git("checkout", "-q", "-b", "feature-x")
        self.write("one.txt", "a changed\n")
        self.write("two.txt", "b changed\n")
        text = self.snap()
        line = next(l for l in text.splitlines() if "feature-x" in l)
        self.assertRegex(line, r"\b2\b")

    def test_R006_10_note_and_final_next_line(self):
        text = self.snap(note="tried X, it failed on Windows", next_step="try Y")
        self.assertIn("tried X, it failed on Windows", text)
        self.assertEqual(self.block_lines(text)[-1], "**Next:** try Y")

    def test_R006_11_next_defaults_to_first_open_task(self):
        self.assertEqual(self.block_lines(self.snap())[-1], "**Next:** T2 write the parser")

    def test_R006_11_next_defaults_to_phase_action(self):
        self.write("specs/012-fixture/tasks.md", "- [x] T1 a\n- [x] T2 b\n")
        text = self.snap()
        self.assertIn("Tasks: 2/2 done", text)
        self.assertEqual(self.block_lines(text)[-1], "**Next:** run /implement 012")

    def test_R006_11_cli_next_option(self):
        run_cli("handoff", "012", "--note", "a note", "--next", "ship it")
        text = self.progress.read_text(encoding="utf-8")
        self.assertIn("a note", text)
        self.assertEqual(self.block_lines(text)[-1], "**Next:** ship it")


class TestNoGit(HandoffCase):
    USE_GIT = False

    def test_R006_10_no_branch_outside_git(self):
        os.environ["GIT_CEILING_DIRECTORIES"] = str(self.tmp)
        text = self.snap(next_step="n")
        self.assertNotIn("branch", text.lower())


class TestMissing(HandoffCase):
    def test_R006_12_unknown_spec(self):
        before = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*")
                        if ".git" not in p.parts)
        code, out = run_cli("handoff", "099")
        self.assertEqual(code, 1)
        self.assertIn("099", out)
        after = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*")
                       if ".git" not in p.parts)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
