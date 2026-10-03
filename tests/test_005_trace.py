"""Spec 005: `agentkit trace` (R005-12 to R005-16, R005-18) and the spec's examples. The
fixture spec is 004; its IDs are built with rid()."""
from __future__ import annotations

from agentkit import trace
from tests.spec_fixtures import SpecCase
from tests.support import rid, run_cli


def r(n: str, sep: str = "-") -> str:
    return rid("004", n, sep)


DECLARED = (f"- **{r('01')}** one\n- **{r('02')}** two\n- **{r('03')}** three [manual]\n"
            f"- **{rid('004', '04')}** four\n")


class TraceCase(SpecCase):

    def spec004(self, status="tests-draft", body=DECLARED, num="004", slug="fixture"):
        return self.spec(num, slug, status=status, body=body)

    def add_test(self, name, text):
        self.write(f"tests/{name}", text)


class TraceTests(TraceCase):

    def test_R005_12_traced_phases_only(self):
        for num, phase in (("001", "draft"), ("002", "approved"), ("003", "tests-draft"),
                           ("004", "tests-approved"), ("005", "frozen"), ("006", "done"),
                           ("007", "dropped")):
            self.spec(num, status=phase, body=f"- **{rid(num, '01')}** x\n")
        results = trace.trace_specs(self.cfg())
        self.assertEqual(sorted(res.spec for res in results), ["003", "004", "005", "006"])
        code, out = run_cli("trace")
        self.assertEqual(code, 1)
        for num in ("003", "004", "005", "006"):
            self.assertIn(f"spec {num}: 0/1 requirements traced [MISSING]", out)
        for num in ("001", "002", "007"):
            self.assertNotIn(f"spec {num}:", out)

    def test_R005_12_spec_option_any_phase(self):
        for phase in ("draft", "approved", "dropped", "done"):
            self.spec004(status=phase)
            self.add_test("test_a.py", f"def test_{r('01', '_')}(): pass\n")
            results = trace.trace_specs(self.cfg(), "004")
            self.assertEqual([res.spec for res in results], ["004"], phase)
            code, out = run_cli("trace", "--spec", "004")
            self.assertEqual(code, 1, phase)
            self.assertIn("spec 004: 1/3 requirements traced [MISSING]", out)

    def test_R005_13_test_globs_only(self):
        self.spec004()
        self.add_test("unit/test_a.py", f"def test_{r('01', '_')}(): pass\n")
        self.write("app/src/test/BTest.kt", f"// {r('02')}\n")
        self.write("src/impl.py", f"# implements {r('04')}\n")
        self.write("docs/notes.md", f"{r('04')}\n")
        res = trace.trace_specs(self.cfg(), "004")[0]
        self.assertEqual(sorted(res.covered), [r("01"), r("02")])
        self.assertEqual(res.covered[r("01")], ["tests/unit/test_a.py"])
        self.assertEqual(res.covered[r("02")], ["app/src/test/BTest.kt"])
        self.assertEqual(res.missing, [r("04")])

    def test_R005_13_build_output_ignored(self):
        self.spec004()
        self.write("tests/build/gen_test.py", f"{r('01')} {r('02')} {rid('004', '04')}\n")
        self.write("tests/__pycache__/x.py", f"{r('01')}\n")
        res = trace.trace_specs(self.cfg(), "004")[0]
        self.assertEqual(res.covered, {})
        self.assertFalse(res.ok)

    def test_R005_13_any_accepted_form(self):
        self.spec004()
        self.add_test("a.py", f"def test_{r('01', '_')}_x(): pass\n")
        self.add_test("b.txt", f"`{r('02')} …`\n")
        self.add_test("c.py", f"x = '{rid('004', '04')}'\n")
        res = trace.trace_specs(self.cfg(), "004")[0]
        self.assertTrue(res.ok)
        self.assertEqual(sorted(res.covered), [r("01"), r("02"), rid("004", "04")])

    def test_R005_13_lookalikes_do_not_count(self):
        self.spec004()
        self.add_test("a.py", f"X{r('01')} {r('02')}9 {r('04')[1:]}\n")
        res = trace.trace_specs(self.cfg(), "004")[0]
        self.assertEqual(res.covered, {})

    def test_R005_14_output_format(self):
        self.spec004()
        self.add_test("a.py", f"test_{r('01', '_')}\n")
        res = trace.trace_specs(self.cfg(), "004")
        lines = trace.format_results(res)
        self.assertEqual(lines[0], "spec 004: 1/3 requirements traced [MISSING]")
        untraced = lines[1:3]
        self.assertTrue(any(r("02") in line for line in untraced), lines)
        self.assertTrue(any(rid("004", "04") in line for line in untraced), lines)
        self.assertEqual(len(lines), 3, lines)

    def test_R005_14_ok_line(self):
        self.spec004()
        self.add_test("a.py", f"{r('01')} {r('02')} {rid('004', '04')}\n")
        lines = trace.format_results(trace.trace_specs(self.cfg(), "004"))
        self.assertEqual(lines, ["spec 004: 3/3 requirements traced [OK]"])

    def test_R005_15_undeclared_id_warns(self):
        self.spec004()
        self.add_test("a.py", f"{r('01')} {r('02')} {rid('004', '04')}\n")
        self.add_test("b.py", f"{r('09')}\n")
        res = trace.trace_specs(self.cfg(), "004")[0]
        self.assertTrue(res.ok)
        self.assertIn(r("09"), res.unknown)
        code, out = run_cli("trace", "--spec", "004")
        self.assertEqual(code, 0)
        warn = [line for line in out.splitlines() if r("09") in line]
        self.assertEqual(len(warn), 1, out)
        self.assertIn("tests/b.py", warn[0])

    def test_R005_15_excluded_id_warns(self):
        self.spec004()
        self.add_test("a.py", f"{r('01')} {r('02')} {rid('004', '04')} {r('03')}\n")
        res = trace.trace_specs(self.cfg(), "004")[0]
        self.assertTrue(res.ok)
        self.assertIn(r("03"), res.unknown)
        self.assertNotIn(r("03"), res.covered)
        code, out = run_cli("trace", "--spec", "004")
        self.assertEqual(code, 0)
        self.assertTrue(any(r("03") in line and "tests/a.py" in line
                            for line in out.splitlines()), out)

    def test_R005_15_one_file_named(self):
        self.spec004()
        self.add_test("a.py", f"{r('09')}\n")
        self.add_test("b.py", f"{r('09')}\n")
        code, out = run_cli("trace", "--spec", "004")
        warn = [line for line in out.splitlines() if r("09") in line]
        self.assertEqual(len(warn), 1, out)
        self.assertEqual(sum(f in warn[0] for f in ("tests/a.py", "tests/b.py")), 1, warn)

    def test_R005_16_untraced_fails(self):
        self.spec004()
        self.add_test("a.py", f"{r('01')}\n")
        code, out = run_cli("trace")
        self.assertEqual(code, 1)
        self.assertIn("[MISSING]", out)

    def test_R005_16_one_bad_spec_fails_all(self):
        self.spec004()
        self.spec("006", status="done", body=f"- **{rid('006', '01')}** x\n")
        self.add_test("a.py", f"{r('01')} {r('02')} {rid('004', '04')}\n")
        code, out = run_cli("trace")
        self.assertEqual(code, 1)
        self.assertIn("spec 004: 3/3 requirements traced [OK]", out)
        self.assertIn("spec 006: 0/1 requirements traced [MISSING]", out)

    def test_R005_16_all_traced_passes(self):
        self.spec004()
        self.add_test("a.py", f"{r('01')} {r('02')} {rid('004', '04')}\n")
        code, out = run_cli("trace")
        self.assertEqual(code, 0, out)

    def test_R005_16_unknown_spec(self):
        self.spec004()
        code, out = run_cli("trace", "--spec", "042")
        self.assertEqual(code, 1)
        self.assertIn("042", out)

    def test_R005_16_nothing_to_trace(self):
        self.spec004(status="approved")
        self.assertEqual(trace.trace_specs(self.cfg()), [])
        code, out = run_cli("trace")
        self.assertEqual(code, 0)
        self.assertTrue(out.strip())

    def test_R005_16_no_specs_at_all(self):
        code, out = run_cli("trace")
        self.assertEqual(code, 0)
        self.assertTrue(out.strip())

    def test_R005_18_dropped_skipped(self):
        self.spec004(status="dropped")
        self.spec("006", status="done", body=f"- **{rid('006', '01')}** x\n")
        self.add_test("a.py", f"{rid('006', '01')}\n")
        code, out = run_cli("trace")
        self.assertEqual(code, 0, out)
        self.assertNotIn("spec 004", out)

    def test_R005_13_result_fields(self):
        self.spec004()
        self.add_test("a.py", f"{r('01')}\n")
        self.add_test("b.py", f"{r('01')} {r('09')}\n")
        res = trace.trace_specs(self.cfg(), "004")[0]
        self.assertEqual(res.spec, "004")
        self.assertEqual(res.required, [r("01"), r("02"), rid("004", "04")])
        self.assertEqual(sorted(res.covered[r("01")]), ["tests/a.py", "tests/b.py"])
        self.assertEqual(res.unknown, {r("09"): ["tests/b.py"]})
        self.assertEqual(res.missing, [r("02"), rid("004", "04")])
        self.assertFalse(res.ok)


