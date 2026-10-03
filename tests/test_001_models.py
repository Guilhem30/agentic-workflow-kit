"""Spec 001: model routing (tiers, modes, `agentkit models`)."""
from __future__ import annotations

import os
import re

from agentkit import config
from agentkit.config import ConfigError, load_config
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

    def test_R001_19_absent_mode_means_tool(self):
        root = self.project("p", kit='profile = "fixture"\nadapters = ["claude-code"]')
        self.assertEqual(load_config(root=root).models("claude-code"), {})

    def test_R001_19_invalid_mode(self):
        root = self.project("p", kit='profile = "fixture"\nadapters = ["claude-code"]',
                            rest='[models]\nmode = "auto"\n')
        with self.assertRaises(ConfigError) as ctx:
            load_config(root=root)
        self.assertIn("models.mode", str(ctx.exception))
        os.chdir(root)
        code, out = run_cli("models")
        self.assertEqual(code, 2)
        self.assertIn("models.mode", out)

    def test_R001_21_models_help_text(self):
        lines = config.MODELS_HELP.strip("\n").splitlines()
        self.assertLessEqual(len(lines), 8)
        self.assertTrue(any("kit" in l and "recommended" in l.lower() for l in lines))
        self.assertTrue(any(re.search(r"\btool\b", l) for l in lines))

    def test_R001_21_install_help_prints_it(self):
        os.chdir(self.tmp)
        _, out = run_cli("install", "--help")
        self.assertIn(config.MODELS_HELP.strip("\n"), out)

    def test_R001_21_missing_models_option_prints_it(self):
        target = self.tmp / "fresh"
        target.mkdir()
        os.chdir(target)
        _, out = run_cli("install")
        self.assertIn(config.MODELS_HELP.strip("\n"), out)

    def test_R001_22_models_command_kit_mode(self):
        root, _ = self.cfg_for("kit", adapters='["claude-code", "opencode"]')
        os.chdir(root)
        code, out = run_cli("models")
        self.assertEqual(code, 0)
        self.assert_lines_in_order(out, [
            "claude-code: mode kit",
            "  strong: opus (effort high)",
            "  standard: sonnet (effort medium)",
            "  fast: haiku (effort low)",
            "opencode: mode kit",
            "  strong: decided by the tool",
            "  standard: decided by the tool",
            "  fast: decided by the tool",
        ])

    def test_R001_22_models_command_tool_mode(self):
        root, _ = self.cfg_for("tool", adapters='["claude-code"]')
        os.chdir(root)
        code, out = run_cli("models")
        self.assertEqual(code, 0)
        self.assert_lines_in_order(out, ["claude-code: mode tool"]
                                   + [f"  {t}: decided by the tool" for t in TIERS])
        self.assertNotIn("opus", out.lower())

    def assert_lines_in_order(self, out: str, expected: list[str]):
        lines = [l.rstrip() for l in out.splitlines()]
        start = lines.index(expected[0]) if expected[0] in lines else -1
        self.assertGreaterEqual(start, 0, f"missing line {expected[0]!r} in:\n{out}")
        self.assertEqual(lines[start:start + len(expected)], expected)

    def test_R001_23_override_table_in_kit_mode(self):
        _, cfg = self.cfg_for("kit", rest='[models.claude-code]\nfast = "sonnet"\n')
        self.assertEqual(cfg.models("claude-code"),
                         {"strong": "opus", "standard": "sonnet", "fast": "sonnet"})

    def test_R001_23_override_for_adapter_without_map(self):
        _, cfg = self.cfg_for("kit", adapters='["opencode"]',
                              rest='[models.opencode]\nstrong = "local-big"\n')
        self.assertEqual(cfg.models("opencode"), {"strong": "local-big"})

    def test_R001_23_override_table_ignored_in_tool_mode(self):
        _, cfg = self.cfg_for("tool", rest='[models.claude-code]\nfast = "sonnet"\n')
        self.assertEqual(cfg.models("claude-code"), {})
