"""Spec 010: install options, config, the installed copy, launchers, hooksPath, CODEOWNERS,
.gitignore, idempotence and the summary (R010-01 to R010-11, R010-21 to R010-25)."""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import unittest

from agentkit import config
from agentkit.install import Planned
from tests.install_fixtures import (FIRST_INSTALL, FIXTURE_VERSION, KIT_DIRS, InstallCase,
                                    age_files, build_kit, kit_files, snapshot)

DEFAULT_PYTHON = "python" if os.name == "nt" else "python3"


class TestOptions(InstallCase):
    def test_R010_01_installs_into_existing_target(self):
        out = self.cli_install(*FIRST_INSTALL)
        for rel in ("agentkit.toml", "AGENTS.md", ".agentkit/bin/agentkit",
                    ".agentkit/manifest.json"):
            with self.subTest(file=rel):
                self.assertTrue((self.target / rel).is_file(), out)
        self.assertEmptyDir(self.tmp / "elsewhere")

    def test_R010_01_target_must_exist(self):
        missing = self.tmp / "missing"
        code, out = self.kit_cli("install", "--target", str(missing), *FIRST_INSTALL)
        self.assertEqual(code, 2, out)
        self.assertFalse(missing.exists())

    def test_R010_02_unknown_values_exit_2_and_write_nothing(self):
        cases = {"adapter": ("--adapters", "claude-code,bogus-tool"),
                 "profile": ("--profile", "bogus-profile"),
                 "ci provider": ("--ci", "github,bogus-ci"),
                 "ci os": ("--ci-os", "linux,bogus-os")}
        for what, (flag, value) in cases.items():
            with self.subTest(what=what):
                args = {"--ci": "github", "--ci-os": "linux", "--models": "tool"}
                args[flag] = value
                flat = [x for kv in args.items() for x in kv]
                code, out = self.kit_cli("install", "--target", str(self.target), *flat)
                self.assertEqual(code, 2, out)
                self.assertIn(value.split(",")[-1], out)
                self.assertEmptyDir(self.target)

    def test_R010_02_known_adapters(self):
        fake = self.fake_adapters()
        self.write_config()
        self.api_install(adapters=["claude-code", "codex", "opencode", "deepseek-harness", "pi"])
        self.assertEqual(set(self.toml()["kit"]["adapters"]),
                         {"claude-code", "codex", "opencode", "deepseek-harness", "pi"})
        self.assertEqual(set(fake.kit_calls),
                         {"claude-code", "codex", "opencode", "deepseek-harness", "pi"})

    def test_R010_01_adapters_option_is_a_comma_list(self):
        kit = self.own_kit(fake_adapters=True)
        out = self.cli_install("--adapters", "deepseek-harness,claude-code", *FIRST_INSTALL,
                               kit=kit)
        self.assertEqual(set(self.toml()["kit"]["adapters"]),
                         {"deepseek-harness", "codex", "claude-code"})
        self.assertIn("claude-code: fixture note from the kit copy", out)

    def test_R010_08_ci_files_rendered_for_chosen_providers(self):
        from tests.install_fixtures import GITHUB_CI, GITLAB_CI
        self.cli_install("--ci", "github,gitlab", "--ci-os", "linux", "--models", "tool")
        self.assertEqual(len(self.files_with_bytes(GITHUB_CI.encode())), 1)
        self.assertEqual(len(self.files_with_bytes(GITLAB_CI.encode())), 1)

    def test_R010_02_missing_kit_source_exits_2_and_writes_nothing(self):
        kit = self.own_kit()
        (kit / "githooks" / "commit-msg").unlink()
        code, out = self.kit_cli("install", "--target", str(self.target), *FIRST_INSTALL,
                                 kit=kit)
        self.assertEqual(code, 2, out)
        self.assertIn("commit-msg", out)
        self.assertEmptyDir(self.target)

    def test_R010_03_renders_config_from_options(self):
        self.cli_install("--profile", "generic", "--ci", "github,gitlab",
                         "--ci-os", "linux,macos", "--models", "kit", "--python", "py -3.12")
        data = self.toml()
        self.assertEqual(data["kit"]["profile"], "generic")
        self.assertEqual(data["kit"]["python"], "py -3.12")
        self.assertEqual(data["ci"]["providers"], ["github", "gitlab"])
        self.assertEqual(data["ci"]["os"], ["linux", "macos"])
        self.assertEqual(data["models"]["mode"], "kit")
        self.assertIs(data["chaos"]["enabled"], False)  # from the template
        self.assertIn("`py -3.12 .agentkit/bin/agentkit test`", self.text("AGENTS.md"))

    def test_R010_03_defaults(self):
        self.cli_install("--ci", "none", "--models", "tool")
        data = self.toml()
        self.assertEqual(data["kit"]["profile"], "generic")
        self.assertEqual(data["ci"]["providers"], [])
        self.assertEqual(data["models"]["mode"], "tool")
        self.assertIn(f"`{DEFAULT_PYTHON} .agentkit/bin/agentkit test`", self.text("AGENTS.md"))

    def test_R010_23_first_install_requires_ci(self):
        code, out = self.kit_cli("install", "--target", str(self.target), "--models", "tool")
        self.assertEqual(code, 2, out)
        self.assertIn("--ci", out)
        self.assertIn("--ci-os", out)
        self.assertEmptyDir(self.target)

    def test_R010_23_first_install_requires_ci_os_unless_none(self):
        code, out = self.kit_cli("install", "--target", str(self.target), "--ci", "github",
                                 "--models", "tool")
        self.assertEqual(code, 2, out)
        self.assertIn("--ci-os", out)
        self.assertEmptyDir(self.target)
        self.cli_install("--ci", "none", "--models", "tool")
        self.assertEqual(self.toml()["ci"]["providers"], [])

    def test_R010_25_first_install_requires_models(self):
        code, out = self.kit_cli("install", "--target", str(self.target), "--ci", "none")
        self.assertEqual(code, 2, out)
        self.assertIn(config.MODELS_HELP.strip("\n"), out)
        self.assertEmptyDir(self.target)

    def test_R010_25_models_replaces_stored_mode(self):
        self.cli_install(*FIRST_INSTALL)
        self.cli_install()
        self.assertEqual(self.toml()["models"]["mode"], "tool")
        self.cli_install("--models", "kit")
        self.assertEqual(self.toml()["models"]["mode"], "kit")

    def test_R010_24_ci_options_replace_stored_values(self):
        self.cli_install("--ci", "github", "--ci-os", "linux", "--models", "tool")
        self.cli_install()
        self.assertEqual(self.toml()["ci"]["providers"], ["github"])
        self.assertEqual(self.toml()["ci"]["os"], ["linux"])
        self.cli_install("--ci", "gitlab", "--ci-os", "windows,macos")
        self.assertEqual(self.toml()["ci"]["providers"], ["gitlab"])
        self.assertEqual(self.toml()["ci"]["os"], ["windows", "macos"])


