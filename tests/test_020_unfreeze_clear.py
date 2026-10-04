"""Spec 020: agent unfreeze (R020-23 to R020-25, R020-39), owner commands `clear`, `log` and
`audit` (R020-26 to R020-28, R020-40, R020-41), and their records (R020-10)."""
from __future__ import annotations

import io
from unittest import mock

from agentkit import chaos
from agentkit.lock import OwnerCheckError
from tests.chaos_fixtures import (FAIL, NOW, NOW_TEXT, OWNER, SPEC_PASS, UNFREEZE_FAIL,
                                  UNFREEZE_PASS, ChaosCase, dumps)
from tests.support import LOG_HEADER, run_cli, sha256_lf

AUDITOR = "specs/012-fixture/reviews/{seq}-unfreeze-test-auditor.md"
IMPL = "specs/012-fixture/reviews/{seq}-unfreeze-impl-reviewer.md"


class UnfreezeCase(ChaosCase):
    """Spec 012 is frozen with two test files (one in a sub-directory); 011's file and a shared
    helper without a spec are frozen too."""

    SPECS = {"012": "frozen", "011": "frozen"}

    def setUp(self) -> None:
        super().setUp()
        self.write("tests/test_012_b.py", "b\n")
        self.write("tests/sub/test_012_a.py", "a\n")
        self.write("tests/test_011_x.py", "x\n")
        self.write("tests/helpers.py", "h\n")
        self.write_lock({"tests/test_012_b.py": "012", "tests/sub/test_012_a.py": "012",
                         "tests/test_011_x.py": "011", "tests/helpers.py": None})
        self.head = self.commit_all("frozen")
        self.lock_before = self.lock_file.read_bytes()

    def unfreeze_cli(self, *paths, reason="wrong fixture", auditor=UNFREEZE_PASS,
                     impl=UNFREEZE_PASS):
        return run_cli("chaos", "unfreeze", *paths, "--reason", reason,
                       "--auditor-review", self.review(auditor, name="auditor"),
                       "--impl-review", self.review(impl, name="impl"))

    def unfreeze_api(self, paths, reason="wrong fixture", auditor=UNFREEZE_PASS,
                     impl=UNFREEZE_PASS, user="Alice"):
        return chaos.unfreeze(self.cfg(), paths, reason, self.review(auditor, name="auditor"),
                              self.review(impl, name="impl"), user=user, now=NOW)

    def assert_unchanged(self, status="frozen"):
        self.assertEqual(self.lock_file.read_bytes(), self.lock_before)
        self.assertEqual(self.spec_status("012"), status)
        self.assertFalse(self.log_file.exists())


