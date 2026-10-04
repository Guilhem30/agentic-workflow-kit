"""Spec 004: recorded payloads per tool, fed to `guard` (R004-21)."""
from __future__ import annotations

import json
from pathlib import Path

from tests.hook_fixtures import ALLOW, DEGRADED, DENY, FORMAT_NAMES, HookCase, verdict_of

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "payloads"
REQUIRED = {"allowed-edit", "denied-frozen-edit", "denied-shell-write", "allowed-readonly-shell"}


def load(tool: str) -> list[tuple[str, dict]]:
    out = []
    for path in sorted((FIXTURES / tool).glob("*.json")):
        out.append((path.name, json.loads(path.read_text(encoding="utf-8"))))
    return out


class ConformanceTests(HookCase):

    def test_R004_21_every_tool_has_the_required_fixtures(self):
        for tool in FORMAT_NAMES:
            with self.subTest(tool=tool):
                fixtures = load(tool)
                for name, data in fixtures:
                    self.assertEqual(data["req"], "R004-21", name)
                    self.assertIn(data["expected"], (ALLOW, DENY), name)
                    self.assertIsInstance(data["payload"], dict, name)
                covers = {data["covers"] for _, data in fixtures}
                required = REQUIRED | ({"apply-patch-frozen"} if tool == "codex" else set())
                self.assertLessEqual(required, covers)

    def test_R004_21_codex_apply_patch_fixture_is_an_apply_patch(self):
        patches = [d for _, d in load("codex") if d["covers"] == "apply-patch-frozen"]
        self.assertTrue(patches)
        for data in patches:
            self.assertEqual(data["payload"]["tool_name"], "apply_patch")
            self.assertIn("*** Begin Patch", data["payload"]["tool_input"]["command"])

    def test_R004_21_fixtures_give_their_expected_verdict(self):
        for tool in FORMAT_NAMES:
            for name, data in load(tool):
                with self.subTest(tool=tool, fixture=name):
                    payload = dict(data["payload"], cwd=str(self.root))
                    code, out, err = self.hook("guard", "--format", tool,
                                               stdin=json.dumps(payload))
                    self.assertEqual(code, 0, err)
                    self.assertNotIn(DEGRADED, err)
                    self.assertEqual(verdict_of(tool, code, out), data["expected"])


if __name__ == "__main__":
    import unittest
    unittest.main()
