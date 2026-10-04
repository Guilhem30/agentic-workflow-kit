"""Spec 006: `agentkit status`."""
from __future__ import annotations

import json
import unittest

from tests.support import RepoTestCase, run_cli

ACTIONS = {
    "draft": "run /spec {n}, then HUMAN approves",
    "approved": "run /write-tests {n}",
    "tests-draft": "HUMAN reviews the tests",
    "tests-approved": "HUMAN runs /freeze {n}",
    "frozen": "run /implement {n}",
}


class StatusCase(RepoTestCase):
    def spec(self, num, status, slug="fixture", depends=None):
        dep = "" if depends is None else "depends: " + json.dumps(list(depends)) + "\n"
        return self.write(f"specs/{num}-{slug}/spec.md",
                          f'---\nid: "{num}"\ntitle: Fixture {num}\nstatus: {status}\n{dep}---\n\n'
                          f"# {num} Fixture\n\nBody.\n")

    def lines(self):
        from agentkit.status import status_lines
        return status_lines(self.cfg())

    def spec_lines(self):
        return [l for l in self.lines() if l.startswith("spec ")]

    def frozen_file(self, rel="tests/test_x.py", spec="011"):
        self.write(rel, "x\n")
        self.write_lock({rel: spec})


class TestLineOne(StatusCase):
    def test_R006_02_lock_ok(self):
        self.frozen_file("tests/a.py")
        self.write("tests/b.py", "y\n")
        self.write_lock(["tests/a.py", "tests/b.py"])
        self.assertEqual(self.lines()[0], "agentkit: profile fixture | frozen files: 2 | lock: OK")

    def test_R006_02_no_lock(self):
        self.assertEqual(self.lines()[0], "agentkit: profile fixture | frozen files: 0 | lock: OK")

    def test_R006_02_lock_violated(self):
        self.frozen_file()
        self.write("tests/test_x.py", "changed\n")
        self.assertEqual(self.lines()[0],
                         "agentkit: profile fixture | frozen files: 1 | lock: VIOLATED "
                         "(1 file(s): run `agentkit lock verify`)")

    def test_R006_08_broken_lock(self):
        self.lock_file.write_text("{not json", encoding="utf-8")
        self.assertIn("| lock: BROKEN (", self.lines()[0])
        code, out = run_cli("status")
        self.assertEqual(code, 0)
        self.assertIn("lock: BROKEN (", out.splitlines()[0])