class UnfreezeUsageTests(UnfreezeCase):

    def test_R020_23_reason_of_five_characters(self):
        for reason in ("", "abcd", "  ab  "):
            with self.subTest(reason=reason):
                code, _ = self.unfreeze_cli("tests/test_012_b.py", reason=reason)
                self.assertEqual(code, 2)
        with self.assertRaises(chaos.ChaosUsageError):
            self.unfreeze_api(["tests/test_012_b.py"], reason="  abcd ")
        self.assert_unchanged()
        self.assertFalse(self.chaos_log.exists())

    def test_R020_23_reason_of_exactly_five_characters(self):
        code, _ = self.unfreeze_cli("tests/test_012_b.py", reason="  abcde ")
        self.assertEqual(code, 0)
        self.assertEqual(self.records()[-1]["reason"], "abcde")

    def test_R020_23_both_reviews_required(self):
        auditor = self.review(UNFREEZE_PASS, name="auditor")
        impl = self.review(UNFREEZE_PASS, name="impl")
        for extra in (["--auditor-review", auditor], ["--impl-review", impl], []):
            with self.subTest(extra=extra):
                code, _ = run_cli("chaos", "unfreeze", "tests/test_012_b.py",
                                  "--reason", "wrong fixture", *extra)
                self.assertEqual(code, 2)
        self.assert_unchanged()

    def test_R020_23_path_not_frozen(self):
        self.write("tests/test_012_new.py", "new\n")
        self.commit_all("new")
        code, out = self.unfreeze_cli("tests/test_012_b.py", "tests/test_012_new.py")
        self.assertEqual(code, 1)
        self.assertIn("tests/test_012_new.py", out)
        self.assertIn("owner", out.lower())
        self.assert_unchanged()
        self.assertFalse(self.chaos_log.exists())

    def test_R020_23_path_without_a_spec(self):
        code, out = self.unfreeze_cli("tests/test_012_b.py", "tests/helpers.py")
        self.assertEqual(code, 1)
        self.assertIn("tests/helpers.py", out)
        self.assertIn("owner", out.lower())
        self.assert_unchanged()

    def test_R020_23_paths_of_two_specs(self):
        code, out = self.unfreeze_cli("tests/test_012_b.py", "tests/test_011_x.py")
        self.assertEqual(code, 1)
        self.assertTrue("tests/test_011_x.py" in out or "tests/test_012_b.py" in out)
        self.assertIn("owner", out.lower())
        self.assert_unchanged()
        self.assertFalse(self.chaos_log.exists())

    def test_R020_23_directory_stands_for_its_frozen_files(self):
        code, _ = self.unfreeze_cli("tests/sub")
        self.assertEqual(code, 0)
        files = self.read_lock()["files"]
        self.assertNotIn("tests/sub/test_012_a.py", files)
        self.assertIn("tests/test_012_b.py", files)
        self.assertEqual(self.records()[-1]["files"], ["tests/sub/test_012_a.py"])

    def test_R020_23_directory_of_mixed_specs(self):
        code, out = self.unfreeze_cli("tests")
        self.assertEqual(code, 1)
        self.assert_unchanged()

    def test_R020_39_phase_must_be_frozen_or_done(self):
        for phase in ("tests-draft", "tests-approved", "approved"):
            with self.subTest(phase=phase):
                self.spec("012", phase)
                self.commit_all(f"phase {phase}")
                code, out = self.unfreeze_cli("tests/test_012_b.py")
                self.assertEqual(code, 1)
                self.assertIn(phase, out)
                self.assertEqual(self.lock_file.read_bytes(), self.lock_before)
                self.assertFalse(self.chaos_log.exists())

    def test_R020_39_done_is_allowed(self):
        self.spec("012", "done")
        self.commit_all("done")
        code, _ = self.unfreeze_cli("tests/test_012_b.py")
        self.assertEqual(code, 0)
        self.assertEqual(self.spec_status("012"), "tests-draft")

    def test_R020_18_paused_refuses_unfreeze(self):
        self.write_log([self.record(1, "escalate", spec="012", gate="done", cause="owner",
                                    detail=["x"])])
        self.commit_all("escalated")
        code, out = self.unfreeze_cli("tests/test_012_b.py")
        self.assertEqual(code, 1)
        self.assertIn("#1", out)
        self.assertEqual(self.lock_file.read_bytes(), self.lock_before)
        self.assertEqual(len(self.records()), 1)


class PatientUnfreezeTests(UnfreezeCase):
    REST = "[chaos]\nenabled = true\nmax_rejections = 9\n"

    def test_R020_24_one_keep_frozen_rejects(self):
        for auditor, impl in ((UNFREEZE_PASS, UNFREEZE_FAIL), (UNFREEZE_FAIL, UNFREEZE_PASS)):
            with self.subTest(auditor=auditor, impl=impl):
                code, _ = self.unfreeze_cli("tests/test_012_b.py", auditor=auditor, impl=impl)
                self.assertEqual(code, 1)
                self.assert_unchanged()
        recs = self.records()
        self.assertEqual([r["kind"] for r in recs], ["reject", "reject"])
        rec = recs[0]
        self.assertEqual((rec["spec"], rec["gate"]), ("012", "unfreeze"))
        self.assertEqual([r["role"] for r in rec["reviews"]], ["test-auditor", "impl-reviewer"])
        self.assertEqual([r["verdict"] for r in rec["reviews"]], [UNFREEZE_PASS, UNFREEZE_FAIL])
        self.assertEqual([r["review"] for r in rec["reviews"]],
                         [AUDITOR.format(seq=1), IMPL.format(seq=1)])


