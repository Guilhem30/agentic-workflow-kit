"""Spec 004: the API surface, format selection and stdin payloads (R004-01, R004-02)."""
from __future__ import annotations

import importlib
import json
import unittest
from unittest import mock

import agentkit.payloads as payloads
from agentkit.payloads.base import HookFormat, PluginFormat, Response
from tests.hook_fixtures import (ALLOW, ALLOWING, CLAUDE_SHAPED, DEGRADED, FORMAT_NAMES, PLUGINS,
                                 HookCase)

BAD_PAYLOADS = ("", "   \n", "not json", "{\"tool_name\": ", "[1, 2]", "42", "\"text\"", "null")


class FormatRegistryTests(unittest.TestCase):

    def test_R004_01_formats_has_exactly_the_five_names(self):
        self.assertEqual(set(payloads.FORMATS), set(FORMAT_NAMES))
        for name, fmt in payloads.FORMATS.items():
            with self.subTest(name=name):
                self.assertIsInstance(fmt, HookFormat)
                self.assertEqual(fmt.name, name)

    def test_R004_01_get_format_returns_the_registered_format(self):
        for name in FORMAT_NAMES:
            with self.subTest(name=name):
                self.assertIs(payloads.get_format(name), payloads.FORMATS[name])

    def test_R004_01_each_module_exports_format(self):
        for name in FORMAT_NAMES:
            with self.subTest(name=name):
                module = importlib.import_module(f"agentkit.payloads.{name}")
                self.assertIs(module.FORMAT, payloads.FORMATS[name])

    def test_R004_01_plugin_formats_and_ask_support(self):
        for name in FORMAT_NAMES:
            with self.subTest(name=name):
                self.assertEqual(isinstance(payloads.FORMATS[name], PluginFormat), name in PLUGINS)
        support = {name: payloads.FORMATS[name].supports_ask for name in FORMAT_NAMES}
        self.assertEqual(support, {"claude": True, "codex": False, "dsh": False,
                                   "opencode": False, "pi": True})

    def test_R004_01_response_defaults(self):
        self.assertEqual(Response(), Response(stdout="", stderr="", code=0))


class CommandFormatTests(HookCase):

    def test_R004_01_unknown_format_exits_2(self):
        for command in ("guard", "verify", "status"):
            for fmt in ("bogus", "Claude", "", "opencode-plugin"):
                with self.subTest(command=command, fmt=fmt):
                    code, out, _ = self.hook(command, "--format", fmt, stdin="{}")
                    self.assertEqual(code, 2)
                    self.assertEqual(out, "")

    def test_R004_01_every_format_is_accepted(self):
        patcher = mock.patch("agentkit.status.status_lines", return_value=["status line"])
        patcher.start()
        self.addCleanup(patcher.stop)
        for command in ("guard", "verify", "status"):
            for fmt in FORMAT_NAMES:
                with self.subTest(command=command, fmt=fmt):
                    code, _, err = self.hook(command, "--format", fmt, stdin="{}")
                    self.assertEqual(code, 0, err)

    def test_R004_02_bad_payload_is_a_degraded_allow(self):
        for fmt in FORMAT_NAMES:
            for stdin in BAD_PAYLOADS:
                with self.subTest(fmt=fmt, stdin=stdin):
                    code, out, err = self.hook("guard", "--format", fmt, stdin=stdin)
                    self.assertEqual(code, 1)
                    self.assertIn(ALLOWING + ": ", err)
                    if fmt in PLUGINS:
                        self.assertEqual(json.loads(out)["decision"], ALLOW)
                    else:
                        self.assertEqual(out.strip(), "")

    def test_R004_02_object_without_tool_is_a_normal_allow(self):
        for fmt in FORMAT_NAMES:
            for stdin in ("{}", json.dumps({"cwd": str(self.root)}),
                          json.dumps({"hook_event_name": "PreToolUse", "session_id": "s"})):
                with self.subTest(fmt=fmt, stdin=stdin):
                    code, out, err = self.hook("guard", "--format", fmt, stdin=stdin)
                    self.assertEqual(code, 0)
                    self.assertNotIn(DEGRADED, err)
                    if fmt in PLUGINS:
                        self.assertEqual(json.loads(out)["decision"], ALLOW)
                    else:
                        self.assertEqual(out.strip(), "")

    def test_R004_02_bad_payload_is_empty_for_verify(self):
        self.violate()
        for stdin in BAD_PAYLOADS:
            for fmt in CLAUDE_SHAPED:
                with self.subTest(fmt=fmt, stdin=stdin):
                    code, out, _ = self.hook("verify", "--format", fmt, stdin=stdin)
                    self.assertEqual(code, 0)
                    # {} has no stop_hook_active: the first stop blocks (R004-16).
                    self.assertEqual(json.loads(out)["decision"], "block")

    def test_R004_02_bad_payload_is_empty_for_status(self):
        with mock.patch("agentkit.status.status_lines", return_value=["one"]):
            for stdin in BAD_PAYLOADS:
                with self.subTest(stdin=stdin):
                    code, out, _ = self.hook("status", "--format", "pi", stdin=stdin)
                    self.assertEqual((code, json.loads(out)), (0, {"context": "one"}))


if __name__ == "__main__":
    unittest.main()
