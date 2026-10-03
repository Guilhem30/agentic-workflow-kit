"""Spec 002, chaos amendment: `lock audit` also audits the chaos log (R002-33), and agents may not
run `lock freeze --spec` where chaos applies (R002-34). This file belongs to spec 002; it is
frozen by path after the bootstrap freeze (see specs/002-test-lock/progress.md)."""
from __future__ import annotations

import os

from agentkit import lock
from tests.chaos_fixtures import SPEC_PASS, ChaosCase
from tests.support import rid, run_cli


class AuditChaosLogTests(ChaosCase):

    def logged(self):
        self.write_log([self.record(1, "approve", spec="012", gate="approved",
                                    reviews=[self.cite("012", 1, "approved", "spec-reviewer",
                                                       SPEC_PASS)])])
        return self.spec_dir("012") / "reviews" / "1-approved-spec-reviewer.md"

    def test_R002_33_valid_chaos_log_passes(self):
        self.logged()
        self.commit_all("log")
        self.assertEqual(lock.audit(self.cfg()), [])
        code, _ = run_cli("lock", "audit")
        self.assertEqual(code, 0)

    def test_R002_33_chaos_problems_fail_lock_audit(self):
        self.logged().unlink()
        problems = lock.audit(self.cfg())
        self.assertTrue(any("1-approved-spec-reviewer.md" in p for p in problems))
        code, out = run_cli("lock", "audit")
        self.assertEqual(code, 1)
        self.assertIn("1-approved-spec-reviewer.md", out)

    def test_R002_33_rewritten_chaos_log(self):
        self.logged()
        self.commit_all("log")
        self.write_log([self.record(1, "approve", spec="012", gate="approved", user="Mallory",
                                    reviews=[self.cite("012", 1, "approved", "spec-reviewer",
                                                       SPEC_PASS)])])
        self.assertTrue(lock.audit(self.cfg(), base="HEAD"))

    def test_R002_33_no_chaos_log_unchanged(self):
        self.write("specs/012-fixture/reviews/stray.md", "not cited\n")
        self.assertEqual(lock.audit(self.cfg()), [])

    def test_R002_33_staged_reads_the_index(self):
        review = self.logged()
        self.git("add", "-A")
        review.unlink()
        self.assertEqual(lock.audit(self.cfg(), staged=True), [])
        self.assertTrue(lock.audit(self.cfg(), staged=False))

    def test_R002_33_staged_without_a_staged_log(self):
        self.logged().unlink()  # only in the worktree, never staged
        self.assertEqual(lock.audit(self.cfg(), staged=True), [])

    def test_R002_33_malformed_table_uses_the_default_log(self):
        self.write("agentkit.toml", '[kit]\nprofile = "fixture"\n\n'
                   '[chaos]\nenabled = true\nmax_rejections = 0\nlog = "meta/c.jsonl"\n')
        self.logged().unlink()
        self.assertTrue(lock.audit(self.cfg()))


class AgentFreezeTests(ChaosCase):
    REST = '[chaos]\nenabled = true\nspecs = ["012"]\n'
    SPECS = {"012": "tests-approved", "013": "tests-approved"}

    def setUp(self) -> None:
        super().setUp()
        self.write("tests/test_012_x.py", f"# {rid('012', '01')}\n")
        self.write("tests/test_013_x.py", f"# {rid('013', '01')}\n")

    def test_R002_34_agent_refused_where_chaos_applies(self):
        self.agent()
        code, out = run_cli("lock", "freeze", "--spec", "012")
        self.assertEqual(code, 1)
        self.assertIn("chaos approve 012 frozen", out)
        self.assertFalse(self.lock_file.exists())
        self.assertEqual(self.spec_status("012"), "tests-approved")

    def test_R002_34_other_specs_and_the_owner_unchanged(self):
        self.agent()
        code, _ = run_cli("lock", "freeze", "--spec", "013")
        self.assertEqual(code, 0)
        self.assertEqual(self.spec_status("013"), "frozen")
        os.environ.pop("AGENTKIT_AGENT", None)  # the owner, in their own terminal
        code, _ = run_cli("lock", "freeze", "--spec", "012")
        self.assertEqual(code, 0)
        self.assertEqual(self.spec_status("012"), "frozen")

    def test_R002_34_api_does_not_check(self):
        self.agent()
        result = lock.freeze(self.cfg(), spec="012")
        self.assertEqual(result.added, ["tests/test_012_x.py"])
        self.assertEqual(self.spec_status("012"), "frozen")