class TestSpecLines(StatusCase):
    def test_R006_03_one_line_per_active_spec_in_order(self):
        self.spec("012", "tests-draft")
        self.spec("010", "draft")
        self.spec("011", "done")
        self.spec("013", "dropped")
        self.spec("014", "approved")
        self.assertEqual(self.spec_lines(), [
            "spec 010 fixture [draft] -> run /spec 010, then HUMAN approves",
            "spec 012 fixture [tests-draft] -> HUMAN reviews the tests",
            "spec 014 fixture [approved] -> run /write-tests 014",
        ])

    def test_R006_03_action_per_phase(self):
        for phase, action in ACTIONS.items():
            with self.subTest(phase=phase):
                self.spec("012", phase)
                self.assertEqual(self.spec_lines(),
                                 [f"spec 012 fixture [{phase}] -> {action.format(n='012')}"])

    def test_R006_13_blocked_by_listed_last(self):
        self.spec("010", "frozen", depends=["011", "013"])
        self.spec("011", "approved")
        self.spec("012", "frozen", depends=["014"])
        self.spec("013", "done")
        self.spec("014", "done")
        self.spec("015", "done")
        self.spec("016", "frozen", depends=["015"])
        self.assertEqual(self.spec_lines(), [
            "spec 011 fixture [approved] -> run /write-tests 011",
            "spec 012 fixture [frozen] -> run /implement 012",
            "spec 016 fixture [frozen] -> run /implement 016",
            "spec 010 fixture [frozen] -> blocked by 011",
        ])

    def test_R006_13_several_blockers(self):
        self.spec("010", "approved")
        self.spec("011", "draft")
        self.spec("012", "frozen", depends=["010", "011"])
        self.assertIn("spec 012 fixture [frozen] -> blocked by 010, 011", self.spec_lines())

    def test_R006_13_dropped_blocker_still_blocks(self):
        self.spec("010", "dropped")
        self.spec("012", "frozen", depends=["010"])
        self.assertEqual(self.spec_lines(), ["spec 012 fixture [frozen] -> blocked by 010"])

    def test_R006_04_progress_next_for_frozen(self):
        self.spec("012", "frozen")
        self.write("specs/012-fixture/progress.md", "# p\n\n- notes\n\n**Next:** fix the parser\n")
        self.spec("013", "approved")
        self.write("specs/013-fixture/progress.md", "**Next:** ignored for this phase\n")
        self.assertEqual(self.spec_lines(), [
            "spec 012 fixture [frozen] -> run /implement 012 (progress: fix the parser)",
            "spec 013 fixture [approved] -> run /write-tests 013",
        ])

    def test_R006_05_overflow(self):
        for i in range(9):
            self.spec(f"0{10 + i}", "approved")
        lines = self.lines()
        self.assertEqual(len(lines), 10)
        self.assertEqual(len([l for l in lines if l.startswith("spec ")]), 7)
        self.assertEqual(lines[8], "... 2 more active spec(s)")
        self.assertEqual(lines[9], "next: run /write-tests 010")


class TestLastLine(StatusCase):
    def test_R006_06_next_action_of_first_active_spec(self):
        self.spec("010", "frozen", depends=["011"])
        self.spec("011", "tests-approved")
        self.assertEqual(self.lines()[-1], "next: HUMAN runs /freeze 011")

    def test_R006_06_lock_violation_first(self):
        self.spec("010", "approved")
        self.frozen_file()
        self.write("tests/test_x.py", "changed\n")
        last = self.lines()[-1].lower()
        self.assertIn("restore", last)
        self.assertIn("owner", last)
        self.assertIn("unfreeze", last)
        self.assertNotIn("write-tests", last)

    def test_R006_06_violation_line_kept_on_overflow(self):
        for i in range(12):
            self.spec(f"0{10 + i}", "approved")
        self.frozen_file()
        self.write("tests/test_x.py", "changed\n")
        lines = self.lines()
        self.assertLessEqual(len(lines), 10)
        self.assertIn("restore", lines[-1].lower())
        self.assertTrue(any(l.startswith("... ") and l.endswith("more active spec(s)") for l in lines))

    def test_R006_07_no_active_spec(self):
        self.spec("010", "done")
        self.spec("011", "dropped")
        text = "\n".join(self.lines())
        self.assertIn("/spec", text)
        self.assertIn("agentkit new-spec", text)
        self.assertNotIn("/kickoff", text)

    def test_R006_07_no_spec_at_all(self):
        text = "\n".join(self.lines()[1:])
        self.assertIn("/kickoff", text)
        self.assertNotIn("new-spec", text)


class TestLimits(StatusCase):
    def test_R006_01_at_most_10_lines_of_200_chars(self):
        self.spec("012", "frozen", slug="s" + "l" * 20)
        self.write("specs/012-s" + "l" * 20 + "/progress.md", "**Next:** " + "n" * 500 + "\n")
        for i in range(15):
            self.spec(f"0{20 + i}", "draft")
        lines = self.lines()
        self.assertLessEqual(len(lines), 10)
        self.assertTrue(all(len(l) <= 200 for l in lines), [len(l) for l in lines])

    def test_R006_01_cli_prints_lines(self):
        self.spec("012", "approved")
        code, out = run_cli("status")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), self.lines())


if __name__ == "__main__":
    unittest.main()
