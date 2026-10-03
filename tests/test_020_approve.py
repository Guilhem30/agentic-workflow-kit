"""Spec 020: `chaos approve` - gates and phases (R020-15 to R020-18, R020-20 to R020-22), the
critical checks (R020-19), `needs owner` (R020-43) and the order of checks (R020-38)."""
from __future__ import annotations

from agentkit import chaos
from tests.chaos_fixtures import (AUDIT_PASS, CHAOS_ON, FAIL, IMPL_PASS, NOW, OWNER, SPEC_PASS,
                                  ChaosCase)
from tests.support import rid, run_cli

HINT = "agentkit chaos log --open"


class ApproveCase(ChaosCase):

    def approve_cli(self, spec: str, gate: str, last_line: str | None = None, name="review"):
        args = ["chaos", "approve", spec, gate]
        if last_line is not None:
            args += ["--review", self.review(last_line, name=name)]
        return run_cli(*args)

    def assert_nothing_written(self, num: str = "012", status: str | None = None):
        self.assertFalse(self.chaos_log.exists())
        self.assertFalse((self.spec_dir(num) / "reviews").exists())
        if status is not None:
            self.assertEqual(self.spec_status(num), status)

    def escalation(self, seq, cause="owner"):
        return self.record(seq, "escalate", spec="012", gate="approved", cause=cause, detail=["x"])

    def traced(self, num="012", status="tests-draft", reqs=("01", "02"), covered=("01", "02")):
        """Spec NNN with requirements, and a test file naming the covered ones; committed."""
        self.spec(num, status, reqs=reqs)
        body = "".join(f"def test_{rid(num, r, '_')}_works():\n    pass\n" for r in covered)
        self.write(f"tests/test_{num}_x.py", body)
        self.commit_all("traced spec")


class UsageTests(ApproveCase):

    def test_R020_15_unknown_gate_exit_2(self):
        for gate in ("draft", "tests-draft", "dropped", "bogus"):
            with self.subTest(gate=gate):
                code, _ = self.approve_cli("012", gate, SPEC_PASS)
                self.assertEqual(code, 2)
        self.assert_nothing_written(status="draft")

    def test_R020_15_review_required_except_for_frozen(self):
        for gate in ("approved", "tests-approved", "done"):
            with self.subTest(gate=gate):
                code, out = self.approve_cli("012", gate)
                self.assertEqual(code, 2)
                self.assertIn("--review", out)
        self.assert_nothing_written(status="draft")

    def test_R020_15_frozen_refuses_a_review(self):
        self.spec("012", "tests-approved")
        self.commit_all("tests approved")
        code, _ = self.approve_cli("012", "frozen", AUDIT_PASS)
        self.assertEqual(code, 2)
        self.assertEqual(self.spec_status("012"), "tests-approved")
        self.assertFalse(self.lock_file.exists())
        self.assertFalse(self.chaos_log.exists())

    def test_R020_15_api_usage_errors(self):
        cfg = self.cfg()
        with self.assertRaises(chaos.ChaosUsageError):
            chaos.approve(cfg, "012", "approved", review=None, user="A", now=NOW)
        with self.assertRaises(chaos.ChaosUsageError):
            chaos.approve(cfg, "012", "frozen", review=self.review(AUDIT_PASS), user="A", now=NOW)
        with self.assertRaises(chaos.ChaosUsageError):
            chaos.approve(cfg, "012", "bogus", review=self.review(SPEC_PASS), user="A", now=NOW)
        self.assert_nothing_written(status="draft")


