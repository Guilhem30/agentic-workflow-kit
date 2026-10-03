"""Spec 007: compact test runner (`agentkit test`)."""
from __future__ import annotations

import json
import os
import re
import sys
import time
import unittest
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from tests.support import FIXTURE_PROFILE, RepoTestCase, run_cli

FAKE = r'''
import json, os, sys
from pathlib import Path
here = Path(__file__).resolve().parent
(here / "ran.json").write_text(json.dumps({"cwd": os.getcwd(), "argv": sys.argv[1:]}))
b = json.loads((here / "behave.json").read_text())
for rel, xml in b.get("reports", {}).items():
    p = here / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(xml)
for line in b.get("stdout", []):
    print(line)
sys.stdout.flush()
for line in b.get("stderr", []):
    print(line, file=sys.stderr)
sys.exit(b.get("exit", 0))
'''

PY = f'"{sys.executable}"'


def junit(cases, time_attr="1.5") -> str:
    """cases: (classname, name, kind, message, text); kind in None, failure, error, skipped."""
    body = []
    for cls, name, kind, message, text in cases:
        inner = ""
        if kind in ("failure", "error"):
            inner = f"<{kind} message={quoteattr(message)}>{escape(text)}</{kind}>"
        elif kind == "skipped":
            inner = "<skipped/>"
        body.append(f'<testcase classname="{cls}" name="{name}" time="0.1">{inner}</testcase>')
    n = lambda k: sum(1 for c in cases if c[2] == k)
    return (f'<?xml version="1.0"?>\n<testsuite name="s" tests="{len(cases)}" '
            f'failures="{n("failure")}" errors="{n("error")}" skipped="{n("skipped")}" '
            f'time="{time_attr}">' + "".join(body) + "</testsuite>\n")


PASSING = junit([("pkg.A", "t1", None, "", ""), ("pkg.A", "t2", None, "", ""),
                 ("pkg.A", "t3", "skipped", "", "")])


class RunnerCase(RepoTestCase):
    JUNIT = '["**/TEST-*.xml"]'
    FILTER = ""

    def setUp(self) -> None:
        super().setUp()
        self.write(".agentkit/profiles/fixture.toml", self.profile_body())
        self.write("fake.py", FAKE)
        self.write(".gitignore", "build/\nran.json\n")
        self.behave()

    def profile_body(self) -> str:
        return (FIXTURE_PROFILE
                + f"test_cmd = '{PY} fake.py posix'\n"
                + f"test_cmd_windows = '{PY} fake.py win'\n"
                + f"test_one_cmd = '{PY} fake.py one {{scope}}'\n"
                + f"test_one_cmd_windows = '{PY} fake.py one-win {{scope}}'\n"
                + f"junit_report_glob = {self.JUNIT}\n"
                + f"output_filter_regex = '{self.FILTER}'\n")

    def behave(self, exit=0, stdout=(), stderr=(), reports=None) -> None:
        self.write("behave.json", json.dumps({"exit": exit, "stdout": list(stdout),
                                              "stderr": list(stderr), "reports": reports or {}}))

    def ran(self) -> dict:
        return json.loads((self.root / "ran.json").read_text())

    def run_tests(self, scope=None):
        from agentkit.runtests import run_tests
        return run_tests(self.cfg(), scope)

    def old_report(self, rel: str, xml: str) -> None:
        p = self.write(rel, xml)
        past = time.time() - 5
        os.utime(p, (past, past))


FIRST = re.compile(r"^(PASS|FAIL): (\d+) passed, (\d+) failed, (\d+) errors, (\d+) skipped "
                   r"\(\d+(\.\d+)?s, (\d+) report\(s\)\)")


# Command ----------------------------------------------------------------------------------