class NoGitTraceTests(TraceCase):
    USE_GIT = False

    def test_R005_13_without_git(self):
        self.spec004()
        self.add_test("a.py", f"{r('01')} {r('02')} {rid('004', '04')}\n")
        self.write("tests/build/x.py", f"{r('09')}\n")
        code, out = run_cli("trace", "--spec", "004")
        self.assertEqual(code, 0, out)
        self.assertNotIn(r("09"), out)


class ExampleTests(TraceCase):
    """The spec's examples: 004 declares 01..03, 03 is [manual]."""

    def test_R005_14_example_two_of_two(self):
        self.spec004(body=f"- **{r('01')}** a\n- **{r('02')}** b\n- **{r('03')}** c [manual]\n"
                          f"- see {rid('001', '05')}\n")
        self.add_test("x.md", f"`{r('01')} …`\n")
        self.add_test("test_x.py", f"def test_{r('02', '_')}_x(): pass\n")
        code, out = run_cli("trace")
        self.assertEqual(code, 0, out)
        self.assertIn("spec 004: 2/2 requirements traced [OK]", out)

    def test_R005_10_example_reference_not_counted(self):
        self.spec004(body=f"- **{r('01')}** relies on {rid('001', '05')}\n")
        self.add_test("a.py", f"{r('01')}\n")
        res = trace.trace_specs(self.cfg(), "004")[0]
        self.assertEqual(res.required, [r("01")])
        self.assertTrue(res.ok)

    def test_R005_15_example_undeclared_warning_only(self):
        self.spec004(body=f"- **{r('01')}** a\n")
        self.add_test("a.py", f"{r('01')} {r('09')}\n")
        code, out = run_cli("trace")
        self.assertEqual(code, 0)
        self.assertIn(r("09"), out)