class PhaseTests(ApproveCase):

    def test_R020_16_wrong_phase_exit_1_naming_it(self):
        cases = [("approved", "approved", SPEC_PASS),
                 ("tests-approved", "draft", AUDIT_PASS),
                 ("frozen", "tests-draft", None),
                 ("done", "tests-approved", IMPL_PASS)]
        for gate, phase, line in cases:
            with self.subTest(gate=gate):
                self.spec("012", phase)
                self.commit_all(f"phase {phase}")
                code, out = self.approve_cli("012", gate, line)
                self.assertEqual(code, 1)
                self.assertIn(phase, out)
                self.assertEqual(self.spec_status("012"), phase)
                self.assertFalse(self.chaos_log.exists())

    def test_R020_16_missing_spec_exit_1(self):
        code, out = self.approve_cli("099", "approved", SPEC_PASS)
        self.assertEqual(code, 1)
        self.assertIn("099", out)
        self.assertFalse(self.chaos_log.exists())

    def test_R020_16_api_wrong_phase_raises(self):
        with self.assertRaises(chaos.ChaosError) as ctx:
            chaos.approve(self.cfg(), "012", "done", review=self.review(IMPL_PASS), user="A", now=NOW)
        self.assertNotIsInstance(ctx.exception, chaos.ChaosUsageError)
        self.assertIn("draft", str(ctx.exception))


class TraceGateTests(ApproveCase):

    def test_R020_17_untraced_requirement_exit_1(self):
        self.traced(covered=("01",))
        code, out = self.approve_cli("012", "tests-approved", AUDIT_PASS)
        self.assertEqual(code, 1)
        self.assertIn(rid("012", "02"), out)
        self.assert_nothing_written(status="tests-draft")

    def test_R020_17_bad_depends_exit_1(self):
        self.traced()
        self.spec("012", "tests-draft", depends=["098"], reqs=("01", "02"))
        self.commit_all("bad depends")
        code, out = self.approve_cli("012", "tests-approved", AUDIT_PASS)
        self.assertEqual(code, 1)
        self.assertIn("098", out)
        self.assert_nothing_written(status="tests-draft")

    def test_R020_17_duplicate_number_exit_1(self):
        self.traced()
        self.spec("012", "draft", slug="twin")
        self.commit_all("twin")
        code, out = self.approve_cli("012", "tests-approved", AUDIT_PASS)
        self.assertEqual(code, 1)
        self.assertIn("twin", out)
        self.assertFalse(self.chaos_log.exists())

    def test_R020_17_traced_spec_is_approved(self):
        self.traced()
        code, _ = self.approve_cli("012", "tests-approved", AUDIT_PASS)
        self.assertEqual(code, 0)
        self.assertEqual(self.spec_status("012"), "tests-approved")
        self.assertEqual(self.kinds(), ["approve"])

    def test_R020_17_other_gates_skip_trace(self):
        self.spec("012", "draft", reqs=("01",))
        self.commit_all("untraced draft")
        code, _ = self.approve_cli("012", "approved", SPEC_PASS)
        self.assertEqual(code, 0)
        self.assertEqual(self.spec_status("012"), "approved")


class PausedTests(ApproveCase):

    def test_R020_18_paused_exit_1_lists_escalations(self):
        self.write_log([self.escalation(1), self.escalation(2),
                        self.record(3, "clear", escalations=[1], note="looked at it")])
        self.commit_all("escalated")
        before = self.chaos_log.read_bytes()
        code, out = self.approve_cli("012", "approved", SPEC_PASS)
        self.assertEqual(code, 1)
        self.assertIn("#2", out)
        self.assertNotIn("#1 ", out)
        self.assertIn("owner", out.lower())
        self.assertEqual(self.chaos_log.read_bytes(), before)
        self.assertEqual(self.spec_status("012"), "draft")
        self.assertFalse((self.spec_dir("012") / "reviews").exists())

    def test_R020_18_api_raises(self):
        self.write_log([self.escalation(1)])
        self.commit_all("escalated")
        with self.assertRaises(chaos.ChaosError) as ctx:
            chaos.approve(self.cfg(), "012", "approved", review=self.review(SPEC_PASS),
                          user="A", now=NOW)
        self.assertNotIsInstance(ctx.exception, chaos.ChaosUsageError)


