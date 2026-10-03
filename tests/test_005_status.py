"""Spec 005: `agentkit spec-status` and `set_status()` (R005-06 to R005-08, R005-18)."""
from __future__ import annotations

import os

from agentkit import specs
from tests.spec_fixtures import SpecCase
from tests.support import run_cli

BODY = "# Title\n\nstatus: in the body stays\n\n- **x** trailing  \n"


class SpecStatusTests(SpecCase):

    def setUp(self):
        super().setUp()
        self.folder = self.spec("004", status="approved", body=BODY)
        self.md = self.folder / "spec.md"

    def test_R005_06_sets_status_and_keeps_the_rest(self):
        before = self.md.read_bytes()
        code, _ = run_cli("spec-status", "004", "tests-draft")
        self.assertEqual(code, 0)
        after = self.md.read_bytes()
        self.assertEqual(after, before.replace(b"status: approved", b"status: tests-draft", 1))
        self.assertEqual(specs.find_spec(self.cfg(), "004").status, "tests-draft")

    def test_R005_06_every_non_frozen_phase_accepted(self):
        for phase in ("draft", "approved", "tests-draft", "tests-approved", "done"):
            code, out = run_cli("spec-status", "004", phase)
            self.assertEqual(code, 0, out)
            self.assertEqual(specs.find_spec(self.cfg(), "004").status, phase)

    def test_R005_06_crlf_file(self):
        crlf = self.md.read_bytes().replace(b"\n", b"\r\n")
        self.md.write_bytes(crlf)
        code, _ = run_cli("spec-status", "004", "done")
        self.assertEqual(code, 0)
        self.assertEqual(self.md.read_bytes(),
                         crlf.replace(b"status: approved\r\n", b"status: done\r\n", 1))

    def test_R005_06_utf8_body_untouched(self):
        self.spec("004", status="approved", body="Données — ✓\n")
        before = self.md.read_bytes()
        run_cli("spec-status", "004", "done")
        self.assertEqual(self.md.read_bytes(),
                         before.replace(b"status: approved", b"status: done", 1))

    def test_R005_06_missing_status_line_added(self):
        self.spec("004", status=None, body=BODY)
        code, _ = run_cli("spec-status", "004", "approved")
        self.assertEqual(code, 0)
        self.assertEqual(specs.find_spec(self.cfg(), "004").status, "approved")
        self.assertIn(BODY, self.md.read_text(encoding="utf-8"))

    def test_R005_06_set_status_api(self):
        spec = specs.find_spec(self.cfg(), "004")
        self.assertIsNone(specs.set_status(spec, "tests-draft"))
        self.assertEqual(specs.find_spec(self.cfg(), "004").status, "tests-draft")

    def test_R005_06_set_status_ignores_chaos(self):
        self.write("agentkit.toml", '[kit]\nprofile = "fixture"\n\n[chaos]\nenabled = true\n')
        os.environ["AGENTKIT_AGENT"] = "1"
        for phase in ("approved", "tests-approved", "done"):
            specs.set_status(specs.find_spec(self.cfg(), "004"), phase)
            self.assertEqual(specs.find_spec(self.cfg(), "004").status, phase)

    def test_R005_07_frozen_refused(self):
        before = self.md.read_bytes()
        code, out = run_cli("spec-status", "004", "frozen")
        self.assertEqual(code, 1)
        self.assertIn("lock freeze", out)
        self.assertEqual(self.md.read_bytes(), before)

    def test_R005_08_unknown_phase(self):
        before = self.md.read_bytes()
        for bad in ("finished", "Approved", "", "tests_draft"):
            code, _ = run_cli("spec-status", "004", bad)
            self.assertEqual(code, 1, bad)
        self.assertEqual(self.md.read_bytes(), before)

    def test_R005_08_unknown_spec(self):
        before = self.tree()
        code, out = run_cli("spec-status", "009", "approved")
        self.assertEqual(code, 1)
        self.assertIn("009", out)
        self.assertEqual(self.tree(), before)


class DropTransitionTests(SpecCase):

    def test_R005_18_drop_allowed_from_early_phases(self):
        for phase in ("draft", "approved", "tests-draft"):
            self.spec("004", status=phase)
            code, out = run_cli("spec-status", "004", "dropped")
            self.assertEqual(code, 0, f"{phase}: {out}")
            self.assertEqual(specs.find_spec(self.cfg(), "004").status, "dropped")

    def test_R005_18_drop_refused_from_later_phases(self):
        for phase in ("tests-approved", "frozen", "done"):
            self.spec("004", status=phase)
            before = self.tree()
            code, out = run_cli("spec-status", "004", "dropped")
            self.assertEqual(code, 1, phase)
            self.assertIn("unfreeze", out)
            self.assertEqual(self.tree(), before)
