"""Spec 001: model routing (tiers, modes, `agentkit models`)."""
from __future__ import annotations

import os

from agentkit.config import load_config
from tests.support import TempDirTestCase, run_cli

TIERS = ("strong", "standard", "fast")
CLAUDE_MAP = {"strong": "opus", "standard": "sonnet", "fast": "haiku"}


class ModelTests(TempDirTestCase):

    def cfg_for(self, mode: str, adapters: str = '["claude-code"]', rest: str = ""):
        root = self.project("p", kit=f'profile = "fixture"\nadapters = {adapters}',
                            rest=f'[models]\nmode = "{mode}"\n\n{rest}')
        return root, load_config(root=root)

    def test_R001_17_kit_mode_uses_builtin_map(self):
        _, cfg = self.cfg_for("kit")
        self.assertEqual(cfg.models("claude-code"), CLAUDE_MAP)

    def test_R001_17_tool_mode_resolves_to_nothing(self):
        _, cfg = self.cfg_for("tool")
        self.assertEqual(cfg.models("claude-code"), {})

    def test_R001_17_adapter_without_map_resolves_to_nothing(self):
        _, cfg = self.cfg_for("kit", adapters='["opencode"]')
        self.assertEqual(cfg.models("opencode"), {})

    def test_R001_18_claude_code_map(self):
        _, cfg = self.cfg_for("kit")
        self.assertEqual(cfg.models("claude-code"), CLAUDE_MAP)

    def test_R001_18_codex_has_a_model_per_tier(self):
        _, cfg = self.cfg_for("kit", adapters='["codex"]')
        models = cfg.models("codex")
        for tier in TIERS:
            with self.subTest(tier=tier):
                self.assertIsInstance(models.get(tier), str)
                self.assertTrue(models[tier])

    def test_R001_18_any_provider_tools_have_no_map(self):
        _, cfg = self.cfg_for("kit", adapters='["opencode", "pi", "deepseek-harness"]')
        for adapter in ("opencode", "pi", "deepseek-harness"):
            with self.subTest(adapter=adapter):
                self.assertEqual(cfg.models(adapter), {})

    def test_R001_19_mode_read_from_models_table(self):
        root, cfg = self.cfg_for("kit")
        self.assertEqual(cfg.data["models"]["mode"], "kit")
        self.assertEqual(cfg.models("claude-code")["strong"], "opus")
        os.chdir(root)
        code, out = run_cli("models")
        self.assertEqual(code, 0)
        self.assertIn("kit", out)

    def test_R001_21_install_help_summarises_modes(self):
        os.chdir(self.tmp)
        _, out = run_cli("install", "--help")
        self.assert_mode_summary(out)

    def test_R001_21_missing_models_option_summarises_modes(self):
        target = self.tmp / "fresh"
        target.mkdir()
        os.chdir(target)
        _, out = run_cli("install")
        self.assert_mode_summary(out)

    def assert_mode_summary(self, out: str):
        self.assertIn("--models", out)
        self.assertRegex(out, r"\btool\b")
        recommended = [line for line in out.splitlines() if "recommended" in line.lower()]
        self.assertTrue(recommended, "no line marks a mode as recommended")
        self.assertTrue(any("kit" in line for line in recommended))

    def test_R001_22_models_command_kit_mode(self):
        root, _ = self.cfg_for("kit", adapters='["claude-code", "opencode"]')
        os.chdir(root)
        code, out = run_cli("models")
        self.assertEqual(code, 0)
        self.assertIn("claude-code", out)
        self.assertIn("opencode", out)
        lines = out.splitlines()
        for tier, model, effort in (("strong", "opus", "high"), ("standard", "sonnet", "medium"),
                                    ("fast", "haiku", "low")):
            with self.subTest(tier=tier):
                self.assertTrue(any(tier in l and model in l and effort in l for l in lines),
                                f"no line shows {tier} -> {model} / {effort}")
        self.assertGreaterEqual(out.count("decided by the tool"), 3)  # opencode's three tiers

    def test_R001_22_models_command_tool_mode(self):
        root, _ = self.cfg_for("tool", adapters='["claude-code", "opencode"]')
        os.chdir(root)
        code, out = run_cli("models")
        self.assertEqual(code, 0)
        self.assertIn("tool", out)
        self.assertNotIn("opus", out.lower())
        self.assertGreaterEqual(out.count("decided by the tool"), 6)

    def test_R001_23_override_table_in_kit_mode(self):
        _, cfg = self.cfg_for("kit", rest='[models.claude-code]\nfast = "sonnet"\n')
        self.assertEqual(cfg.models("claude-code"),
                         {"strong": "opus", "standard": "sonnet", "fast": "sonnet"})

    def test_R001_23_override_table_ignored_in_tool_mode(self):
        _, cfg = self.cfg_for("tool", rest='[models.claude-code]\nfast = "sonnet"\n')
        self.assertEqual(cfg.models("claude-code"), {})