class CriticalCheckTests(ApproveCase):

    def assert_escalated(self, code, out, cause, detail=None, status="draft", seq=1):
        self.assertEqual(code, 1)
        self.assertIn(HINT, out)
        rec = self.records()[-1]
        self.assertEqual(rec["seq"], seq)
        self.assertEqual(rec["kind"], "escalate")
        self.assertEqual(rec["cause"], cause)
        self.assertEqual(rec["spec"], "012")
        if detail is not None:
            self.assertEqual(rec["detail"], detail)
        self.assertNotIn("reject", self.kinds())
        self.assertNotIn("approve", self.kinds())
        self.assertEqual(self.spec_status("012"), status)
        self.assertFalse((self.spec_dir("012") / "reviews").exists())
        return rec

    def test_R020_19_base_commit_missing(self):
        ghost = "0123456789abcdef0123456789abcdef01234567"
        self.write_log([self.record(1, "clear", escalations=[], note="start", commit=ghost)])
        self.commit_all("log with a vanished base")
        code, out = self.approve_cli("012", "approved", SPEC_PASS)
        self.assert_escalated(code, out, "base", [ghost], seq=2)

    def test_R020_19_base_commit_not_an_ancestor(self):
        self.git("checkout", "-q", "-b", "side")
        self.write("side.txt", "side\n")
        side = self.commit_all("side")
        self.git("checkout", "-q", "main")
        self.write_log([self.record(1, "clear", escalations=[], note="start", commit=side)])
        self.commit_all("log based on the side branch")
        code, out = self.approve_cli("012", "approved", SPEC_PASS)
        self.assert_escalated(code, out, "base", [side], seq=2)

    def test_R020_19_verify(self):
        self.write("tests/test_x.py", "x\n")
        self.write_lock({"tests/test_x.py": "011"})
        self.commit_all("frozen")
        self.write("tests/test_x.py", "changed\n")
        code, out = self.approve_cli("012", "approved", SPEC_PASS)
        self.assert_escalated(code, out, "verify", ["modified tests/test_x.py"])

    def test_R020_19_audit(self):
        # The base commit (it changed agentkit.toml) has a frozen file; the lock entry is then
        # dropped without an unfreeze-log entry. verify passes, audit does not.
        self.write("tests/test_x.py", "x\n")
        self.write_lock({"tests/test_x.py": "011"})
        self.write("agentkit.toml", '[kit]\nprofile = "fixture"\n\n' + CHAOS_ON + "# base\n")
        self.commit_all("base with a lock")
        self.write_lock({})
        code, out = self.approve_cli("012", "approved", SPEC_PASS)
        rec = self.assert_escalated(code, out, "audit")
        self.assertTrue(any("tests/test_x.py" in d for d in rec["detail"]))

    def test_R020_19_protected_uncommitted_and_untracked(self):
        self.write("AGENTS.md", "# changed\n")
        self.write("docs/adr/0009-new.md", "# new\n")
        self.write("notes.md", "not protected\n")
        code, out = self.approve_cli("012", "approved", SPEC_PASS)
        self.assert_escalated(code, out, "protected", ["AGENTS.md", "docs/adr/0009-new.md"])

    def test_R020_19_protected_committed_since_the_base(self):
        self.write("CLAUDE.md", "# changed\n")
        self.commit_all("edit CLAUDE.md after the base")
        code, out = self.approve_cli("012", "approved", SPEC_PASS)
        self.assert_escalated(code, out, "protected", ["CLAUDE.md"])

    def test_R020_19_protected_spec_000_and_roles(self):
        self.write("specs/000-vision/spec.md", "---\nid: \"000\"\nstatus: approved\n---\n")
        self.write("roles/test-auditor.md", "# changed\n")
        code, out = self.approve_cli("012", "approved", SPEC_PASS)
        self.assert_escalated(code, out, "protected",
                              ["roles/test-auditor.md", "specs/000-vision/spec.md"])

    def test_R020_19_custom_escalate_globs(self):
        self.write("agentkit.toml", '[kit]\nprofile = "fixture"\n\n'
                   '[chaos]\nenabled = true\nescalate_globs = ["secret/**"]\n')
        self.commit_all("custom globs")
        self.write("AGENTS.md", "# not protected any more\n")
        self.write("secret/x.txt", "x\n")
        code, out = self.approve_cli("012", "approved", SPEC_PASS)
        self.assert_escalated(code, out, "protected", ["secret/x.txt"])

    def test_R020_19_checks_run_in_order(self):
        self.write("tests/test_x.py", "x\n")
        self.write_lock({"tests/test_x.py": "011"})
        self.commit_all("frozen")
        self.write("tests/test_x.py", "changed\n")
        self.write("AGENTS.md", "# changed\n")
        code, out = self.approve_cli("012", "approved", SPEC_PASS)
        self.assert_escalated(code, out, "verify")

    def test_R020_19_frozen_gate_escalates_before_freezing(self):
        self.spec("012", "tests-approved")
        self.write("tests/test_012_x.py", f"# {rid('012', '01')}\n")
        self.commit_all("tests approved")
        self.write("AGENTS.md", "# changed\n")
        code, out = self.approve_cli("012", "frozen")
        self.assert_escalated(code, out, "protected", ["AGENTS.md"], status="tests-approved")
        self.assertFalse(self.lock_file.exists())

    def test_R020_19_escalation_pauses(self):
        self.write("AGENTS.md", "# changed\n")
        self.approve_cli("012", "approved", SPEC_PASS)
        self.assertEqual([r["seq"] for r in chaos.open_escalations(self.cfg())], [1])


