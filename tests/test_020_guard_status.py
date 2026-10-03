"""Spec 020: guard rules (R020-29, R020-30, R020-42), agent gate moves (R020-31) and status
(R020-32 to R020-34)."""
from __future__ import annotations

from agentkit import chaos, guard, specs
from agentkit.guard import DENY, ShellAction, WriteAction
from tests.chaos_fixtures import CHAOS_ON, ChaosCase
from tests.support import rid, run_cli

MALFORMED = '[chaos]\nenabled = true\nmax_rejections = 0\nlog = "meta/chaos.jsonl"\n'


class GuardCase(ChaosCase):

    def decide(self, *actions):
        return guard.evaluate(self.cfg(), list(actions), cwd=str(self.root))

    def assert_denied(self, *actions, needle: str):
        decision = self.decide(*actions)
        self.assertEqual(decision.verdict, DENY)
        self.assertIn(needle, decision.reason)


class ProtectedFilesTests(GuardCase):

    def test_R020_29_write_to_the_log_denied(self):
        self.assert_denied(WriteAction(["chaos-log.jsonl"]), needle="chaos-log.jsonl")

    def test_R020_29_write_to_a_review_denied(self):
        path = "specs/012-fixture/reviews/1-approved-spec-reviewer.md"
        self.assert_denied(WriteAction([path]), needle=path)
        self.assert_denied(WriteAction(["specs/012-fixture/reviews/new.md"]),
                           needle="specs/012-fixture/reviews/new.md")

    def test_R020_29_shell_writes_denied(self):
        for command in ("echo x >> chaos-log.jsonl",
                        "rm specs/012-fixture/reviews/1-approved-spec-reviewer.md",
                        "mv other.jsonl chaos-log.jsonl"):
            with self.subTest(command=command):
                self.assertEqual(self.decide(ShellAction(command)).verdict, DENY)

    def test_R020_29_configured_log_path(self):
        self.write("agentkit.toml", '[kit]\nprofile = "fixture"\n\n'
                   '[chaos]\nenabled = true\nlog = "meta/chaos.jsonl"\n')
        self.assert_denied(WriteAction(["meta/chaos.jsonl"]), needle="meta/chaos.jsonl")

    def test_R020_29_reviews_follow_the_specs_path(self):
        self.write("agentkit.toml", '[kit]\nprofile = "fixture"\n\n[paths]\nspecs = "doc/specs"\n\n'
                   + CHAOS_ON)
        self.assert_denied(WriteAction(["doc/specs/012-x/reviews/r.md"]),
                           needle="doc/specs/012-x/reviews/r.md")

    def test_R020_29_with_chaos_off_and_no_table(self):
        for table in ("[chaos]\nenabled = false\n", ""):
            with self.subTest(table=table):
                self.write("agentkit.toml", f'[kit]\nprofile = "fixture"\n\n{table}')
                self.assert_denied(WriteAction(["chaos-log.jsonl"]), needle="chaos-log.jsonl")
                self.assert_denied(WriteAction(["specs/012-fixture/reviews/r.md"]),
                                   needle="specs/012-fixture/reviews/r.md")

    def test_R020_29_allow_globs_do_not_override(self):
        self.write("agentkit.toml", '[kit]\nprofile = "fixture"\n\n'
                   '[guard]\nallow_globs = ["chaos-log.jsonl", "specs/**"]\n\n' + CHAOS_ON)
        self.assert_denied(WriteAction(["chaos-log.jsonl"]), needle="chaos-log.jsonl")
        self.assert_denied(WriteAction(["specs/012-fixture/reviews/r.md"]),
                           needle="specs/012-fixture/reviews/r.md")


class ChaosClearShellTests(GuardCase):

    def test_R020_30_chaos_clear_denied(self):
        for command in ("python -m agentkit chaos clear 3 --note 'looked at it'",
                        "python3 .agentkit/bin/agentkit chaos clear --all --note ok-ok",
                        "agentkit  chaos   clear 1 --note fine1"):
            with self.subTest(command=command):
                decision = self.decide(ShellAction(command))
                self.assertEqual(decision.verdict, DENY)
                self.assertIn("owner", decision.reason.lower())

    def test_R020_30_other_chaos_commands_not_denied_by_this_rule(self):
        for command in ("python -m agentkit chaos log --open", "python -m agentkit chaos audit"):
            with self.subTest(command=command):
                self.assertNotEqual(self.decide(ShellAction(command)).verdict, DENY)


