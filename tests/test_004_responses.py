"""Spec 004: pre-tool responses (R004-10 to R004-14, R004-22)."""
from __future__ import annotations

import json
import unittest

from agentkit.payloads import FORMATS
from agentkit.payloads.base import Response
from tests.hook_fixtures import (ALLOW, ALLOWING, ASK, ASK_PREFIX, CLAUDE_SHAPED, DEGRADED, DENY,
                                 FORMAT_NAMES, FROZEN, PLUGINS, Decision, HookCase, verdict_of)

REASON = "app/src/test/FooTest.kt is frozen"
DEGRADED_MSG = "agentkit guard error (allowing): agentkit.toml did not load"


def pre_tool(verdict: str, reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": verdict,
                                   "permissionDecisionReason": f"agentkit: {reason}"}}


class PreResponseTests(unittest.TestCase):
    """pre_response() on hand-made Decisions."""

    def respond(self, fmt: str, verdict: str, reasons=(REASON,), degraded=False) -> Response:
        response = FORMATS[fmt].pre_response(Decision(verdict, list(reasons), degraded=degraded))
        self.assertIsInstance(response, Response)
        return response

    def test_R004_10_claude_allow_is_silent(self):
        response = self.respond("claude", ALLOW, ())
        self.assertEqual((response.stdout.strip(), response.code), ("", 0))

    def test_R004_10_claude_allow_with_reasons_is_still_silent(self):
        response = self.respond("claude", ALLOW, ("some note",))
        self.assertEqual((response.stdout.strip(), response.code), ("", 0))

    def test_R004_11_claude_deny_and_ask(self):
        for verdict in (DENY, ASK):
            with self.subTest(verdict=verdict):
                response = self.respond("claude", verdict)
                self.assertEqual(json.loads(response.stdout), pre_tool(verdict, REASON))
                self.assertEqual(response.code, 0)

    def test_R004_11_reason_joins_all_reasons(self):
        response = self.respond("claude", DENY, ("one", "two"))
        self.assertEqual(json.loads(response.stdout), pre_tool(DENY, "one; two"))

    def test_R004_12_codex_and_dsh_deny(self):
        for fmt in ("codex", "dsh"):
            with self.subTest(fmt=fmt):
                response = self.respond(fmt, DENY)
                self.assertEqual(json.loads(response.stdout), pre_tool(DENY, REASON))
                self.assertEqual(response.code, 0)

    def test_R004_12_codex_and_dsh_ask_becomes_deny(self):
        for fmt in ("codex", "dsh"):
            with self.subTest(fmt=fmt):
                response = self.respond(fmt, ASK)
                out = json.loads(response.stdout)["hookSpecificOutput"]
                self.assertEqual(out["permissionDecision"], DENY)
                self.assertEqual(out["hookEventName"], "PreToolUse")
                self.assertTrue(out["permissionDecisionReason"].startswith("agentkit: "))
                self.assertIn(ASK_PREFIX + REASON, out["permissionDecisionReason"])
                self.assertEqual(response.code, 0)

    def test_R004_12_codex_and_dsh_allow_is_silent(self):
        for fmt in ("codex", "dsh"):
            with self.subTest(fmt=fmt):
                response = self.respond(fmt, ALLOW, ())
                self.assertEqual((response.stdout.strip(), response.code), ("", 0))

    def test_R004_13_plugin_always_prints_a_decision(self):
        for fmt in PLUGINS:
            for verdict in (ALLOW, DENY):
                with self.subTest(fmt=fmt, verdict=verdict):
                    response = self.respond(fmt, verdict)
                    out = json.loads(response.stdout)
                    self.assertEqual(set(out), {"decision", "reason"})
                    self.assertEqual(out["decision"], verdict)
                    self.assertIsInstance(out["reason"], str)
                    if verdict == DENY:
                        self.assertIn(REASON, out["reason"])
                    self.assertEqual(response.code, 0)

    def test_R004_13_plugin_allow_without_reasons(self):
        for fmt in PLUGINS:
            with self.subTest(fmt=fmt):
                out = json.loads(self.respond(fmt, ALLOW, ()).stdout)
                self.assertEqual(out["decision"], ALLOW)
                self.assertIsInstance(out["reason"], str)

    def test_R004_14_opencode_ask_becomes_deny(self):
        response = self.respond("opencode", ASK)
        out = json.loads(response.stdout)
        self.assertEqual(out["decision"], DENY)
        self.assertIn(ASK_PREFIX + REASON, out["reason"])
        self.assertEqual(response.code, 0)

    def test_R004_14_pi_keeps_ask(self):
        response = self.respond("pi", ASK)
        out = json.loads(response.stdout)
        self.assertEqual(out["decision"], ASK)
        self.assertIn(REASON, out["reason"])
        self.assertNotIn(ASK_PREFIX, out["reason"])
        self.assertEqual(response.code, 0)

    def test_R004_22_degraded_allow_exits_1_with_the_message(self):
        for fmt in FORMAT_NAMES:
            with self.subTest(fmt=fmt):
                response = self.respond(fmt, ALLOW, (DEGRADED_MSG,), degraded=True)
                self.assertEqual(response.code, 1)
                self.assertIn(DEGRADED_MSG, response.stderr)
                if fmt in PLUGINS:
                    self.assertEqual(json.loads(response.stdout)["decision"], ALLOW)
                else:
                    self.assertEqual(response.stdout.strip(), "")

    def test_R004_22_the_degraded_flag_decides_not_the_text(self):
        for fmt in FORMAT_NAMES:
            with self.subTest(fmt=fmt, degraded=True):
                response = self.respond(fmt, ALLOW, ("other text",), degraded=True)
                self.assertEqual(response.code, 1)
                self.assertIn("other text", response.stderr)
            with self.subTest(fmt=fmt, degraded=False):
                response = self.respond(fmt, ALLOW, (DEGRADED_MSG,), degraded=False)
                self.assertEqual((response.code, response.stderr), (0, ""))

    def test_R004_22_degraded_deny_is_a_normal_deny(self):
        reason = "agentkit guard error (x): writes to test files are refused until the guard is fixed"
        for fmt in FORMAT_NAMES:
            with self.subTest(fmt=fmt):
                response = self.respond(fmt, DENY, (reason,), degraded=True)
                self.assertEqual(response.code, 0)
                self.assertEqual(verdict_of(fmt, response.code, response.stdout), DENY)
                if fmt in CLAUDE_SHAPED:
                    self.assertEqual(json.loads(response.stdout), pre_tool(DENY, reason))

    def test_R004_22_normal_allow_writes_nothing_to_stderr(self):
        for fmt in FORMAT_NAMES:
            with self.subTest(fmt=fmt):
                self.assertEqual(self.respond(fmt, ALLOW, ()).stderr, "")