class UnfreezeVerdictTests(UnfreezeCase):

    def test_R020_24_rejections_escalate(self):
        self.unfreeze_cli("tests/test_012_b.py", impl=UNFREEZE_FAIL)
        code, _ = self.unfreeze_cli("tests/test_012_b.py", impl=UNFREEZE_FAIL)
        self.assertEqual(code, 1)
        self.assertEqual(self.kinds(), ["reject", "reject", "escalate"])
        rec = self.records()[2]
        self.assertEqual((rec["cause"], rec["gate"], rec["detail"]),
                         ("rejections", "unfreeze", ["#1", "#2"]))

    def test_R020_24_an_unfreeze_resets_the_count(self):
        self.unfreeze_cli("tests/test_012_b.py", impl=UNFREEZE_FAIL)
        self.unfreeze_cli("tests/test_012_b.py")
        self.spec("012", "frozen")
        self.write_lock({"tests/test_012_b.py": "012", "tests/sub/test_012_a.py": "012",
                         "tests/test_011_x.py": "011", "tests/helpers.py": None})
        self.commit_all("frozen again")
        self.unfreeze_cli("tests/test_012_b.py", impl=UNFREEZE_FAIL)
        self.assertEqual(self.kinds(), ["reject", "unfreeze", "reject"])

    def test_R020_43_needs_owner_on_unfreeze(self):
        code, out = self.unfreeze_cli("tests/test_012_b.py", impl=OWNER)
        self.assertEqual(code, 1)
        self.assertIn("agentkit chaos log --open", out)
        self.assertEqual(self.kinds(), ["escalate"])
        rec = self.records()[0]
        self.assertEqual((rec["cause"], rec["gate"]), ("owner", "unfreeze"))
        detail = " ".join(rec["detail"])
        self.assertIn("impl-reviewer", detail)
        self.assertIn(IMPL.format(seq=1), detail)
        self.assertNotIn("test-auditor", detail)
        self.assertTrue((self.root / IMPL.format(seq=1)).is_file())
        self.assert_unchanged()

    def test_R020_19_critical_checks_run_on_unfreeze(self):
        self.write("AGENTS.md", "# changed\n")
        code, out = self.unfreeze_cli("tests/test_012_b.py")
        self.assertEqual(code, 1)
        self.assertIn("agentkit chaos log --open", out)
        self.assertEqual(self.kinds(), ["escalate"])
        rec = self.records()[0]
        self.assertEqual((rec["cause"], rec["detail"]), ("protected", ["AGENTS.md"]))
        self.assert_unchanged()

    def test_R020_19_verify_on_unfreeze(self):
        self.write("tests/test_011_x.py", "edited\n")
        code, _ = self.unfreeze_cli("tests/test_012_b.py")
        self.assertEqual(code, 1)
        self.assertEqual(self.records()[0]["cause"], "verify")
        self.assertEqual(self.records()[0]["detail"], ["modified tests/test_011_x.py"])

    def test_R020_43_needs_owner_before_keep_frozen(self):
        code, _ = self.unfreeze_cli("tests/test_012_b.py", auditor=UNFREEZE_FAIL, impl=OWNER)
        self.assertEqual(code, 1)
        self.assertEqual(self.kinds(), ["escalate"])
        self.assertEqual(self.records()[0]["cause"], "owner")
        self.assert_unchanged()

    def test_R020_38_unfreeze_paths_before_chaos_applies(self):
        self.write("agentkit.toml", '[kit]\nprofile = "fixture"\n\n'
                   '[chaos]\nenabled = true\nspecs = ["013"]\n')
        self.commit_all("only 013 under chaos")
        code, out = self.unfreeze_cli("tests/test_012_b.py", "tests/nowhere.py")
        self.assertEqual(code, 1)
        self.assertIn("tests/nowhere.py", out)
        self.assertNotIn("not under chaos mode", out)

    def test_R020_13_unfreeze_review_verdicts_are_checked(self):
        code, out = self.unfreeze_cli("tests/test_012_b.py", impl=SPEC_PASS)
        self.assertEqual(code, 2)
        self.assertIn(SPEC_PASS, out)
        self.assert_unchanged()
        self.assertFalse(self.chaos_log.exists())


