"""Spec 004: end-of-turn verify and session-start status (R004-15 to R004-20)."""
from __future__ import annotations

import json
import unittest
from unittest import mock

from agentkit.payloads import FORMATS
from tests.hook_fixtures import CLAUDE_SHAPED, FORMAT_NAMES, FROZEN, PLUGINS, RESTORE_HINT, HookCase

PROBLEMS = ["modified app/src/test/FooTest.kt", "hint: restore with `agentkit lock restore`"]
STATUS = ["agentkit: profile fixture | lock: OK", "spec 004 hook-dialects [frozen]"]


class StopResponseTests(unittest.TestCase):
    """stop_response() and session_response() on given problems and text."""

    def test_R004_16_block_without_stop_hook_active(self):
        for fmt in CLAUDE_SHAPED:
            for payload in ({}, {"stop_hook_active": False}):
                with self.subTest(fmt=fmt, payload=payload):
                    response = FORMATS[fmt].stop_response(payload, PROBLEMS)
                    out = json.loads(response.stdout)
                    self.assertEqual(set(out), {"decision", "reason"})
                    self.assertEqual(out["decision"], "block")
                    for problem in PROBLEMS:
                        self.assertIn(problem, out["reason"])
                    self.assertEqual(response.code, 0)

    def test_R004_16_no_problems_prints_nothing(self):
        for fmt in CLAUDE_SHAPED:
            for payload in ({}, {"stop_hook_active": True}):
                with self.subTest(fmt=fmt, payload=payload):
                    response = FORMATS[fmt].stop_response(payload, [])
                    self.assertEqual((response.stdout.strip(), response.code), ("", 0))

    def test_R004_17_claude_warns_instead_of_blocking_again(self):
        response = FORMATS["claude"].stop_response({"stop_hook_active": True}, PROBLEMS)
        out = json.loads(response.stdout)
        self.assertEqual(set(out), {"systemMessage"})
        for problem in PROBLEMS:
            self.assertIn(problem, out["systemMessage"])
        self.assertEqual(response.code, 0)

    def test_R004_17_codex_and_dsh_stay_silent_when_active(self):
        for fmt in ("codex", "dsh"):
            with self.subTest(fmt=fmt):
                response = FORMATS[fmt].stop_response({"stop_hook_active": True}, PROBLEMS)
                self.assertEqual((response.stdout.strip(), response.code), ("", 0))

    def test_R004_18_plugin_verify_result(self):
        for fmt in PLUGINS:
            with self.subTest(fmt=fmt):
                bad = FORMATS[fmt].stop_response({}, PROBLEMS)
                out = json.loads(bad.stdout)
                self.assertEqual(set(out), {"ok", "message"})
                self.assertIs(out["ok"], False)
                for problem in PROBLEMS:
                    self.assertIn(problem, out["message"])
                good = json.loads(FORMATS[fmt].stop_response({}, []).stdout)
                self.assertEqual(set(good), {"ok", "message"})
                self.assertIs(good["ok"], True)
                self.assertIsInstance(good["message"], str)

    def test_R004_18_plugin_ignores_stop_hook_active(self):
        for fmt in PLUGINS:
            with self.subTest(fmt=fmt):
                out = json.loads(FORMATS[fmt].stop_response({"stop_hook_active": True},
                                                            PROBLEMS).stdout)
                self.assertIs(out["ok"], False)

    def test_R004_20_session_response(self):
        text = "\n".join(STATUS)
        for fmt in ("claude", "codex"):
            with self.subTest(fmt=fmt):
                response = FORMATS[fmt].session_response(text)
                self.assertEqual(json.loads(response.stdout),
                                 {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                         "additionalContext": text}})
                self.assertEqual(response.code, 0)
        for fmt in PLUGINS:
            with self.subTest(fmt=fmt):
                response = FORMATS[fmt].session_response(text)
                self.assertEqual(json.loads(response.stdout), {"context": text})
                self.assertEqual(response.code, 0)