class MalformedTableGuardTests(GuardCase):
    REST = MALFORMED

    def test_R020_42_guard_protects_the_default_paths(self):
        self.assert_denied(WriteAction(["chaos-log.jsonl"]), needle="chaos-log.jsonl")
        self.assert_denied(WriteAction(["specs/012-fixture/reviews/r.md"]),
                           needle="specs/012-fixture/reviews/r.md")

    def test_R020_42_log_and_audit_use_the_default_path(self):
        self.write_log([self.record(1, "clear", escalations=[], note="looked at it")])
        code, out = run_cli("chaos", "log")
        self.assertEqual(code, 0)
        self.assertIn("looked at it", out)
        self.assertEqual(chaos.audit(self.cfg()), [])
        self.write_log([self.record(5, "clear", escalations=[], note="bad seq")])
        code, _ = run_cli("chaos", "audit")
        self.assertEqual(code, 1)


class AgentGateTests(ChaosCase):
    REST = '[chaos]\nenabled = true\nspecs = ["012"]\n'
    SPECS = {"012": "draft", "013": "draft"}

    def test_R020_31_spec_status_gates_refused_for_agents(self):
        self.agent()
        for phase, gate in (("draft", "approved"), ("tests-draft", "tests-approved"),
                            ("frozen", "done")):
            with self.subTest(gate=gate):
                self.spec("012", phase)
                code, out = run_cli("spec-status", "012", gate)
                self.assertEqual(code, 1)
                self.assertIn(f"chaos approve 012 {gate}", out)
                self.assertEqual(self.spec_status("012"), phase)

    def test_R020_31_lock_freeze_refused_for_agents(self):
        self.agent()
        self.spec("012", "tests-approved")
        self.write("tests/test_012_x.py", f"# {rid('012', '01')}\n")
        code, out = run_cli("lock", "freeze", "--spec", "012")
        self.assertEqual(code, 1)
        self.assertIn("chaos approve 012 frozen", out)
        self.assertFalse(self.lock_file.exists())
        self.assertEqual(self.spec_status("012"), "tests-approved")

    def test_R020_31_other_moves_unchanged(self):
        self.agent()
        self.spec("012", "approved")
        code, _ = run_cli("spec-status", "012", "tests-draft")
        self.assertEqual(code, 0)
        self.assertEqual(self.spec_status("012"), "tests-draft")

    def test_R020_31_specs_outside_chaos_unchanged(self):
        self.agent()
        code, _ = run_cli("spec-status", "013", "approved")
        self.assertEqual(code, 0)
        self.assertEqual(self.spec_status("013"), "approved")

    def test_R020_31_owner_outside_an_agent_environment(self):
        code, _ = run_cli("spec-status", "012", "approved")
        self.assertEqual(code, 0)
        self.assertEqual(self.spec_status("012"), "approved")

    def test_R020_31_apis_do_not_check(self):
        self.agent()
        specs.set_status(specs.find_spec(self.cfg(), "012"), "approved")
        self.assertEqual(self.spec_status("012"), "approved")


class MalformedTableGateTests(ChaosCase):
    REST = MALFORMED

    def test_R020_31_malformed_table_exit_2_for_agents(self):
        self.agent()
        code, _ = run_cli("spec-status", "012", "approved")
        self.assertEqual(code, 2)
        self.assertEqual(self.spec_status("012"), "draft")

    def test_R020_31_malformed_table_ignored_outside_agents(self):
        code, _ = run_cli("spec-status", "012", "approved")
        self.assertEqual(code, 0)
        self.assertEqual(self.spec_status("012"), "approved")


class StatusCase(ChaosCase):

    def lines(self):
        from agentkit import status
        return status.status_lines(self.cfg())

    def escalate(self, seq=1):
        return self.record(seq, "escalate", spec="012", gate="approved", cause="owner",
                           detail=["x"])