class NeedsOwnerTests(ApproveCase):

    def test_R020_43_needs_owner_escalates(self):
        code, out = self.approve_cli("012", "approved", "**Verdict: Needs Owner**")
        self.assertEqual(code, 1)
        self.assertIn(HINT, out)
        stored = "specs/012-fixture/reviews/1-approved-spec-reviewer.md"
        self.assertTrue((self.root / stored).is_file())
        rec = self.records()[-1]
        self.assertEqual(self.kinds(), ["escalate"])
        self.assertEqual(rec["cause"], "owner")
        self.assertEqual(rec["gate"], "approved")
        self.assertEqual(len(rec["detail"]), 1)
        self.assertIn("spec-reviewer", rec["detail"][0])
        self.assertIn(stored, rec["detail"][0])
        self.assertEqual(self.spec_status("012"), "draft")
        self.assertEqual(len(chaos.open_escalations(self.cfg())), 1)

    def test_R020_43_api_returns_the_escalation(self):
        result = chaos.approve(self.cfg(), "012", "approved", review=self.review(OWNER),
                               user="A", now=NOW)
        self.assertEqual(result["kind"], "escalate")
        self.assertEqual(result["cause"], "owner")


class VerdictOutcomeTests(ApproveCase):

    def test_R020_20_failing_verdict_rejects(self):
        code, _ = self.approve_cli("012", "approved", FAIL)
        self.assertEqual(code, 1)
        self.assertEqual(self.kinds(), ["reject"])
        self.assertEqual(self.spec_status("012"), "draft")

    def test_R020_20_api_returns_the_reject(self):
        result = chaos.approve(self.cfg(), "012", "approved", review=self.review(FAIL),
                               user="A", now=NOW)
        self.assertEqual(result["kind"], "reject")
        self.assertEqual(result, self.records()[-1])

    def test_R020_22_passing_verdict_sets_the_phase(self):
        code, _ = self.approve_cli("012", "approved", SPEC_PASS)
        self.assertEqual(code, 0)
        self.assertEqual(self.spec_status("012"), "approved")
        self.assertEqual(self.kinds(), ["approve"])
        text = (self.spec_dir("012") / "spec.md").read_text(encoding="utf-8")
        self.assertIn("Body stays.", text)

    def test_R020_22_done(self):
        self.spec("012", "frozen")
        self.commit_all("frozen")
        code, _ = self.approve_cli("012", "done", IMPL_PASS)
        self.assertEqual(code, 0)
        self.assertEqual(self.spec_status("012"), "done")
        self.assertEqual(self.records()[-1]["gate"], "done")

    def test_R020_22_frozen_freezes_the_spec(self):
        self.spec("012", "tests-approved")
        self.write("tests/test_012_x.py", f"# {rid('012', '01')}\n")
        self.write("tests/test_011_x.py", f"# {rid('011', '01')}\n")
        self.commit_all("tests approved")
        code, _ = self.approve_cli("012", "frozen")
        self.assertEqual(code, 0)
        self.assertEqual(self.spec_status("012"), "frozen")
        files = self.read_lock()["files"]
        self.assertEqual(sorted(files), ["tests/test_012_x.py"])
        self.assertEqual(files["tests/test_012_x.py"].get("spec"), "012")
        rec = self.records()[-1]
        self.assertEqual((rec["kind"], rec["gate"], rec["files"]),
                         ("approve", "frozen", ["tests/test_012_x.py"]))

    def test_R020_22_frozen_with_no_new_file(self):
        self.spec("012", "tests-approved")
        self.commit_all("tests approved")
        code, _ = self.approve_cli("012", "frozen")
        self.assertEqual(code, 0)
        self.assertEqual(self.spec_status("012"), "frozen")
        self.assertEqual(self.records()[-1]["files"], [])