class TestCommand(RunnerCase):
    def test_R007_01_runs_test_cmd_at_root(self):
        sub = self.root / "deep" / "dir"
        sub.mkdir(parents=True)
        os.chdir(sub)
        self.behave(reports={"build/TEST-a.xml": PASSING})
        self.run_tests()
        ran = self.ran()
        self.assertTrue(os.path.samefile(ran["cwd"], self.root))
        self.assertEqual(ran["argv"], ["win"] if os.name == "nt" else ["posix"])

    def test_R007_01_through_the_shell(self):
        self.write(".agentkit/profiles/fixture.toml", FIXTURE_PROFILE
                   + f"test_cmd = '{PY} fake.py a && {PY} fake.py b'\n"
                   + f"test_cmd_windows = '{PY} fake.py a && {PY} fake.py b'\n")
        self.run_tests()
        self.assertEqual(self.ran()["argv"], ["b"])

    def test_R007_02_scope_replaced(self):
        self.run_tests("pkg.mod_x")
        self.assertEqual(self.ran()["argv"], ["one-win" if os.name == "nt" else "one", "pkg.mod_x"])

    def test_R007_03_missing_test_cmd(self):
        self.write(".agentkit/profiles/fixture.toml", FIXTURE_PROFILE)
        code, out = run_cli("test")
        self.assertEqual(code, 2)
        self.assertIn("test_cmd", out)
        self.assertFalse((self.root / "ran.json").exists())

    def test_R007_03_missing_test_one_cmd(self):
        self.write(".agentkit/profiles/fixture.toml", FIXTURE_PROFILE
                   + f"test_cmd = '{PY} fake.py posix'\ntest_cmd_windows = '{PY} fake.py win'\n")
        code, out = run_cli("test", "pkg.mod")
        self.assertEqual(code, 2)
        self.assertIn("test_one_cmd", out)
        self.assertFalse((self.root / "ran.json").exists())

    def test_R007_04_log_has_stdout_and_stderr(self):
        self.behave(exit=1, stdout=["OUT-MARK-1"], stderr=["ERR-MARK-2"])
        self.run_tests()
        log = (self.root / ".agentkit/state/last-test.log").read_text(encoding="utf-8")
        self.assertIn("OUT-MARK-1", log)
        self.assertIn("ERR-MARK-2", log)

    def test_R007_05_exit_code_passed_through(self):
        self.behave(exit=3)
        code, _ = self.run_tests()
        self.assertEqual(code, 3)
        self.behave(exit=0, reports={"build/TEST-a.xml": PASSING})
        code, _ = self.run_tests()
        self.assertEqual(code, 0)

    def test_R007_05_cli_exit_code_and_output(self):
        self.behave(exit=4, reports={"build/TEST-a.xml": PASSING})
        code, out = run_cli("test")
        self.assertEqual(code, 4)
        self.assertRegex(out.splitlines()[0], FIRST)


# JUnit summary ----------------------------------------------------------------------------