class GuardCommandTests(HookCase):
    """`agentkit guard --format F` end to end, on 003's repository with a frozen file."""

    def guard(self, fmt: str, tool: str, tool_input: dict) -> tuple[int, str, str]:
        return self.hook("guard", "--format", fmt, stdin=self.payload(fmt, tool, tool_input))

    def edit_tool(self, fmt: str) -> tuple[str, str]:
        return ("edit", "filePath") if fmt in PLUGINS else ("Edit", "file_path")

    def test_R004_10_allowed_edit_is_silent_for_claude(self):
        code, out, err = self.guard("claude", "Edit", {"file_path": "app/src/main/Foo.kt"})
        self.assertEqual((code, out.strip()), (0, ""))
        self.assertNotIn(DEGRADED, err)

    def test_R004_11_frozen_edit_is_denied_for_claude(self):
        code, out, _ = self.guard("claude", "Edit", {"file_path": FROZEN})
        self.assertEqual(code, 0)
        hso = json.loads(out)["hookSpecificOutput"]
        self.assertEqual((hso["hookEventName"], hso["permissionDecision"]), ("PreToolUse", DENY))
        self.assertTrue(hso["permissionDecisionReason"].startswith("agentkit: "))
        self.assertIn(FROZEN, hso["permissionDecisionReason"])

    def test_R004_11_ask_for_claude(self):
        code, out, _ = self.guard("claude", "Write", {"file_path": ".claude/settings.json"})
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], ASK)

    def test_R004_12_ask_becomes_deny_for_codex_and_dsh(self):
        for fmt in ("codex", "dsh"):
            with self.subTest(fmt=fmt):
                code, out, _ = self.guard(fmt, "Write", {"file_path": ".claude/settings.json"})
                self.assertEqual(code, 0)
                hso = json.loads(out)["hookSpecificOutput"]
                self.assertEqual(hso["permissionDecision"], DENY)
                self.assertIn(ASK_PREFIX, hso["permissionDecisionReason"])

    def test_R004_12_shell_write_denied_and_read_allowed_for_codex(self):
        code, out, _ = self.guard("codex", "Bash", {"command": f"echo x > {FROZEN}"})
        self.assertEqual((code, verdict_of("codex", code, out)), (0, DENY))
        code, out, _ = self.guard("codex", "Bash", {"command": f"cat {FROZEN}"})
        self.assertEqual((code, out.strip()), (0, ""))

    def test_R004_13_plugin_protocol_end_to_end(self):
        for fmt in PLUGINS:
            with self.subTest(fmt=fmt):
                code, out, _ = self.guard(fmt, "edit", {"filePath": FROZEN})
                self.assertEqual((code, json.loads(out)["decision"]), (0, DENY))
                code, out, _ = self.guard(fmt, "edit", {"filePath": "app/src/main/Foo.kt"})
                self.assertEqual(code, 0)
                self.assertEqual(set(json.loads(out)), {"decision", "reason"})
                self.assertEqual(json.loads(out)["decision"], ALLOW)

    def test_R004_14_plugin_ask_end_to_end(self):
        args = {"filePath": ".claude/settings.json"}
        code, out, _ = self.guard("pi", "write", args)
        self.assertEqual((code, json.loads(out)["decision"]), (0, ASK))
        code, out, _ = self.guard("opencode", "write", args)
        self.assertEqual((code, json.loads(out)["decision"]), (0, DENY))
        self.assertIn(ASK_PREFIX, json.loads(out)["reason"])

    def test_R004_13_relative_paths_resolve_against_payload_cwd(self):
        stdin = json.dumps({"tool": "edit", "args": {"filePath": "test/FooTest.kt"},
                            "cwd": str(self.root / "app" / "src")})
        code, out, _ = self.hook("guard", "--format", "pi", stdin=stdin)
        self.assertEqual((code, json.loads(out)["decision"]), (0, DENY))

    def test_R004_22_degraded_allow_end_to_end(self):
        self.break_config()
        for fmt in FORMAT_NAMES:
            with self.subTest(fmt=fmt):
                tool, key = self.edit_tool(fmt)
                code, out, err = self.guard(fmt, tool, {key: "app/src/main/Foo.kt"})
                self.assertEqual(code, 1)
                self.assertIn(ALLOWING, err)
                if fmt in PLUGINS:
                    self.assertEqual(json.loads(out)["decision"], ALLOW)
                else:
                    self.assertEqual(out.strip(), "")

    def test_R004_22_degraded_deny_end_to_end(self):
        self.break_config()
        for fmt in FORMAT_NAMES:
            with self.subTest(fmt=fmt):
                tool, key = self.edit_tool(fmt)
                code, out, _ = self.guard(fmt, tool, {key: "tests.lock.json"})
                self.assertEqual((code, verdict_of(fmt, code, out)), (0, DENY))


if __name__ == "__main__":
    unittest.main()