class RejectionCountTests(ApproveCase):

    def reject(self, seq, spec="012", gate="approved"):
        role = "spec-reviewer" if gate == "approved" else "test-auditor"
        return self.record(seq, "reject", spec=spec, gate=gate,
                           reviews=[self.cite(spec, seq, gate, role, FAIL)])

    def test_R020_21_second_reject_escalates(self):
        self.approve_cli("012", "approved", FAIL)
        code, _ = self.approve_cli("012", "approved", FAIL, name="r2")
        self.assertEqual(code, 1)
        self.assertEqual(self.kinds(), ["reject", "reject", "escalate"])
        rec = self.records()[2]
        self.assertEqual((rec["cause"], rec["spec"], rec["gate"]), ("rejections", "012", "approved"))
        self.assertEqual(rec["detail"], ["#1", "#2"])

    def test_R020_21_max_rejections_is_configurable(self):
        self.write("agentkit.toml", '[kit]\nprofile = "fixture"\n\n'
                   '[chaos]\nenabled = true\nmax_rejections = 3\n')
        self.commit_all("three strikes")
        self.approve_cli("012", "approved", FAIL)
        self.approve_cli("012", "approved", FAIL, name="r2")
        self.assertEqual(self.kinds(), ["reject", "reject"])
        self.approve_cli("012", "approved", FAIL, name="r3")
        self.assertEqual(self.kinds(), ["reject", "reject", "reject", "escalate"])
        self.assertEqual(self.records()[3]["detail"], ["#1", "#2", "#3"])

    def test_R020_21_max_rejections_one(self):
        self.write("agentkit.toml", '[kit]\nprofile = "fixture"\n\n'
                   '[chaos]\nenabled = true\nmax_rejections = 1\n')
        self.commit_all("one strike")
        self.approve_cli("012", "approved", FAIL)
        self.assertEqual(self.kinds(), ["reject", "escalate"])
        self.assertEqual(self.records()[1]["detail"], ["#1"])

    def test_R020_21_other_specs_and_gates_do_not_count(self):
        self.spec("013", "draft")
        self.write_log([self.reject(1, spec="013"), self.reject(2, gate="tests-approved")])
        self.commit_all("other rejects")
        self.approve_cli("012", "approved", FAIL)
        self.assertEqual(self.kinds(), ["reject", "reject", "reject"])

    def test_R020_21_an_approve_resets_the_count(self):
        self.write_log([self.reject(1),
                        self.record(2, "approve", spec="012", gate="approved",
                                    reviews=[self.cite("012", 2, "approved", "spec-reviewer",
                                                       SPEC_PASS)])])
        self.commit_all("approved once")  # spec 012 went back to draft by hand
        self.approve_cli("012", "approved", FAIL)
        self.assertEqual(self.kinds(), ["reject", "approve", "reject"])

    def test_R020_21_a_clear_resets_the_count(self):
        self.write_log([self.reject(1), self.reject(2),
                        self.record(3, "escalate", spec="012", gate="approved", cause="rejections",
                                    detail=["#1", "#2"]),
                        self.record(4, "clear", escalations=[3], note="spec reworded")])
        self.commit_all("cleared")
        self.approve_cli("012", "approved", FAIL)
        self.assertEqual(self.kinds(), ["reject", "reject", "escalate", "clear", "reject"])