class TestExistingConfig(InstallCase):
    def test_R010_04_existing_config_kept(self):
        self.fake_adapters()
        cfg = self.write_config(adapters='["claude-code"]', rest="[budgets]\nagents_md = 99\n")
        before = cfg.read_bytes()
        self.api_install()
        self.assertEqual(cfg.read_bytes(), before)

    def test_R010_04_new_adapters_added(self):
        self.fake_adapters()
        cfg = self.write_config(adapters='["claude-code"]', rest="[budgets]\nagents_md = 99\n")
        self.api_install(adapters=["opencode"])
        data = self.toml()
        self.assertEqual(sorted(data["kit"]["adapters"]), ["claude-code", "opencode"])
        self.assertEqual(data["budgets"], {"agents_md": 99})
        self.assertIn("# fixture config, kept by install", cfg.read_text(encoding="utf-8"))

    def test_R010_05_deepseek_selects_codex(self):
        fake = self.fake_adapters()
        self.write_config()
        self.api_install(adapters=["deepseek-harness"])
        self.assertEqual(sorted(self.toml()["kit"]["adapters"]), ["codex", "deepseek-harness"])
        self.assertIn("codex", fake.kit_calls)


class TestInstalledCopy(InstallCase):
    def test_R010_06_copies_kit_dirs_without_pycache(self):
        self.write(self.target / ".agentkit" / "workflow" / "stale-from-old-kit.md")
        self.cli_install(*FIRST_INSTALL)
        for name in KIT_DIRS:
            with self.subTest(dir=name):
                self.assertEqual(kit_files(self.target / ".agentkit", name),
                                 kit_files(self.kit, name))
        pycache = [p for p in (self.target / ".agentkit").rglob("__pycache__")]
        self.assertEqual(pycache, [])
        self.assertFalse((self.target / ".agentkit/workflow/stale-from-old-kit.md").exists())
        self.assertIn("do not edit", self.text(".agentkit/README.md").lower())

    def test_R010_06_self_hosted_copies_nothing(self):
        root = build_kit(self.tmp / "selfkit", version="7.7.7-self")
        self.cli_install(*FIRST_INSTALL, "--self", target=root, kit=root)
        for name in KIT_DIRS:
            with self.subTest(dir=name):
                self.assertFalse((root / ".agentkit" / name).exists())
        self.assertTrue(self.toml(root)["kit"].get("self_hosted"))

    def test_R010_07_launcher_runs_installed_copy(self):
        self.cli_install(*FIRST_INSTALL)
        launcher = self.target / ".agentkit" / "bin" / "agentkit"
        first = launcher.read_text(encoding="utf-8").splitlines()[0]
        self.assertTrue(first.startswith("#!") and "python3" in first, first)
        self.assertTrue((self.target / ".agentkit" / "bin" / "agentkit.cmd").is_file())
        code, out = self.run_launcher(self.target, "version")
        self.assertEqual(code, 0, out)
        self.assertIn(FIXTURE_VERSION, out)

    def test_R010_07_launcher_sets_root(self):
        self.cli_install(*FIRST_INSTALL)
        code, out = self.run_launcher(self.target, "models")  # needs agentkit.toml
        self.assertEqual(code, 0, out)

    @unittest.skipIf(os.name == "nt", "no executable bit on Windows")
    def test_R010_07_launcher_is_executable(self):
        self.cli_install(*FIRST_INSTALL)
        mode = (self.target / ".agentkit" / "bin" / "agentkit").stat().st_mode
        self.assertTrue(mode & stat.S_IXUSR)

    @unittest.skipUnless(os.name == "nt", "cmd launcher")
    def test_R010_07_cmd_launcher_runs(self):
        self.cli_install(*FIRST_INSTALL)
        cmd = self.target / ".agentkit" / "bin" / "agentkit.cmd"
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
        proc = subprocess.run(["cmd", "/c", str(cmd), "version"], cwd=self.tmp,
                              capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn(FIXTURE_VERSION, proc.stdout)

    def test_R010_07_self_hosted_launcher_uses_root_package(self):
        root = build_kit(self.tmp / "selfkit", version="7.7.7-self")
        self.cli_install(*FIRST_INSTALL, "--self", target=root, kit=root)
        code, out = self.run_launcher(root, "version")
        self.assertEqual(code, 0, out)
        self.assertIn("7.7.7-self", out)


class TestPlannedFiles(InstallCase):
    def test_R010_08_writes_kit_files_then_syncs(self):
        fake = self.fake_adapters()
        fake.kit["claude-code"] = [Planned(path=".fixture/claude.json", content=b"{}\n",
                                           mode="managed")]
        self.write_config(adapters='["claude-code"]', kit_extra='python = "py -3.12"\n')
        self.api_install()
        skills = sorted(p.name for p in (self.kit / "skills").iterdir() if p.is_dir())
        for name in skills:
            with self.subTest(skill=name):
                text = self.text(f".agents/skills/{name}/SKILL.md")
                self.assertNotIn("{{python}}", text)
                self.assertTrue((self.target / f".claude/skills/{name}/SKILL.md").is_file())
        with_python = [n for n in skills
                       if "{{python}}" in (self.kit / "skills" / n / "SKILL.md").read_text(
                           encoding="utf-8")]
        self.assertTrue(with_python)
        for name in with_python:
            with self.subTest(python_in=name):
                self.assertIn("py -3.12 .agentkit/bin/agentkit",
                              self.text(f".agents/skills/{name}/SKILL.md"))
        for rel in ("AGENTS.md", "specs/README.md", "tests.lock.json", "tests.unfreeze-log.md",
                    ".githooks/pre-commit", ".githooks/commit-msg"):
            with self.subTest(file=rel):
                self.assertTrue((self.target / rel).is_file())
        self.assertEqual((self.target / ".fixture/claude.json").read_bytes(), b"{}\n")

    def test_R010_08_uses_configured_paths(self):
        self.fake_adapters()
        self.write_config(rest='[paths]\nspecs = "work/specs"\nlock = "work/frozen.lock.json"\n'
                               'unfreeze_log = "work/unfreeze.md"\nskills = "work/skills"\n')
        self.api_install()
        for rel in ("work/specs/README.md", "work/frozen.lock.json", "work/unfreeze.md",
                    "work/skills/spec/SKILL.md"):
            with self.subTest(file=rel):
                self.assertTrue((self.target / rel).is_file())
        for rel in ("specs", "tests.lock.json", "tests.unfreeze-log.md", ".agents"):
            with self.subTest(absent=rel):
                self.assertFalse((self.target / rel).exists())

    def test_R010_08_once_files_kept(self):
        self.fake_adapters()
        self.write_config()
        mine = self.write(self.target / "specs" / "README.md", "# My spec index\n")
        self.api_install()
        self.assertEqual(mine.read_text(encoding="utf-8"), "# My spec index\n")


class TestGitAndOwners(InstallCase):
    def test_R010_09_sets_hooks_path_in_git_repo(self):
        self.fake_adapters()
        self.init_git(self.target)
        self.write_config()
        self.api_install()
        self.assertEqual(self.git("config", "--get", "core.hooksPath", cwd=self.target),
                         ".githooks")

    def test_R010_09_note_outside_git(self):
        out = self.cli_install(*FIRST_INSTALL)
        self.assertIn("core.hooksPath", out)

    def owners(self) -> dict[str, set[str]]:
        lines = self.text(".github/CODEOWNERS").splitlines()
        begin = [i for i, l in enumerate(lines) if l.startswith("# agentkit:begin")]
        end = [i for i, l in enumerate(lines) if l.startswith("# agentkit:end")]
        self.assertTrue(begin and end, lines)
        out: dict[str, set[str]] = {}
        for line in lines[begin[0] + 1:end[0]]:
            parts = line.split()
            if parts and not parts[0].startswith("#"):
                out.setdefault(parts[0].lstrip("/"), set()).update(parts[1:])
        return out

    def assertOwned(self, owners: dict, path: str, who: str):
        candidates = [path] + ([path + "**"] if path.endswith("/") else [])
        self.assertTrue(any(who in owners.get(c, ()) for c in candidates),
                        f"{path} not owned by {who}: {owners}")

    def test_R010_10_codeowners_block(self):
        self.fake_adapters()
        self.write_config(rest='[paths]\nspecs = "work/specs"\nlock = "work/frozen.lock.json"\n'
                               'unfreeze_log = "work/unfreeze.md"\n\n'
                               '[chaos]\nlog = "audit/chaos.jsonl"\n\n'
                               '[profile]\nfrozen_globs = ["spec/**", "**/fixtures/**"]\n')
        self.api_install(owner="@alice")
        owners = self.owners()
        for path in ("work/frozen.lock.json", "work/unfreeze.md", ".agentkit/", ".githooks/",
                     "spec/**", "**/fixtures/**", "audit/chaos.jsonl", "work/specs/*/reviews/"):
            with self.subTest(path=path):
                self.assertOwned(owners, path, "@alice")

    def test_R010_10_default_chaos_log(self):
        self.fake_adapters()
        self.write_config()
        self.api_install(owner="@alice")
        self.assertOwned(self.owners(), "chaos-log.jsonl", "@alice")

    def test_R010_10_owner_stored_and_replaced(self):
        self.fake_adapters()
        self.write_config()
        self.api_install(owner="@alice")
        self.assertEqual(self.toml()["kit"]["owner"], "@alice")
        self.api_install(owner="@bob")
        self.assertEqual(self.toml()["kit"]["owner"], "@bob")
        owners = self.owners()
        self.assertOwned(owners, ".githooks/", "@bob")
        self.assertFalse(any("@alice" in who for who in owners.values()), owners)

    def test_R010_10_update_rebuilds_block_from_stored_owner(self):
        from agentkit import install as install_mod
        self.fake_adapters()
        cfg = self.write_config()
        self.api_install(owner="@alice")
        with open(cfg, "a", encoding="utf-8", newline="\n") as f:
            f.write('[profile]\nfrozen_globs = ["spec/**"]\n')
        install_mod.update(self.target, self.kit)
        owners = self.owners()
        self.assertOwned(owners, "spec/**", "@alice")
        self.assertOwned(owners, ".githooks/", "@alice")

    def test_R010_10_no_owner_no_codeowners(self):
        self.fake_adapters()
        self.write_config()
        self.api_install()
        self.assertFalse((self.target / ".github" / "CODEOWNERS").exists())

    def test_R010_11_gitignore_block(self):
        self.fake_adapters()
        self.write_config()
        self.write(self.target / ".gitignore", "node_modules/\n")
        self.api_install()
        lines = self.text(".gitignore").splitlines()
        self.assertEqual(lines[0], "node_modules/")
        begin = [i for i, l in enumerate(lines) if l.startswith("# agentkit:begin")]
        end = [i for i, l in enumerate(lines) if l.startswith("# agentkit:end")]
        self.assertTrue(begin and end, lines)
        block = [l.strip() for l in lines[begin[0] + 1:end[0]]]
        for entry in (".agentkit/state/", "__pycache__/", "*.agentkit-new", ".autopilot/"):
            with self.subTest(entry=entry):
                self.assertIn(entry, block)


class TestIdempotenceAndSummary(InstallCase):
    def test_R010_21_second_install_writes_nothing(self):
        self.cli_install("--ci", "github", "--ci-os", "linux", "--models", "kit",
                         "--owner", "@alice")
        age_files(self.target)
        before = snapshot(self.target)
        self.cli_install("--ci", "github", "--ci-os", "linux", "--models", "kit",
                         "--owner", "@alice")
        self.assertEqual(snapshot(self.target), before)

    def test_R010_21_second_install_with_adapters_writes_nothing(self):
        self.fake_adapters()
        self.write_config(adapters='["claude-code"]')
        self.api_install(owner="@alice")
        age_files(self.target)
        before = snapshot(self.target)
        report = self.api_install(owner="@alice")
        self.assertEqual(snapshot(self.target), before)
        self.assertEqual(report.written, [])

    def test_R010_22_summary_lists_written_files(self):
        out = self.cli_install(*FIRST_INSTALL)
        self.assertIn("AGENTS.md", out)
        self.assertIn(".githooks/pre-commit", out)

    def test_R010_22_summary_lists_conflicts_skips_removals_and_notes(self):
        self.fake_adapters()
        self.write_config(adapters='["claude-code"]')
        self.api_install()
        self.write(self.target / ".githooks" / "pre-commit", "#!/bin/sh\n# mine\n")
        (self.target / ".githooks" / "commit-msg").unlink()
        shutil.rmtree(self.target / ".agents" / "skills" / "handoff")
        code, out = self.cli_in(self.target, "update", "--kit", str(self.kit))
        self.assertEqual(code, 1, out)
        self.assertIn(".githooks/pre-commit", out)                 # conflict
        self.assertIn(".githooks/commit-msg", out)                 # skipped
        self.assertIn(".claude/skills/handoff/SKILL.md", out)      # removed
        self.assertIn("claude-code: fixture note, trust the hooks with /hooks", out)

    def test_R010_22_report_categories(self):
        from agentkit import install as install_mod
        self.fake_adapters()
        self.write_config(adapters='["claude-code"]')
        self.api_install()
        self.write(self.target / ".githooks" / "pre-commit", "#!/bin/sh\n# mine\n")
        (self.target / ".githooks" / "commit-msg").unlink()
        shutil.rmtree(self.target / ".agents" / "skills" / "handoff")
        report = install_mod.update(self.target, self.kit)
        self.assertIn(".githooks/pre-commit", report.conflicts)
        self.assertIn(".githooks/commit-msg", report.skipped)
        self.assertIn(".claude/skills/handoff/SKILL.md", report.removed)
        note = "claude-code: fixture note, trust the hooks with /hooks"
        self.assertIn(note, report.notes)
        summary = "\n".join(report.lines())
        for item in (".githooks/pre-commit", ".githooks/commit-msg",
                     ".claude/skills/handoff/SKILL.md", note):
            with self.subTest(item=item):
                self.assertIn(item, summary)


if __name__ == "__main__":
    unittest.main()