class TestJunit(RunnerCase):
    def test_R007_06_parse_counts(self):
        from agentkit.runtests import parse_junit
        a = self.write("r/TEST-a.xml", junit([("p.A", "t1", None, "", ""),
                                              ("p.A", "t2", "failure", "bad", "trace"),
                                              ("p.A", "t3", "skipped", "", "")], "2.0"))
        b = self.write("r/TEST-b.xml", junit([("p.B", "t1", "error", "boom", ""),
                                              ("p.B", "t2", None, "", "")], "0.5"))
        s = parse_junit([a, b])
        self.assertEqual((s.tests, s.failures, s.errors, s.skipped, s.reports), (5, 1, 1, 1, 2))
        self.assertEqual(s.passed, 2)
        self.assertGreaterEqual(s.time, 0)
        self.assertEqual(sorted((f.kind.upper(), f.name) for f in s.failed),
                         [("ERROR", "p.B.t1"), ("FAILURE", "p.A.t2")])

    def test_R007_06_only_new_reports(self):
        self.old_report("build/TEST-old.xml", junit([("p.Old", "t", "failure", "stale", "")]))
        self.behave(reports={"build/TEST-new.xml": PASSING})
        code, lines = self.run_tests()
        m = FIRST.match(lines[0])
        self.assertIsNotNone(m, lines[0])
        self.assertEqual(m.group(1), "PASS")
        self.assertEqual(m.group(7), "1")
        self.assertNotIn("p.Old", "\n".join(lines))

    def test_R007_06_skips_excluded_dirs_keeps_ignored_build_dirs(self):
        bad = junit([("p.Hidden", "t", "failure", "hidden", "")])
        self.behave(reports={"node_modules/x/TEST-a.xml": bad, ".gradle/TEST-b.xml": bad,
                             ".git/x/TEST-d.xml": bad,
                             ".idea/TEST-c.xml": bad, "build/deep/TEST-ok.xml": PASSING})
        code, lines = self.run_tests()
        m = FIRST.match(lines[0])
        self.assertIsNotNone(m, lines[0])
        self.assertEqual((m.group(1), m.group(7)), ("PASS", "1"))
        self.assertNotIn("p.Hidden", "\n".join(lines))

    def test_R007_07_cached_results(self):
        self.old_report("build/TEST-old.xml", PASSING)
        self.behave(exit=0)
        code, lines = self.run_tests()
        self.assertTrue(lines[0].endswith(
            " [no new reports: results are from the previous run / up-to-date tasks]"), lines[0])
        m = FIRST.match(lines[0])
        self.assertIsNotNone(m, lines[0])
        self.assertEqual(m.groups()[:5], ("PASS", "2", "0", "0", "1"))

    def test_R007_07_no_cached_results_when_the_command_failed(self):
        self.old_report("build/TEST-old.xml", PASSING)
        self.behave(exit=1, stdout=["it broke"])
        code, lines = self.run_tests()
        self.assertTrue(lines[0].startswith("FAIL (exit 1)"), lines[0])
        self.assertNotIn("no new reports", "\n".join(lines))

    def test_R007_06_testsuites_wrapper(self):
        inner = PASSING.split("\n", 1)[1]
        xml = ('<?xml version="1.0"?>\n<testsuites tests="4" failures="1" errors="0" skipped="1">'
               + inner.strip() + junit([("p.B", "t", "failure", "bad", "")]).split("\n", 1)[1].strip()
               + "</testsuites>\n")
        self.behave(exit=1, reports={"build/TEST-a.xml": xml})
        code, lines = self.run_tests()
        m = FIRST.match(lines[0])
        self.assertIsNotNone(m, lines[0])
        self.assertEqual(m.groups()[:5], ("FAIL", "2", "1", "0", "1"))
        self.assertIn("FAILURE p.B.t: bad", lines)

    def test_R007_08_first_line_format(self):
        xml = junit([("p.A", "t1", None, "", ""), ("p.A", "t2", "failure", "bad", ""),
                     ("p.A", "t3", "error", "err", ""), ("p.A", "t4", "skipped", "", "")])
        self.behave(exit=1, reports={"build/TEST-a.xml": xml})
        code, lines = self.run_tests()
        m = FIRST.match(lines[0])
        self.assertIsNotNone(m, lines[0])
        self.assertEqual(m.groups()[:5], ("FAIL", "1", "1", "1", "1"))
        self.assertEqual(m.group(7), "1")

    def test_R007_08_pass_needs_exit_zero(self):
        from agentkit.runtests import Summary, format_summary
        s = Summary(tests=2, failures=0, errors=0, skipped=0, time=0.25, failed=[], reports=1)
        self.assertTrue(format_summary(s, 0)[0].startswith("PASS: 2 passed, 0 failed, 0 errors, 0 skipped ("))
        self.assertTrue(format_summary(s, 1)[0].startswith("FAIL: 2 passed"))
        s2 = Summary(tests=2, failures=1, errors=0, skipped=0, time=0.25, failed=[], reports=1)
        self.assertTrue(format_summary(s2, 0)[0].startswith("FAIL: 1 passed, 1 failed"))
        s3 = Summary(tests=2, failures=0, errors=1, skipped=0, time=0.25, failed=[], reports=1)
        self.assertTrue(format_summary(s3, 0)[0].startswith("FAIL: 1 passed, 0 failed, 1 errors"))

    def test_R007_09_failure_lines_and_frames(self):
        trace = "\n".join([
            "java.lang.AssertionError: boom",
            "\tat java.base/java.lang.Thread.run(Thread.java:1)",
            "\tat com.acme.FooTest.a(FooTest.kt:1)",
            "\tat org.junit.Assert.fail(Assert.java:1)",
            "\tat com.acme.FooTest.b(FooTest.kt:2)",
            "\tat jdk.internal.X(X.java:1)",
            "\tat com.acme.FooTest.c(FooTest.kt:3)",
            "\tat kotlin.Y.z(Y.kt:1)",
            "\tat sun.reflect.Z(Z.java:1)",
            "\tat org.gradle.W(W.java:1)",
            "\tat kotlinx.coroutines.V(V.kt:1)",
            "\tat io.kotest.U(U.kt:1)",
            "\tat com.acme.FooTest.d(FooTest.kt:4)",
            "\tat com.acme.FooTest.e(FooTest.kt:5)",
        ])
        xml = junit([("com.acme.FooTest", "adds", "failure", "boom\nsecond line", trace),
                     ("com.acme.FooTest", "ok", None, "", "")])
        self.behave(exit=1, reports={"build/TEST-a.xml": xml})
        code, lines = self.run_tests()
        i = lines.index("FAILURE com.acme.FooTest.adds: boom")
        frames = lines[i + 1:i + 5]
        self.assertEqual(len(frames), 4)
        self.assertFalse(lines[i + 5:i + 6] and lines[i + 5][:1].isspace(), lines[i + 5:i + 6])
        for frame, tag in zip(frames, "abcd"):
            self.assertTrue(frame[:1].isspace(), frame)
            self.assertIn(f"com.acme.FooTest.{tag}", frame)
        text = "\n".join(lines)
        for excluded in ("java.base", "org.junit.", "jdk.", "kotlin.Y", "sun.", "org.gradle.",
                         "kotlinx.coroutines.", "io.kotest.", "FooTest.e", "second line"):
            self.assertNotIn(excluded, text)

    def test_R007_09_error_kind_and_message_cut(self):
        prefix = "ERROR p.A.t1: "
        xml = junit([("p.A", "t1", "error", "x" * 500, "")])
        self.behave(exit=1, reports={"build/TEST-a.xml": xml})
        code, lines = self.run_tests()
        line = next(l for l in lines if l.startswith(prefix))
        self.assertTrue(line.startswith(prefix + "x" * 50))
        self.assertLessEqual(len(line), len(prefix) + 300)

    def test_R007_10_command_failed_without_test_failures(self):
        self.FILTER = "^e: "
        self.write(".agentkit/profiles/fixture.toml", self.profile_body())
        self.behave(exit=1, stdout=["> Task :compileKotlin", "noise 1",
                                    "e: file.kt:12:5 Unresolved reference: foo", "noise 2"],
                    reports={"build/TEST-a.xml": PASSING})
        code, lines = self.run_tests()
        self.assertEqual(code, 1)
        self.assertTrue(lines[0].startswith("FAIL: "), lines[0])
        text = "\n".join(lines)
        self.assertIn("e: file.kt:12:5 Unresolved reference: foo", text)
        self.assertNotIn("noise", text)
        self.assertGreaterEqual(len(lines), 3)

    def test_R007_10_at_most_30_output_lines(self):
        self.FILTER = "^e: "
        self.write(".agentkit/profiles/fixture.toml", self.profile_body())
        self.behave(exit=1, stdout=[f"e: f.kt:{i}:1 bad" for i in range(50)],
                    reports={"build/TEST-a.xml": PASSING})
        code, lines = self.run_tests()
        shown = [l for l in lines if l.startswith("e: ")]
        self.assertTrue(shown)
        self.assertLessEqual(len(shown), 30)

    def test_R007_11_malformed_report_skipped(self):
        self.behave(reports={"build/TEST-bad.xml": "<testsuite><testcase",
                             "build/TEST-good.xml": PASSING})
        code, lines = self.run_tests()
        m = FIRST.match(lines[0])
        self.assertIsNotNone(m, lines[0])
        self.assertEqual(m.groups()[:5], ("PASS", "2", "0", "0", "1"))

    def test_R007_11_parse_junit_skips_malformed(self):
        from agentkit.runtests import parse_junit
        bad = self.write("r/TEST-bad.xml", "not xml at all")
        good = self.write("r/TEST-good.xml", PASSING)
        s = parse_junit([bad, good])
        self.assertEqual((s.tests, s.skipped), (3, 1))