class CheckOrderTests(ApproveCase):

    def test_R020_38_usage_before_everything(self):
        self.write("AGENTS.md", "# changed\n")
        code, _ = run_cli("chaos", "approve", "099", "bogus", "--review", self.review(SPEC_PASS))
        self.assertEqual(code, 2)
        self.assertFalse(self.chaos_log.exists())

    def test_R020_38_log_read_before_spec_lookup(self):
        self.chaos_log.write_text("{not json\n", encoding="utf-8")
        self.commit_all("bad log")
        code, out = self.approve_cli("099", "approved", SPEC_PASS)
        self.assertEqual(code, 1)
        self.assertNotIn("does not exist", out)

    def test_R020_38_base_commit_before_spec_lookup(self):
        self.git("checkout", "-q", "--orphan", "other")
        self.git("rm", "-rq", "--cached", ".")
        self.write("README.md", "readme\n")
        self.git("add", "README.md")
        self.git("commit", "-q", "--no-verify", "-m", "readme only")
        code, _ = self.approve_cli("099", "approved", SPEC_PASS)
        self.assertEqual(code, 2)

    def test_R020_38_phase_before_review(self):
        code, _ = self.approve_cli("012", "done", "not a verdict")
        self.assertEqual(code, 1)
        self.assertFalse(self.chaos_log.exists())

    def test_R020_38_review_before_pause(self):
        self.write_log([self.escalation(1)])
        self.commit_all("escalated")
        code, _ = self.approve_cli("012", "approved", "not a verdict")
        self.assertEqual(code, 2)
        self.assertEqual(len(self.records()), 1)

    def test_R020_38_pause_before_trace(self):
        self.traced(covered=("01",))
        self.write_log([self.escalation(1)])
        self.commit_all("escalated")
        code, out = self.approve_cli("012", "tests-approved", AUDIT_PASS)
        self.assertEqual(code, 1)
        self.assertIn("#1", out)
        self.assertNotIn(rid("012", "02"), out)

    def test_R020_38_trace_before_critical_checks(self):
        self.traced(covered=("01",))
        self.write("AGENTS.md", "# changed\n")
        code, out = self.approve_cli("012", "tests-approved", AUDIT_PASS)
        self.assertEqual(code, 1)
        self.assertIn(rid("012", "02"), out)
        self.assertFalse(self.chaos_log.exists())

    def test_R020_38_critical_checks_before_the_verdict(self):
        self.write("AGENTS.md", "# changed\n")
        code, _ = self.approve_cli("012", "approved", FAIL)
        self.assertEqual(code, 1)
        self.assertEqual(self.kinds(), ["escalate"])
        self.assertEqual(self.records()[0]["cause"], "protected")