class UnfreezePassTests(UnfreezeCase):

    def test_R020_25_both_pass(self):
        self.agent()  # no human check, no console (R020-25)
        # Succeeding in an agent environment shows that the owner check (R002-20) is skipped.
        with mock.patch("agentkit.lock.open_console", side_effect=AssertionError("console")):
            result = self.unfreeze_api(["tests/test_012_b.py", "tests/sub"],
                                       reason="  fixture was wrong  ")
        files = self.read_lock()["files"]
        self.assertEqual(sorted(files), ["tests/helpers.py", "tests/test_011_x.py"])
        self.assertEqual(self.spec_status("012"), "tests-draft")
        self.assertEqual(result, self.records()[-1])
        self.assertEqual(result["kind"], "unfreeze")

    def test_R020_25_unfreeze_log_entry(self):
        self.unfreeze_api(["tests/test_012_b.py", "tests/sub"], reason="  fixture was wrong  ")
        auditor = self.root / AUDITOR.format(seq=1)
        impl = self.root / IMPL.format(seq=1)
        expected = (LOG_HEADER
                    + "\n"
                    + f"## {NOW_TEXT} - chaos agent (Alice)\n"
                    + "reason: fixture was wrong\n"
                    + f"review: {AUDITOR.format(seq=1)} sha256 {sha256_lf(auditor.read_bytes())}"
                      " (chaos log #1)\n"
                    + f"review: {IMPL.format(seq=1)} sha256 {sha256_lf(impl.read_bytes())}"
                      " (chaos log #1)\n"
                    + "- tests/sub/test_012_a.py\n"
                    + "- tests/test_012_b.py\n")
        self.assertEqual(self.log_file.read_text(encoding="utf-8"), expected)

    def test_R020_25_appends_to_an_existing_log(self):
        old = LOG_HEADER + "\n## 2026-01-01T00:00:00Z - Owner\nreason: earlier\n- tests/old.py\n"
        self.write("tests.unfreeze-log.md", old)
        self.commit_all("earlier log")
        self.unfreeze_api(["tests/test_012_b.py"])
        text = self.log_file.read_text(encoding="utf-8")
        self.assertTrue(text.startswith(old))
        self.assertIn(f"\n\n## {NOW_TEXT} - chaos agent (Alice)\n", text[len(old) - 1:])

    def test_R020_25_record_appended_last(self):
        self.unfreeze_api(["tests/test_012_b.py"])
        rec = self.records()[-1]
        self.assertEqual(rec["seq"], 1)
        self.assertEqual(self.kinds(), ["unfreeze"])

    def test_R020_10_unfreeze_record(self):
        self.unfreeze_api(["tests/test_012_b.py", "tests/sub"], reason="  fixture was wrong  ")
        rec = self.records()[0]
        self.assertEqual(rec["spec"], "012")
        self.assertEqual(rec["gate"], "unfreeze")
        self.assertEqual(rec["files"], ["tests/sub/test_012_a.py", "tests/test_012_b.py"])
        self.assertEqual(rec["reason"], "fixture was wrong")
        self.assertEqual([r["role"] for r in rec["reviews"]], ["test-auditor", "impl-reviewer"])
        for review in rec["reviews"]:
            self.assertEqual(review["verdict"], UNFREEZE_PASS)
            self.assertEqual(review["review_sha256"],
                             sha256_lf((self.root / review["review"]).read_bytes()))
        for key in ("seq", "time", "commit", "user", "actor"):
            self.assertIn(key, rec)


