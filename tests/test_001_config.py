"""Spec 001: locating the configuration, settings, profiles."""
from __future__ import annotations

import os
import re

from agentkit.config import ConfigError, find_root, load_config, load_profile
from tests.support import TempDirTestCase, rid, run_cli


class LocatingTests(TempDirTestCase):

    def test_R001_01_agentkit_root_env_wins_over_cwd_search(self):
        a = self.project("a")
        b = self.project("b")
        os.chdir(b)
        os.environ["AGENTKIT_ROOT"] = str(a)
        self.assertEqual(load_config().root.resolve(), a)

    def test_R001_01_agentkit_root_without_config_falls_back_to_search(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        b = self.project("b")
        os.chdir(b)
        os.environ["AGENTKIT_ROOT"] = str(empty)
        self.assertEqual(load_config().root.resolve(), b)

    def test_R001_02_search_upward_from_start(self):
        root = self.project("proj")
        deep = root / "src" / "a" / "b"
        deep.mkdir(parents=True)
        self.assertEqual(find_root(deep).resolve(), root)
        self.assertEqual(load_config(start=deep).root.resolve(), root)

    def test_R001_02_nearest_config_wins(self):
        outer = self.project("outer")
        inner = self.project(outer / "inner")
        deep = inner / "x"
        deep.mkdir()
        self.assertEqual(find_root(deep).resolve(), inner)

    def test_R001_02_search_from_cwd_by_default(self):
        root = self.project("proj")
        sub = root / "sub"
        sub.mkdir()
        os.chdir(sub)
        self.assertEqual(load_config().root.resolve(), root)

    def test_R001_03_no_config_found(self):
        nowhere = self.tmp / "nowhere"
        nowhere.mkdir()
        self.assertIsNone(find_root(nowhere))
        with self.assertRaises(ConfigError):
            load_config(start=nowhere)

    def test_R001_03_command_exits_2_suggesting_install(self):
        nowhere = self.tmp / "nowhere"
        nowhere.mkdir()
        os.chdir(nowhere)
        code, out = run_cli("models")
        self.assertEqual(code, 2)
        self.assertIn("agentkit install", out)

    def test_R001_03_version_works_without_config(self):
        nowhere = self.tmp / "nowhere"
        nowhere.mkdir()
        os.chdir(nowhere)
        code, _ = run_cli("version")
        self.assertEqual(code, 0)

    def test_R001_04_invalid_toml_names_file_and_position(self):
        root = self.tmp / "bad"
        self.write(root / "agentkit.toml", '[kit]\nprofile = "fixture"\nbroken = \n')
        with self.assertRaises(ConfigError) as ctx:
            load_config(root=root)
        msg = str(ctx.exception)
        self.assertIn("agentkit.toml", msg)
        self.assertIn("line 3", msg)
        self.assertIn("column", msg)

    def test_R001_04_invalid_toml_command_exits_2(self):
        root = self.tmp / "bad"
        self.write(root / "agentkit.toml", "[kit\n")
        os.chdir(root)
        code, out = run_cli("models")
        self.assertEqual(code, 2)
        self.assertIn("agentkit.toml", out)


class SettingsTests(TempDirTestCase):

    def test_R001_05_reads_all_tables(self):
        root = self.project("p", kit='version = "1.2.3"\nprofile = "fixture"\n'
                                      'adapters = ["claude-code", "codex"]\n'
                                      'python = "py -3.12"\nself_hosted = true', rest=(
            '[ci]\nproviders = ["github"]\nos = ["linux"]\n\n'
            '[paths]\nspecs = "doc/specs"\n\n'
            '[models]\nmode = "kit"\n\n'
            '[models.claude-code]\nfast = "sonnet"\n\n'
            '[budgets]\nagents_md = 1500\n\n'
            '[guard]\nextra = ["x"]\n\n'
            '[profile]\ntest_cmd = "make test"\n'))
        cfg = load_config(root=root)
        self.assertEqual(cfg.data["kit"]["version"], "1.2.3")
        self.assertEqual(cfg.adapters, ["claude-code", "codex"])
        self.assertEqual(cfg.python_cmd, "py -3.12")
        self.assertIs(cfg.self_hosted, True)
        self.assertEqual(cfg.data["ci"]["providers"], ["github"])
        self.assertEqual(cfg.path("specs"), "doc/specs")
        self.assertEqual(cfg.data["models"]["mode"], "kit")
        self.assertEqual(cfg.data["models"]["claude-code"]["fast"], "sonnet")
        self.assertEqual(cfg.budgets, {"agents_md": 1500})
        self.assertEqual(cfg.guard, {"extra": ["x"]})
        self.assertEqual(cfg.profile["test_cmd"], "make test")

    def test_R001_06_path_defaults(self):
        root = self.project("p")
        cfg = load_config(root=root)
        expected = {"specs": "specs", "lock": "tests.lock.json",
                    "unfreeze_log": "tests.unfreeze-log.md", "codemap": "docs/CODEMAP.md",
                    "skills": ".agents/skills", "roles": "roles"}
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(cfg.path(key), value)
        self.assertEqual(cfg.lock_rel, "tests.lock.json")
        self.assertEqual(cfg.unfreeze_log_rel, "tests.unfreeze-log.md")
        self.assertEqual(cfg.lock_path.resolve(), root / "tests.lock.json")
        self.assertEqual(cfg.unfreeze_log_path.resolve(), root / "tests.unfreeze-log.md")
        self.assertEqual(cfg.specs_dir.resolve(), root / "specs")

    def test_R001_06_explicit_path_overrides_only_its_key(self):
        root = self.project("p", rest='[paths]\nlock = "meta/lock.json"\n')
        cfg = load_config(root=root)
        self.assertEqual(cfg.lock_rel, "meta/lock.json")
        self.assertEqual(cfg.lock_path.resolve(), root / "meta" / "lock.json")
        self.assertEqual(cfg.unfreeze_log_rel, "tests.unfreeze-log.md")

    def test_R001_20_valid_ci_table(self):
        root = self.project("p", rest='[ci]\nproviders = ["github", "gitlab"]\n'
                                      'os = ["linux", "windows", "macos"]\n\n'
                                      '[ci.gitlab_tags]\nlinux = "docker"\nwindows = "win"\n')
        cfg = load_config(root=root)
        self.assertEqual(cfg.data["ci"]["gitlab_tags"], {"linux": "docker", "windows": "win"})

    def test_R001_20_empty_providers_means_no_ci(self):
        root = self.project("p", rest="[ci]\nproviders = []\nos = []\n")
        load_config(root=root)  # must not raise

    def test_R001_20_invalid_values_name_the_key(self):
        cases = {
            "providers": '[ci]\nproviders = ["jenkins"]\nos = ["linux"]\n',
            "os": '[ci]\nproviders = ["github"]\nos = ["freebsd"]\n',
            "gitlab_tags": '[ci]\nproviders = ["gitlab"]\nos = ["linux"]\n\n'
                           '[ci.gitlab_tags]\nsolaris = "x"\n',
        }
        for key, rest in cases.items():
            with self.subTest(key=key):
                root = self.project(f"p-{key}", rest=rest)
                with self.assertRaises(ConfigError) as ctx:
                    load_config(root=root)
                self.assertRegex(str(ctx.exception), rf"\b{key}\b")
                os.chdir(root)
                code, out = run_cli("models")
                self.assertEqual(code, 2)
                self.assertRegex(out, rf"\b{key}\b")

    def test_R001_07_python_default_per_platform(self):
        cfg = load_config(root=self.project("p"))
        self.assertEqual(cfg.python_cmd, "python" if os.name == "nt" else "python3")


class ProfileTests(TempDirTestCase):

    def test_R001_08_dot_agentkit_profiles_first(self):
        root = self.project("p", kit='profile = "mine"', profile_name="")
        self.write(root / ".agentkit/profiles/mine.toml", 'test_cmd = "from-dot-agentkit"\n')
        self.write(root / "profiles/mine.toml", 'test_cmd = "from-profiles"\n')
        self.assertEqual(load_profile("mine", root)["test_cmd"], "from-dot-agentkit")
        self.assertEqual(load_config(root=root).profile["test_cmd"], "from-dot-agentkit")

    def test_R001_08_then_root_profiles(self):
        root = self.project("p", kit='profile = "mine"', profile_name="")
        self.write(root / "profiles/mine.toml", 'test_cmd = "from-profiles"\n')
        self.assertEqual(load_profile("mine", root)["test_cmd"], "from-profiles")

    def test_R001_08_default_profile_is_generic(self):
        root = self.project("p", kit='adapters = []', profile_name="")
        self.write(root / "profiles/generic.toml", 'test_cmd = "generic-marker"\n')
        self.assertEqual(load_config(root=root).profile["test_cmd"], "generic-marker")

    def test_R001_09_missing_profile_lists_searched_dirs(self):
        root = self.project("p", kit='profile = "nope"', profile_name="")
        with self.assertRaises(ConfigError) as ctx:
            load_config(root=root)
        msg = str(ctx.exception).replace("\\", "/")
        self.assertIn(".agentkit/profiles", msg)
        self.assertGreaterEqual(msg.count("profiles"), 3)  # three directories searched

    def test_R001_09_missing_profile_command_exits_2(self):
        root = self.project("p", kit='profile = "nope"', profile_name="")
        os.chdir(root)
        code, out = run_cli("models")
        self.assertEqual(code, 2)
        self.assertIn("nope", out)

    def test_R001_10_profile_defaults(self):
        root = self.project("p", profile_body="")
        prof = load_config(root=root).profile
        expected = {
            "test_cmd": "", "test_cmd_windows": "", "test_one_cmd": "",
            "test_one_cmd_windows": "", "junit_report_glob": [],
            "frozen_globs": ["tests/**", "test/**"], "test_globs": ["tests/**", "test/**"],
            "source_globs": [],
            "build_output_globs": ["**/build/**", "**/dist/**", "**/node_modules/**",
                                   "**/__pycache__/**"],
            "ci_setup": "",
        }
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(prof[key], value)
        for key in ("req_id_regex", "output_filter_regex", "format_cmd", "lint_cmd"):
            with self.subTest(key=key):
                self.assertIn(key, prof)
        self.assertEqual(prof["codemap"]["symbol_regexes"], [])

    def test_R001_10_test_globs_default_follows_frozen_globs(self):
        root = self.project("p", profile_body='frozen_globs = ["spec/**"]\n')
        cfg = load_config(root=root)
        self.assertEqual(cfg.frozen_globs, ["spec/**"])
        self.assertEqual(cfg.test_globs, ["spec/**"])

    def test_R001_11_toml_profile_table_overrides(self):
        root = self.project("p", profile_body='test_cmd = "a"\nlint_cmd = "l"\n',
                            rest='[profile]\ntest_cmd = "b"\n')
        prof = load_config(root=root).profile
        self.assertEqual(prof["test_cmd"], "b")
        self.assertEqual(prof["lint_cmd"], "l")

    def test_R001_11_nested_tables_merge_one_level(self):
        root = self.project("p", profile_body='[codemap]\nsymbol_regexes = ["a"]\nkeep = "yes"\n',
                            rest='[profile.codemap]\nsymbol_regexes = ["b"]\n')
        prof = load_config(root=root).profile
        self.assertEqual(prof["codemap"]["symbol_regexes"], ["b"])
        self.assertEqual(prof["codemap"]["keep"], "yes")

    def test_R001_12_regex_needs_two_groups(self):
        root = self.project("p", rest="[profile]\nreq_id_regex = 'R(\\d{3})'\n")
        with self.assertRaises(ConfigError) as ctx:
            load_config(root=root)
        self.assertIn("req_id_regex", str(ctx.exception))
        os.chdir(root)
        code, out = run_cli("models")
        self.assertEqual(code, 2)
        self.assertIn("req_id_regex", out)

    def test_R001_12_regex_with_two_groups_accepted(self):
        root = self.project("p", rest="[profile]\nreq_id_regex = 'REQ(\\d+)\\.(\\d+)'\n")
        self.assertEqual(load_config(root=root).profile["req_id_regex"], r"REQ(\d+)\.(\d+)")

    def test_R001_13_default_req_id_regex(self):
        regex = re.compile(load_config(root=self.project("p", profile_body="")).profile["req_id_regex"])
        for text in (rid("004", "07"), rid("004", "07", "_"), "test_" + rid("004", "07", "_") + "_x",
                     "see " + rid("004", "07") + ", then"):
            with self.subTest(text=text):
                m = regex.search(text)
                self.assertIsNotNone(m)
                self.assertEqual((m.group(1), m.group(2)), ("004", "07"))
        for text in ("X" + rid("004", "07"), rid("004", "0712")):
            with self.subTest(text=text):
                self.assertIsNone(regex.search(text))