# Without JUnit reports --------------------------------------------------------------------

class TestNoReports(RunnerCase):
    JUNIT = "[]"
    FILTER = "^ERR"

    def test_R007_12_pass_with_command(self):
        self.behave(exit=0, stdout=["all good"])
        code, lines = self.run_tests()
        self.assertTrue(lines[0].startswith("PASS"), lines[0])
        self.assertIn("fake.py", "\n".join(lines[:2]))

    def test_R007_12_fail_filtered_lines(self):
        out = [f"ERR {i} " + "y" * (500 if i == 41 else 1) if i % 2 else f"ok {i}"
               for i in range(100)]
        self.behave(exit=2, stdout=out)
        code, lines = self.run_tests()
        self.assertEqual(code, 2)
        self.assertTrue(lines[0].startswith("FAIL (exit 2)"), lines[0])
        body = [l for l in lines if l.startswith("ERR ")]
        self.assertTrue(body)
        self.assertLessEqual(len(body), 40)
        self.assertNotIn("ok 2", "\n".join(lines))
        self.assertTrue(all(len(l) <= 300 for l in lines), max(map(len, lines)))
        text = "\n".join(lines)
        for i in range(21, 80, 2):  # kept whether the first or the last 40 matches are shown
            self.assertIn(f"ERR {i} y", text)

    def test_R007_12_no_match_shows_last_lines(self):
        self.behave(exit=1, stdout=[f"line {i}" for i in range(100)])
        code, lines = self.run_tests()
        body = [l for l in lines if l.startswith("line ")]
        self.assertIn("line 99", body)
        self.assertNotIn("line 0", body)
        self.assertLessEqual(len(body), 40)

    def test_R007_12_report_glob_set_but_no_report(self):
        self.write(".agentkit/profiles/fixture.toml", self.profile_body().replace(
            "junit_report_glob = []", 'junit_report_glob = ["**/TEST-*.xml"]'))
        self.behave(exit=1, stdout=["ERR broken"])
        code, lines = self.run_tests()
        self.assertTrue(lines[0].startswith("FAIL (exit 1)"), lines[0])
        self.assertIn("ERR broken", "\n".join(lines))


# Limits and state -------------------------------------------------------------------------

class TestLimits(RunnerCase):
    def test_R007_13_cap_at_60_lines(self):
        cases = [("p.A", f"t{i}", "failure", f"bad {i}", "") for i in range(200)]
        self.behave(exit=1, reports={"build/TEST-a.xml": junit(cases)})
        code, lines = self.run_tests()
        self.assertEqual(len(lines), 60)
        self.assertIn("142", lines[-1])
        self.assertRegex(lines[-1], r"\.agentkit[/\\]state[/\\]last-test\.log")

    def test_R007_13_no_note_when_short(self):
        self.behave(reports={"build/TEST-a.xml": PASSING})
        code, lines = self.run_tests()
        self.assertNotIn("last-test.log", "\n".join(lines))

    def test_R007_14_first_10_lines_saved(self):
        cases = [("p.A", f"t{i}", "failure", f"bad {i}", "") for i in range(20)]
        self.behave(exit=1, reports={"build/TEST-a.xml": junit(cases)})
        code, lines = self.run_tests()
        saved = (self.root / ".agentkit/state/last-test.txt").read_text(encoding="utf-8")
        self.assertEqual(saved.splitlines(), lines[:10])


if __name__ == "__main__":
    unittest.main()