class ClearTests(ChaosCase):

    def escalations(self, *seqs, cleared=()):
        recs, seq = [], 1
        for s in range(1, max(seqs) + 1):
            if s in seqs:
                recs.append(self.record(s, "escalate", spec="012", gate="approved", cause="owner",
                                        detail=["x"]))
            else:
                recs.append(self.record(s, "reject", spec="012", gate="approved",
                                        reviews=[self.cite("012", s, "approved", "spec-reviewer",
                                                           FAIL)]))
        for c in cleared:
            recs.append(self.record(len(recs) + 1, "clear", escalations=list(c), note="earlier"))
        self.write_log(recs)
        self.commit_all("escalations")

    def asker(self, answer=True):
        self.asked = []

        def confirm(prompt, expected):
            self.asked.append((prompt, expected))
            return answer
        return confirm

    def test_R020_26_clear_listed_escalations(self):
        self.escalations(1, 3)
        result = chaos.clear(self.cfg(), seqs=[3, 1], note="  spec reworded  ",
                             confirm=self.asker(), user="Owner", now=NOW)
        self.assertEqual([e for _, e in self.asked], ["clear 2"])
        rec = self.records()[-1]
        self.assertEqual(result, rec)
        self.assertEqual(rec["kind"], "clear")
        self.assertEqual(rec["seq"], 4)
        self.assertEqual(rec["escalations"], [1, 3])
        self.assertEqual(rec["actor"], "human")
        self.assertEqual(rec["user"], "Owner")
        self.assertEqual(chaos.open_escalations(self.cfg()), [])

    def test_R020_10_clear_record_has_the_note(self):
        self.escalations(1)
        chaos.clear(self.cfg(), seqs=[1], note="  spec reworded  ", confirm=self.asker(),
                    user="Owner", now=NOW)
        rec = self.records()[-1]
        self.assertEqual(rec["escalations"], [1])
        self.assertIn("spec reworded", rec["note"])

    def test_R020_26_clear_all(self):
        self.escalations(1, 3, 4, cleared=[(1,)])
        chaos.clear(self.cfg(), all_open=True, note="looked at all", confirm=self.asker(),
                    user="Owner", now=NOW)
        self.assertEqual([e for _, e in self.asked], ["clear 2"])
        self.assertEqual(self.records()[-1]["escalations"], [3, 4])

    def test_R020_26_agent_environment_refused(self):
        self.escalations(1)
        self.agent()
        before = self.chaos_log.read_bytes()
        with self.assertRaises(OwnerCheckError):
            chaos.clear(self.cfg(), seqs=[1], note="looked at it", confirm=self.asker())
        self.assertEqual(self.asked, [])
        code, _ = run_cli("chaos", "clear", "1", "--note", "looked at it")
        self.assertEqual(code, 2)
        self.assertEqual(self.chaos_log.read_bytes(), before)

    def test_R020_26_seqs_or_all_exactly_once(self):
        self.escalations(1)
        for args in (["--note", "looked at it"], ["1", "--all", "--note", "looked at it"]):
            with self.subTest(args=args):
                code, _ = run_cli("chaos", "clear", *args)
                self.assertEqual(code, 2)
        self.assertEqual(len(self.records()), 1)

    def test_R020_26_note_of_five_characters(self):
        self.escalations(1)
        for note in ("", "abcd", "  ab  "):
            with self.subTest(note=note):
                with self.assertRaises(chaos.ChaosUsageError):
                    chaos.clear(self.cfg(), seqs=[1], note=note, confirm=self.asker())
                code, _ = run_cli("chaos", "clear", "1", "--note", note)
                self.assertEqual(code, 2)
        self.assertEqual(len(self.records()), 1)

    def test_R020_26_note_of_exactly_five_characters(self):
        self.escalations(1)
        chaos.clear(self.cfg(), seqs=[1], note="  abcde ", confirm=self.asker(), user="O", now=NOW)
        self.assertEqual(self.kinds()[-1], "clear")

    def test_R020_26_default_confirm_uses_the_console(self):
        self.escalations(1)
        reader, writer = io.StringIO("clear 1\n"), io.StringIO()
        with mock.patch("agentkit.lock.open_console", return_value=(reader, writer)):
            code, _ = run_cli("chaos", "clear", "1", "--note", "looked at it")
        self.assertEqual(code, 0)
        self.assertIn("clear 1", writer.getvalue())
        self.assertEqual(self.kinds()[-1], "clear")

    def test_R020_26_works_with_chaos_off(self):
        self.escalations(1)
        self.write("agentkit.toml", '[kit]\nprofile = "fixture"\n\n[chaos]\nenabled = false\n')
        self.commit_all("chaos off")
        chaos.clear(self.cfg(), seqs=[1], note="looked at it", confirm=self.asker(),
                    user="Owner", now=NOW)
        self.assertEqual(self.kinds()[-1], "clear")

    def test_R020_40_seq_not_open(self):
        self.escalations(1, 3, cleared=[(1,)])
        before = self.chaos_log.read_bytes()
        for seqs in ([1], [2], [3, 9]):  # cleared, a reject, unknown
            with self.subTest(seqs=seqs):
                with self.assertRaises(chaos.ChaosError) as ctx:
                    chaos.clear(self.cfg(), seqs=seqs, note="looked at it", confirm=self.asker())
                self.assertNotIsInstance(ctx.exception, chaos.ChaosUsageError)
                self.assertEqual(self.asked, [])  # checked before asking
        code, _ = run_cli("chaos", "clear", "2", "--note", "looked at it")
        self.assertEqual(code, 1)
        self.assertEqual(self.chaos_log.read_bytes(), before)

    def test_R020_40_all_finds_none(self):
        self.escalations(1, cleared=[(1,)])
        with self.assertRaises(chaos.ChaosError):
            chaos.clear(self.cfg(), all_open=True, note="looked at it", confirm=self.asker())
        self.assertEqual(self.asked, [])

    def test_R020_40_wrong_answer(self):
        self.escalations(1)
        before = self.chaos_log.read_bytes()
        with self.assertRaises(chaos.ChaosError):
            chaos.clear(self.cfg(), seqs=[1], note="looked at it", confirm=self.asker(False))
        self.assertEqual(self.chaos_log.read_bytes(), before)
        reader, writer = io.StringIO("yes\n"), io.StringIO()
        with mock.patch("agentkit.lock.open_console", return_value=(reader, writer)):
            code, _ = run_cli("chaos", "clear", "1", "--note", "looked at it")
        self.assertEqual(code, 1)
        self.assertEqual(self.chaos_log.read_bytes(), before)

    def test_R020_40_console_cannot_be_opened(self):
        self.escalations(1)
        before = self.chaos_log.read_bytes()
        with mock.patch("agentkit.lock.open_console", side_effect=OSError("no tty")):
            code, _ = run_cli("chaos", "clear", "1", "--note", "looked at it")
        self.assertEqual(code, 1)
        self.assertEqual(self.chaos_log.read_bytes(), before)