class VerifyCommandTests(HookCase):

    def verify(self, fmt: str | None = None, **payload) -> tuple[int, str, str]:
        argv = ("verify",) if fmt is None else ("verify", "--format", fmt)
        return self.hook(*argv, stdin=json.dumps(payload))

    def assert_problems(self, text: str, kind: str) -> None:
        self.assertIn(f"{kind} {FROZEN}", text)
        self.assertIn(RESTORE_HINT, text)
        self.assertIn("owner", text.lower())

    def test_R004_15_modified_file_and_hint(self):
        self.violate()
        code, out, _ = self.verify("claude")
        self.assertEqual(code, 0)
        self.assert_problems(json.loads(out)["reason"], "modified")

    def test_R004_15_missing_file(self):
        (self.root / FROZEN).unlink()
        code, out, _ = self.verify("codex")
        self.assertEqual(code, 0)
        self.assert_problems(json.loads(out)["reason"], "missing")

    def test_R004_16_clean_lock_prints_nothing(self):
        for fmt in CLAUDE_SHAPED:
            with self.subTest(fmt=fmt):
                self.assertEqual(self.verify(fmt)[:2], (0, ""))

    def test_R004_16_violation_blocks_first_stop(self):
        self.violate()
        for fmt in CLAUDE_SHAPED:
            for payload in ({}, {"stop_hook_active": False}):
                with self.subTest(fmt=fmt, payload=payload):
                    code, out, _ = self.verify(fmt, **payload)
                    self.assertEqual(code, 0)
                    self.assertEqual(json.loads(out)["decision"], "block")

    def test_R004_17_second_stop_does_not_block_again(self):
        self.violate()
        code, out, _ = self.verify("claude", stop_hook_active=True)
        self.assertEqual(code, 0)
        self.assert_problems(json.loads(out)["systemMessage"], "modified")
        for fmt in ("codex", "dsh"):
            with self.subTest(fmt=fmt):
                self.assertEqual(self.verify(fmt, stop_hook_active=True)[:2], (0, ""))

    def test_R004_18_plugin_verify(self):
        for fmt in PLUGINS:
            with self.subTest(fmt=fmt, state="clean"):
                code, out, _ = self.verify(fmt)
                self.assertEqual(code, 0)
                self.assertIs(json.loads(out)["ok"], True)
        self.violate()
        for fmt in PLUGINS:
            with self.subTest(fmt=fmt, state="violated"):
                code, out, _ = self.verify(fmt)
                self.assertEqual(code, 0)
                out = json.loads(out)
                self.assertIs(out["ok"], False)
                self.assert_problems(out["message"], "modified")

    def test_R004_19_plain_verify(self):
        code, out, _ = self.verify()
        self.assertEqual((code, out.strip()), (0, "verify: OK"))
        self.violate()
        code, out, _ = self.verify()
        self.assertEqual(code, 1)
        self.assert_problems(out, "modified")
        self.assertNotIn("verify: OK", out)

    def test_R004_19_plain_verify_needs_no_stdin(self):
        code, out, _ = self.hook("verify", stdin="")
        self.assertEqual((code, out.strip()), (0, "verify: OK"))


class TwoFrozenFilesTests(HookCase):
    FROZEN_EXTRA = ("app/src/test/BarTest.kt",)

    def test_R004_15_each_violated_file_is_reported(self):
        self.violate()
        (self.root / "app/src/test/BarTest.kt").unlink()
        for fmt in (None, "claude", "pi"):
            with self.subTest(fmt=fmt):
                argv = ("verify",) if fmt is None else ("verify", "--format", fmt)
                code, out, _ = self.hook(*argv, stdin="{}")
                if fmt == "claude":
                    out = json.loads(out)["reason"]
                elif fmt == "pi":
                    out = json.loads(out)["message"]
                self.assertIn(f"modified {FROZEN}", out)
                self.assertIn("missing app/src/test/BarTest.kt", out)
                self.assertIn(RESTORE_HINT, out)


class StatusCommandTests(HookCase):

    def status(self, fmt: str) -> tuple[int, str, list]:
        seen = []

        def fake(cfg):
            seen.append(cfg)
            return list(STATUS)

        with mock.patch("agentkit.status.status_lines", side_effect=fake):
            code, out, _ = self.hook("status", "--format", fmt, stdin="{}")
        return code, out, seen

    def test_R004_20_claude_and_codex(self):
        for fmt in ("claude", "codex"):
            with self.subTest(fmt=fmt):
                code, out, seen = self.status(fmt)
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(out),
                                 {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                         "additionalContext": "\n".join(STATUS)}})
                self.assertEqual(len(seen), 1)
                self.assertEqual(seen[0].root.resolve(), self.root.resolve())

    def test_R004_20_plugin_protocol(self):
        for fmt in PLUGINS:
            with self.subTest(fmt=fmt):
                code, out, _ = self.status(fmt)
                self.assertEqual((code, json.loads(out)), (0, {"context": "\n".join(STATUS)}))

    def test_R004_20_every_format_exits_0(self):
        for fmt in FORMAT_NAMES:
            with self.subTest(fmt=fmt):
                self.assertEqual(self.status(fmt)[0], 0)


if __name__ == "__main__":
    unittest.main()
