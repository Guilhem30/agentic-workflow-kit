"""Spec 020: the chaos log (R020-07 to R020-11, R020-37), reviews and verdicts (R020-12 to
R020-14)."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

from agentkit import chaos
from tests.chaos_fixtures import (AUDIT_PASS, FAIL, IMPL_PASS, NOW, NOW_TEXT, OWNER, SPEC_PASS,
                                  UNFREEZE_FAIL, UNFREEZE_PASS, ChaosCase, dumps)
from tests.support import rid, run_cli, sha256_lf

PATIENT = "[chaos]\nenabled = true\nmax_rejections = 5\n"


class LogFormatTests(ChaosCase):
    REST = PATIENT

    def test_R020_07_json_lines_appended_never_rewritten(self):
        chaos.approve(self.cfg(), "012", "approved", review=self.review(FAIL), user="Alice", now=NOW)
        first = self.chaos_log.read_bytes()
        chaos.approve(self.cfg(), "012", "approved", review=self.review(SPEC_PASS, name="r2"),
                      user="Alice", now=NOW)
        raw = self.chaos_log.read_bytes()
        self.assertTrue(raw.startswith(first))
        self.assertTrue(raw.endswith(b"\n"))
        self.assertNotIn(b"\r", raw)
        lines = raw.decode("utf-8").split("\n")
        self.assertEqual(lines[-1], "")
        self.assertEqual(len(lines), 3)
        for line in lines[:-1]:
            self.assertEqual(line, dumps(json.loads(line)))

    def test_R020_07_utf8_not_escaped(self):
        chaos.approve(self.cfg(), "012", "approved", review=self.review(FAIL), user="Zoë", now=NOW)
        raw = self.chaos_log.read_bytes()
        self.assertIn("Zoë".encode("utf-8"), raw)
        self.assertNotIn(b"\\u00eb", raw)

    def test_R020_08_common_fields(self):
        chaos.approve(self.cfg(), "012", "approved", review=self.review(FAIL), user="Alice", now=NOW)
        rec = self.records()[0]
        self.assertEqual(rec["seq"], 1)
        self.assertEqual(rec["time"], NOW_TEXT)
        self.assertEqual(rec["kind"], "reject")
        self.assertEqual(rec["commit"], self.head)
        self.assertEqual(len(rec["commit"]), 40)
        self.assertEqual(rec["user"], "Alice")
        self.assertEqual(rec["actor"], "human")

    def test_R020_08_agent_actor_and_git_user(self):
        self.agent()
        chaos.approve(self.cfg(), "012", "approved", review=self.review(FAIL), now=NOW)
        rec = self.records()[0]
        self.assertEqual(rec["actor"], "agent")
        self.assertEqual(rec["user"], "Fixture Owner")

    def test_R020_08_unknown_user_when_git_has_none(self):
        empty = self.write(self.tmp / "empty.gitconfig", "")
        os.environ["GIT_CONFIG_GLOBAL"] = str(empty)
        os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
        self.git("config", "--unset", "user.name")
        chaos.approve(self.cfg(), "012", "approved", review=self.review(FAIL), now=NOW)
        self.assertEqual(self.records()[0]["user"], "unknown")

    def test_R020_08_time_is_utc(self):
        local = datetime(2026, 10, 3, 14, 34, 56, tzinfo=timezone(timedelta(hours=2)))
        chaos.approve(self.cfg(), "012", "approved", review=self.review(FAIL), user="A", now=local)
        self.assertEqual(self.records()[0]["time"], NOW_TEXT)

    def test_R020_08_default_time_format(self):
        chaos.approve(self.cfg(), "012", "approved", review=self.review(FAIL), user="A")
        self.assertRegex(self.records()[0]["time"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

    def test_R020_08_seq_is_the_line_number(self):
        self.write_log([self.record(1, "reject", spec="012", gate="approved",
                                    reviews=[self.cite("012", 1, "approved", "spec-reviewer", FAIL)]),
                        self.record(2, "reject", spec="012", gate="approved",
                                    reviews=[self.cite("012", 2, "approved", "spec-reviewer", FAIL)])])
        self.commit_all("two rejects")
        chaos.approve(self.cfg(), "012", "approved", review=self.review(FAIL), user="A", now=NOW)
        self.assertEqual([r["seq"] for r in self.records()], [1, 2, 3])
        self.assertEqual(self.records()[2]["commit"], self.git("rev-parse", "HEAD"))

    def test_R020_09_approve_record(self):
        result = chaos.approve(self.cfg(), "012", "approved", review=self.review(SPEC_PASS),
                               user="Alice", now=NOW)
        rec = self.records()[0]
        self.assertEqual(result, rec)
        self.assertEqual(rec["kind"], "approve")
        self.assertEqual(rec["spec"], "012")
        self.assertEqual(rec["gate"], "approved")
        stored = "specs/012-fixture/reviews/1-approved-spec-reviewer.md"
        self.assertEqual(rec["reviews"], [{
            "role": "spec-reviewer", "verdict": SPEC_PASS, "review": stored,
            "review_sha256": sha256_lf((self.root / stored).read_bytes())}])

    def test_R020_09_reject_record_holds_the_normalised_verdict(self):
        chaos.approve(self.cfg(), "012", "approved",
                      review=self.review("  **`Verdict:   Needs  CHANGES`**  "), user="A", now=NOW)
        rec = self.records()[0]
        self.assertEqual(rec["kind"], "reject")
        self.assertEqual(rec["spec"], "012")
        self.assertEqual(rec["gate"], "approved")
        self.assertEqual(rec["reviews"][0]["verdict"], FAIL)
        self.assertEqual(rec["reviews"][0]["role"], "spec-reviewer")


class FrozenRecordTests(ChaosCase):
    SPECS = {"012": "tests-approved", "013": "tests-approved"}

    def freeze_fixture(self, records):
        self.write_log(records)
        self.write("tests/test_012_b.py", f"# {rid('012', '01')}\n")
        self.write("tests/test_012_a.py", f"# {rid('012', '02')}\n")
        self.commit_all("tests")

    def test_R020_09_frozen_record(self):
        self.freeze_fixture([self.record(1, "approve", spec="012", gate="tests-approved",
                                         reviews=[self.cite("012", 1, "tests-approved",
                                                            "test-auditor", AUDIT_PASS)])])
        result = chaos.approve(self.cfg(), "012", "frozen", user="A", now=NOW)
        rec = self.records()[-1]
        self.assertEqual(result, rec)
        self.assertEqual(rec["kind"], "approve")
        self.assertEqual(rec["gate"], "frozen")
        self.assertEqual(rec["reviews"], [])
        self.assertEqual(rec["files"], ["tests/test_012_a.py", "tests/test_012_b.py"])
        self.assertEqual(rec["based_on"], 1)

    def test_R020_09_based_on_the_newest_approve_of_tests_approved(self):
        self.freeze_fixture([
            self.record(1, "approve", spec="012", gate="tests-approved",
                        reviews=[self.cite("012", 1, "tests-approved", "test-auditor", AUDIT_PASS)]),
            self.record(2, "approve", spec="013", gate="tests-approved",
                        reviews=[self.cite("013", 2, "tests-approved", "test-auditor", AUDIT_PASS)]),
            self.record(3, "approve", spec="012", gate="tests-approved",
                        reviews=[self.cite("012", 3, "tests-approved", "test-auditor", AUDIT_PASS)]),
        ])
        chaos.approve(self.cfg(), "012", "frozen", user="A", now=NOW)
        self.assertEqual(self.records()[-1]["based_on"], 3)

    def test_R020_09_based_on_null_without_an_approve(self):
        self.freeze_fixture([])
        chaos.approve(self.cfg(), "012", "frozen", user="A", now=NOW)
        rec = self.records()[-1]
        self.assertEqual(rec["seq"], 1)
        self.assertIsNone(rec["based_on"])


class EscalateRecordTests(ChaosCase):

    def test_R020_10_escalate_record(self):
        chaos.approve(self.cfg(), "012", "approved", review=self.review(FAIL), user="A", now=NOW)
        result = chaos.approve(self.cfg(), "012", "approved", review=self.review(FAIL, name="r2"),
                               user="A", now=NOW)
        rec = self.records()[-1]
        self.assertEqual(result, rec)
        self.assertEqual(rec["kind"], "escalate")
        self.assertEqual(rec["seq"], 3)
        self.assertEqual(rec["spec"], "012")
        self.assertEqual(rec["gate"], "approved")
        self.assertEqual(rec["cause"], "rejections")
        self.assertIsInstance(rec["detail"], list)
        self.assertTrue(all(isinstance(d, str) for d in rec["detail"]))
        for key in ("time", "commit", "user", "actor"):
            self.assertIn(key, rec)


class OpenEscalationTests(ChaosCase):

    def escalation(self, seq):
        return self.record(seq, "escalate", spec="012", gate="approved", cause="owner",
                           detail=[f"spec-reviewer specs/012-fixture/reviews/{seq}.md"])

    def test_R020_11_open_until_cleared(self):
        self.write_log([self.escalation(1), self.escalation(2),
                        self.record(3, "clear", escalations=[1], note="looked at it")])
        opened = chaos.open_escalations(self.cfg())
        self.assertEqual([r["seq"] for r in opened], [2])
        self.assertEqual(opened[0]["kind"], "escalate")

    def test_R020_11_all_cleared(self):
        self.write_log([self.escalation(1), self.escalation(2),
                        self.record(3, "clear", escalations=[1, 2], note="looked at it")])
        self.assertEqual(chaos.open_escalations(self.cfg()), [])

    def test_R020_11_no_log_no_escalation(self):
        self.assertEqual(chaos.open_escalations(self.cfg()), [])

    def test_R020_11_paused_refuses_approvals(self):
        self.write_log([self.escalation(1)])
        self.commit_all("escalated")
        code, out = run_cli("chaos", "approve", "012", "approved", "--review", self.review(SPEC_PASS))
        self.assertEqual(code, 1)
        self.assertIn("#1", out)
        self.assertEqual(self.spec_status("012"), "draft")
        self.assertEqual(len(self.records()), 1)


class ReadLogTests(ChaosCase):

    def valid(self, seq=1):
        return self.record(seq, "clear", escalations=[], note="looked at it")

    def assert_bad(self, lines: list[str], line_no: int):
        self.write(self.chaos_log, "".join(line + "\n" for line in lines))
        with self.assertRaises(chaos.ChaosError) as ctx:
            chaos.read_log(self.cfg())
        self.assertRegex(str(ctx.exception), rf"\b{line_no}\b")

    def test_R020_37_missing_log_reads_as_empty(self):
        self.assertEqual(chaos.read_log(self.cfg()), [])

    def test_R020_37_valid_log_reads_back(self):
        recs = [self.valid(1), self.record(2, "escalate", spec="012", gate="done", cause="verify",
                                           detail=["modified tests/x.py"])]
        self.write_log(recs)
        self.assertEqual(chaos.read_log(self.cfg()), recs)

    def test_R020_37_not_json(self):
        self.assert_bad([dumps(self.valid(1)), "{not json"], 2)

    def test_R020_37_not_an_object(self):
        self.assert_bad(["[1, 2]"], 1)

    def test_R020_37_missing_common_field(self):
        for key in ("seq", "time", "kind", "commit", "user", "actor"):
            with self.subTest(key=key):
                rec = self.valid(1)
                del rec[key]
                self.assert_bad([dumps(rec)], 1)

    def test_R020_37_unknown_kind(self):
        rec = self.valid(1)
        rec["kind"] = "bogus"
        self.assert_bad([dumps(rec)], 1)

    def test_R020_37_missing_kind_fields(self):
        cases = [
            ("approve", {"spec": "012", "gate": "approved"}),            # no reviews
            ("reject", {"spec": "012", "reviews": []}),                  # no gate
            ("escalate", {"spec": "012", "gate": "approved", "detail": []}),  # no cause
            ("unfreeze", {"spec": "012", "gate": "unfreeze", "files": [], "reviews": []}),  # no reason
            ("clear", {"escalations": []}),                              # no note
        ]
        for kind, fields in cases:
            with self.subTest(kind=kind):
                self.assert_bad([dumps(self.valid(1)), dumps(self.record(2, kind, **fields))], 2)

    def test_R020_37_frozen_approve_needs_files_and_based_on(self):
        rec = self.record(1, "approve", spec="012", gate="frozen", reviews=[], files=[])
        self.assert_bad([dumps(rec)], 1)

    def test_R020_37_seq_must_equal_the_line_number(self):
        self.assert_bad([dumps(self.valid(1)), dumps(self.valid(5))], 2)

    def test_R020_37_malformed_log_stops_approve(self):
        self.write(self.chaos_log, "{not json\n")
        self.commit_all("bad log")
        before = self.chaos_log.read_bytes()
        code, out = run_cli("chaos", "approve", "012", "approved", "--review", self.review(SPEC_PASS))
        self.assertEqual(code, 1)
        self.assertRegex(out, r"\b1\b")
        self.assertIn("chaos-log.jsonl", out)
        self.assertEqual(self.chaos_log.read_bytes(), before)
        self.assertEqual(self.spec_status("012"), "draft")


class ReviewsTests(ChaosCase):

    def test_R020_12_review_table(self):
        self.assertEqual(chaos.REVIEWS, {
            "approved": [("spec-reviewer", SPEC_PASS, FAIL)],
            "tests-approved": [("test-auditor", AUDIT_PASS, FAIL)],
            "done": [("impl-reviewer", IMPL_PASS, FAIL)],
            "unfreeze": [("test-auditor", UNFREEZE_PASS, UNFREEZE_FAIL),
                         ("impl-reviewer", UNFREEZE_PASS, UNFREEZE_FAIL)],
        })
        self.assertEqual(chaos.NEEDS_OWNER, OWNER)
        self.assertEqual(chaos.GATES, ("approved", "tests-approved", "frozen", "done"))
        self.assertEqual(chaos.CAUSES, ("rejections", "verify", "audit", "protected", "base", "owner"))


class VerdictTests(ChaosCase):

    def test_R020_13_pass_fail_owner_per_role(self):
        cases = [("approved", "spec-reviewer", SPEC_PASS),
                 ("tests-approved", "test-auditor", AUDIT_PASS),
                 ("done", "impl-reviewer", IMPL_PASS),
                 ("unfreeze", "test-auditor", UNFREEZE_PASS),
                 ("unfreeze", "impl-reviewer", UNFREEZE_PASS)]
        for gate, role, passing in cases:
            failing = UNFREEZE_FAIL if gate == "unfreeze" else FAIL
            with self.subTest(gate=gate, role=role):
                self.assertEqual(chaos.parse_verdict(f"# R\n\n{passing}\n", gate, role), "pass")
                self.assertEqual(chaos.parse_verdict(f"# R\n\n{failing}\n", gate, role), "fail")
                self.assertEqual(chaos.parse_verdict(f"# R\n\n{OWNER}\n", gate, role), "owner")

    def test_R020_13_normalisation(self):
        text = "# Review\n\n  **`Verdict:   Ready  FOR owner\tapproval`**  \n\n \n"
        self.assertEqual(chaos.parse_verdict(text, "approved", "spec-reviewer"), "pass")
        self.assertEqual(chaos.parse_verdict("verdict: ready for owner approval\r\n\r\n",
                                             "approved", "spec-reviewer"), "pass")

    def test_R020_13_only_the_last_non_empty_line_counts(self):
        text = f"{FAIL}\nmore findings\n{SPEC_PASS}\n"
        self.assertEqual(chaos.parse_verdict(text, "approved", "spec-reviewer"), "pass")
        text = f"{SPEC_PASS}\nverdict follows later\n"
        with self.assertRaises(chaos.ChaosUsageError) as ctx:
            chaos.parse_verdict(text, "approved", "spec-reviewer")
        self.assertIn("verdict follows later", str(ctx.exception))

    def test_R020_13_unknown_line_is_quoted(self):
        with self.assertRaises(chaos.ChaosUsageError) as ctx:
            chaos.parse_verdict("# R\n\nlooks fine to me\n", "approved", "spec-reviewer")
        self.assertIn("looks fine to me", str(ctx.exception))

    def test_R020_13_another_gates_verdict_is_refused(self):
        with self.assertRaises(chaos.ChaosUsageError):
            chaos.parse_verdict(f"{IMPL_PASS}\n", "approved", "spec-reviewer")
        with self.assertRaises(chaos.ChaosUsageError):
            chaos.parse_verdict(f"{AUDIT_PASS}\n", "unfreeze", "test-auditor")

    def test_R020_13_empty_text(self):
        for text in ("", "\n\n  \n"):
            with self.subTest(text=text):
                with self.assertRaises(chaos.ChaosUsageError):
                    chaos.parse_verdict(text, "approved", "spec-reviewer")

    def assert_cli_refuses(self, review_path: str, needle: str | None = None):
        code, out = run_cli("chaos", "approve", "012", "approved", "--review", review_path)
        self.assertEqual(code, 2)
        if needle:
            self.assertIn(needle, out)
        self.assertFalse(self.chaos_log.exists())
        self.assertFalse((self.spec_dir("012") / "reviews").exists())
        self.assertEqual(self.spec_status("012"), "draft")

    def test_R020_13_cli_unknown_line_exit_2(self):
        self.assert_cli_refuses(self.review("looks fine to me"), "looks fine to me")

    def test_R020_13_cli_missing_file_exit_2(self):
        self.assert_cli_refuses(str(self.tmp / "nowhere.md"))

    def test_R020_13_cli_empty_file_exit_2(self):
        path = self.tmp / "empty.md"
        path.write_bytes(b"")
        self.assert_cli_refuses(str(path))

    def test_R020_13_cli_not_utf8_exit_2(self):
        path = self.tmp / "latin1.md"
        path.write_bytes("# R\n\nverdict: ready for owner approval \xe9\n".encode("latin-1"))
        self.assert_cli_refuses(str(path))


class StoredReviewTests(ChaosCase):
    REST = PATIENT

    def test_R020_14_copy_is_byte_for_byte(self):
        data = b"# Review\r\n\r\nFindings: none. \xc3\xa9\r\n\r\nverdict: ready for owner approval\r\n"
        path = self.tmp / "crlf.md"
        path.write_bytes(data)
        chaos.approve(self.cfg(), "012", "approved", review=str(path), user="A", now=NOW)
        stored = self.spec_dir("012") / "reviews" / "1-approved-spec-reviewer.md"
        self.assertEqual(stored.read_bytes(), data)
        self.assertEqual(self.records()[0]["reviews"][0]["review_sha256"], sha256_lf(data))

    def test_R020_14_reject_stores_its_review(self):
        review = self.review(FAIL, body="Findings: R012-01 is vague.\n")
        chaos.approve(self.cfg(), "012", "approved", review=review, user="A", now=NOW)
        stored = self.spec_dir("012") / "reviews" / "1-approved-spec-reviewer.md"
        self.assertEqual(stored.read_bytes(), open(review, "rb").read())
        self.assertEqual(self.records()[0]["reviews"][0]["review"],
                         "specs/012-fixture/reviews/1-approved-spec-reviewer.md")

    def test_R020_14_replaces_an_existing_file(self):
        stored = self.write("specs/012-fixture/reviews/1-approved-spec-reviewer.md", "stale\n")
        self.commit_all("stale review")
        review = self.review(SPEC_PASS)
        chaos.approve(self.cfg(), "012", "approved", review=review, user="A", now=NOW)
        self.assertEqual(stored.read_bytes(), open(review, "rb").read())