class ClearWithoutGitTests(ChaosCase):
    USE_GIT = False

    def test_R020_26_agent_check_before_git(self):
        self.agent()
        with self.assertRaises(OwnerCheckError):
            chaos.clear(self.cfg(), all_open=True, note="looked at it", confirm=lambda p, e: True)


class LogCommandTests(ChaosCase):

    def history(self):
        files = ["tests/a.py", "tests/b.py"]
        recs = [
            self.record(1, "reject", spec="012", gate="approved",
                        reviews=[self.cite("012", 1, "approved", "spec-reviewer", FAIL)]),
            self.record(2, "approve", spec="012", gate="approved",
                        reviews=[self.cite("012", 2, "approved", "spec-reviewer", SPEC_PASS)]),
            self.record(3, "approve", spec="012", gate="frozen", reviews=[], files=files,
                        based_on=None),
            self.record(4, "escalate", spec="012", gate="done", cause="protected",
                        detail=["AGENTS.md", "CLAUDE.md"]),
            self.record(5, "unfreeze", spec="012", gate="unfreeze", files=files,
                        reason="wrong fixture",
                        reviews=[self.cite("012", 5, "unfreeze", "test-auditor", UNFREEZE_PASS),
                                 self.cite("012", 5, "unfreeze", "impl-reviewer", UNFREEZE_PASS)]),
            self.record(6, "escalate", spec="013", gate="approved", cause="owner", detail=["y"]),
            self.record(7, "clear", escalations=[4, 6], note="spec reworded", actor="human"),
        ]
        self.write_log(recs)
        return recs

    EXPECTED = [
        f"#1 {NOW_TEXT} reject 012 approved {FAIL} (agent)",
        f"#2 {NOW_TEXT} approve 012 approved {SPEC_PASS} (agent)",
        f"#3 {NOW_TEXT} approve 012 frozen files=2 (agent)",
        f"#4 {NOW_TEXT} escalate 012 done protected (agent)",
        f"#5 {NOW_TEXT} unfreeze 012 unfreeze {UNFREEZE_PASS} + {UNFREEZE_PASS} (agent)",
        f"#6 {NOW_TEXT} escalate 013 approved owner (agent)",
        f"#7 {NOW_TEXT} clear - - #4,#6: spec reworded (human)",
    ]

    def test_R020_27_format(self):
        self.assertEqual(chaos.format_log(self.history()), self.EXPECTED)

    def test_R020_27_cli_prints_oldest_first(self):
        self.history()
        code, out = run_cli("chaos", "log")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), self.EXPECTED)

    def test_R020_27_last_n(self):
        self.history()
        code, out = run_cli("chaos", "log", "--last", "2")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), self.EXPECTED[-2:])
        for n in ("0", "-1"):
            with self.subTest(n=n):
                code, _ = run_cli("chaos", "log", "--last", n)
                self.assertEqual(code, 2)

    def test_R020_27_default_is_the_last_20(self):
        self.write_log([self.record(i, "clear", escalations=[], note=f"note {i}")
                        for i in range(1, 26)])
        code, out = run_cli("chaos", "log")
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertEqual(len(lines), 20)
        self.assertTrue(lines[0].startswith("#6 "))
        self.assertTrue(lines[-1].startswith("#25 "))

    def test_R020_27_spec_filter(self):
        self.history()
        code, out = run_cli("chaos", "log", "--spec", "013")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), [self.EXPECTED[5]])

    def test_R020_27_long_lines_are_cut(self):
        recs = [self.record(1, "clear", escalations=[7], note="x" * 300)]
        line = chaos.format_log(recs)[0]
        self.assertEqual(len(line), 200)
        self.assertTrue(line.endswith("…"))
        self.assertEqual(line, (f"#1 {NOW_TEXT} clear - - #7: " + "x" * 300)[:199] + "…")

    def test_R020_27_works_with_chaos_off(self):
        self.history()
        self.write("agentkit.toml", '[kit]\nprofile = "fixture"\n')
        code, out = run_cli("chaos", "log")
        self.assertEqual(code, 0)
        self.assertEqual(len(out.splitlines()), 7)

    def test_R020_27_no_log(self):
        code, out = run_cli("chaos", "log")
        self.assertEqual(code, 0)
        self.assertNotIn("#", out)

    def test_R020_27_malformed_log_exit_1(self):
        self.write(self.chaos_log, dumps(self.record(1, "clear", escalations=[], note="ok")) + "\n"
                                  + "{broken\n")
        code, out = run_cli("chaos", "log")
        self.assertEqual(code, 1)
        self.assertRegex(out, r"\b2\b")

    def test_R020_41_open_escalations_with_details(self):
        recs = self.history()[:6]
        self.write_log(recs)
        expected = [self.EXPECTED[3], "  AGENTS.md", "  CLAUDE.md", self.EXPECTED[5], "  y"]
        self.assertEqual(chaos.format_log(recs, open_only=True), expected)
        code, out = run_cli("chaos", "log", "--open")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), expected)

    def test_R020_41_none_open(self):
        recs = self.history()
        self.assertEqual(chaos.format_log(recs, open_only=True), ["no open escalation"])
        code, out = run_cli("chaos", "log", "--open")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["no open escalation"])