class StatusSuffixTests(StatusCase):

    def test_R020_32_chaos_on(self):
        self.assertEqual(chaos.status_suffix(self.cfg()), " | chaos: on")
        line = self.lines()[0]
        self.assertTrue(line.startswith("agentkit: profile fixture | frozen files: 0 | lock: OK"))
        self.assertTrue(line.endswith(" | chaos: on"))

    def test_R020_32_paused(self):
        self.write_log([self.escalate(1), self.escalate(2)])
        self.assertEqual(chaos.status_suffix(self.cfg()), " | chaos: PAUSED (2 open escalation(s))")
        self.assertTrue(self.lines()[0].endswith(" | chaos: PAUSED (2 open escalation(s))"))

    def test_R020_32_broken_table(self):
        self.write("agentkit.toml", '[kit]\nprofile = "fixture"\n\n' + MALFORMED)
        suffix = chaos.status_suffix(self.cfg())
        self.assertTrue(suffix.startswith(" | chaos: BROKEN ("))
        self.assertIn("chaos.max_rejections", suffix)
        line = self.lines()[0]
        self.assertIn(" | chaos: BROKEN (", line)
        self.assertLessEqual(len(line), 200)

    def test_R020_32_broken_log(self):
        self.chaos_log.write_text("{broken\n" + "x" * 400 + "\n", encoding="utf-8")
        line = self.lines()[0]
        self.assertIn(" | chaos: BROKEN (", line)
        self.assertLessEqual(len(line), 200)

    def test_R020_32_off_or_absent_unchanged(self):
        for table in ("[chaos]\nenabled = false\n", ""):
            with self.subTest(table=table):
                self.write("agentkit.toml", f'[kit]\nprofile = "fixture"\n\n{table}')
                self.assertEqual(chaos.status_suffix(self.cfg()), "")
                self.assertNotIn("chaos", self.lines()[0])


class NextActionTests(StatusCase):
    REST = '[chaos]\nenabled = true\nspecs = ["012"]\n'
    SPECS = {"012": "draft", "013": "draft"}

    def spec_line(self, num):
        return next(line for line in self.lines() if line.startswith(f"spec {num} "))

    def test_R020_33_actions_for_chaos_specs(self):
        cases = {
            "draft": "run /spec 012, then chaos approve 012 approved",
            "approved": "run /write-tests 012",
            "tests-draft": "chaos approve 012 tests-approved",
            "tests-approved": "chaos approve 012 frozen",
            "frozen": "run /implement 012, then chaos approve 012 done",
        }
        for phase, action in cases.items():
            with self.subTest(phase=phase):
                self.spec("012", phase)
                self.assertEqual(self.spec_line("012"), f"spec 012 fixture [{phase}] -> {action}")

    def test_R020_33_other_specs_keep_the_owner_actions(self):
        self.assertEqual(self.spec_line("013"),
                         "spec 013 fixture [draft] -> run /spec 013, then HUMAN approves")

    def test_R020_33_blocked_still_applies(self):
        self.spec("011", "approved")
        self.spec("012", "frozen", depends=["011"])
        self.assertEqual(self.spec_line("012"), "spec 012 fixture [frozen] -> blocked by 011")


class PausedStatusTests(StatusCase):

    def test_R020_34_last_line_while_paused(self):
        self.write_log([self.escalate(1)])
        self.assertEqual(self.lines()[-1],
                         "next: HUMAN reviews 1 escalation(s): agentkit chaos log --open")

    def test_R020_34_lock_violation_comes_first(self):
        self.write_log([self.escalate(1)])
        self.write("tests/test_x.py", "x\n")
        self.write_lock({"tests/test_x.py": "011"})
        self.write("tests/test_x.py", "changed\n")
        last = self.lines()[-1]
        self.assertNotIn("escalation", last)
        self.assertIn("restore", last.lower())

    def test_R020_34_not_paused_keeps_the_spec_action(self):
        self.write_log([self.escalate(1),
                        self.record(2, "clear", escalations=[1], note="looked at it")])
        self.assertEqual(self.lines()[-1], "next: run /spec 012, then chaos approve 012 approved")