class AuditTests(ChaosCase):

    def logged(self):
        recs = [self.record(1, "reject", spec="012", gate="approved",
                            reviews=[self.cite("012", 1, "approved", "spec-reviewer", FAIL)]),
                self.record(2, "approve", spec="012", gate="approved",
                            reviews=[self.cite("012", 2, "approved", "spec-reviewer", SPEC_PASS)])]
        self.write_log(recs)
        return recs

    def test_R020_28_no_log_passes(self):
        self.assertEqual(chaos.audit(self.cfg()), [])
        code, _ = run_cli("chaos", "audit")
        self.assertEqual(code, 0)

    def test_R020_28_valid_log_passes(self):
        recs = self.logged()
        self.commit_all("log")
        self.assertEqual(chaos.audit(self.cfg()), [])
        self.write_log(recs + [self.record(3, "clear", escalations=[], note="later")])
        self.assertEqual(chaos.audit(self.cfg()), [])  # appended since HEAD

    def test_R020_28_log_missing_at_ref_counts_as_empty(self):
        self.logged()
        self.assertEqual(chaos.audit(self.cfg(), base="HEAD"), [])

    def test_R020_28_malformed_log(self):
        self.write(self.chaos_log, "{broken\n")
        problems = chaos.audit(self.cfg())
        self.assertTrue(problems)
        code, _ = run_cli("chaos", "audit")
        self.assertEqual(code, 1)

    def test_R020_28_cited_review_missing(self):
        self.logged()
        (self.spec_dir("012") / "reviews" / "1-approved-spec-reviewer.md").unlink()
        problems = chaos.audit(self.cfg())
        self.assertTrue(any("1-approved-spec-reviewer.md" in p for p in problems))
        code, _ = run_cli("chaos", "audit")
        self.assertEqual(code, 1)

    def test_R020_28_cited_review_changed(self):
        self.logged()
        self.write("specs/012-fixture/reviews/2-approved-spec-reviewer.md", "# edited\n")
        problems = chaos.audit(self.cfg())
        self.assertTrue(any("2-approved-spec-reviewer.md" in p for p in problems))

    def test_R020_28_crlf_copy_has_the_same_hash(self):
        self.logged()
        path = self.spec_dir("012") / "reviews" / "2-approved-spec-reviewer.md"
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        self.assertEqual(chaos.audit(self.cfg()), [])

    def test_R020_28_rewritten_log(self):
        recs = self.logged()
        self.commit_all("log")
        recs[0]["user"] = "Mallory"
        self.write_log(recs)
        problems = chaos.audit(self.cfg())
        self.assertTrue(problems)
        code, _ = run_cli("chaos", "audit", "--base", "HEAD")
        self.assertEqual(code, 1)

    def test_R020_28_truncated_log(self):
        recs = self.logged()
        self.commit_all("log")
        self.write_log(recs[:1])
        self.assertTrue(chaos.audit(self.cfg()))

    def test_R020_28_unknown_ref_skips_only_the_prefix_check(self):
        recs = self.logged()
        self.commit_all("log")
        recs[0]["user"] = "Mallory"
        self.write_log(recs)
        self.assertEqual(chaos.audit(self.cfg(), base="no-such-ref"), [])
        (self.spec_dir("012") / "reviews" / "1-approved-spec-reviewer.md").unlink()
        self.assertTrue(chaos.audit(self.cfg(), base="no-such-ref"))

    def test_R020_28_staged_reads_the_index(self):
        self.logged()
        self.git("add", "-A")
        self.write("specs/012-fixture/reviews/2-approved-spec-reviewer.md", "# edited\n")
        self.assertEqual(chaos.audit(self.cfg(), staged=True), [])
        self.assertTrue(chaos.audit(self.cfg(), staged=False))
        code, _ = run_cli("chaos", "audit", "--staged")
        self.assertEqual(code, 0)

    def test_R020_28_staged_rewritten_log(self):
        recs = self.logged()
        self.commit_all("log")
        recs[1]["user"] = "Mallory"
        self.write_log(recs)
        self.git("add", "-A")
        self.assertTrue(chaos.audit(self.cfg(), staged=True))


class AuditWithoutGitTests(ChaosCase):
    USE_GIT = False

    def test_R020_28_no_git_skips_only_the_prefix_check(self):
        self.write_log([self.record(1, "approve", commit="0" * 40, spec="012", gate="approved",
                                    reviews=[self.cite("012", 1, "approved", "spec-reviewer",
                                                       SPEC_PASS)])])
        self.assertEqual(chaos.audit(self.cfg()), [])
        (self.spec_dir("012") / "reviews" / "1-approved-spec-reviewer.md").unlink()
        self.assertTrue(chaos.audit(self.cfg()))
