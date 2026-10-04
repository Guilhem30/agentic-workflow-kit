"""Spec 000: both invocation forms (R000-04), the exit-code convention (R000-08) and failing
items with a one-line hint (R000-09)."""
from __future__ import annotations

import os
import unittest

from tests.process_fixtures import COMMANDS, NO_SUCH_OPTION, run_launcher, run_module
from tests.support import FIXTURE_PROFILE, RepoTestCase, TempDirTestCase, rid, run_cli

PROFILE = (FIXTURE_PROFILE
           + 'test_globs = ["tests/**/*.py"]\nsource_globs = ["src/**/*.py"]\n'
           + "\n[codemap]\nsymbol_regexes = ['^def (?P<name>\\w+)']\n")

INVALID = "invalid choice"


def hint_lines(out: str) -> list[str]:
    return [line for line in out.splitlines() if line.startswith("hint: ") and line[6:].strip()]


class CommandRegistrationTests(TempDirTestCase):
    """A name the CLI does not know is an invalid choice; every contract command is known.
    The unknown option makes argparse stop before any command runs."""

    def setUp(self) -> None:
        super().setUp()
        os.chdir(self.tmp)

    def test_R000_04_control_unknown_command_is_an_invalid_choice(self):
        code, out = run_cli("no-such-command", NO_SUCH_OPTION)
        self.assertEqual(code, 2)
        self.assertIn(INVALID, out)

    def test_R000_04_every_contract_command_is_registered(self):
        for command in COMMANDS:
            with self.subTest(command=command):
                code, out = run_cli(command, NO_SUCH_OPTION)
                self.assertNotIn(INVALID, out)
                self.assertEqual(code, 2, out)


class ModuleFormTests(TempDirTestCase):
    """`python -m agentkit <command>` with the kit repo on the path."""

    def setUp(self) -> None:
        super().setUp()
        self.root = self.project("proj")
        os.chdir(self.root)

    def test_R000_04_module_form_runs_version(self):
        proc = run_module(self.root, "version")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        code, out = run_cli("version")
        self.assertEqual(code, 0)
        self.assertEqual(proc.stdout, out)
        self.assertTrue(proc.stdout.startswith("agentkit "), proc.stdout)

    def test_R000_04_module_form_knows_every_command(self):
        for command in COMMANDS:
            with self.subTest(command=command):
                proc = run_module(self.root, command, NO_SUCH_OPTION)
                self.assertNotIn(INVALID, proc.stderr + proc.stdout)
                self.assertEqual(proc.returncode, 2)

    def test_R000_04_module_form_matches_in_process_results(self):
        self.write("specs/050-fixture/spec.md",
                   '---\nid: "050"\ntitle: Fixture\nstatus: draft\n---\n\n# 050\n', base=self.root)
        for argv in (("trace",), ("spec-status", "999", "tests-draft"), ("models",)):
            with self.subTest(argv=argv):
                proc = run_module(self.root, *argv)
                code, out = run_cli(*argv)
                self.assertEqual(proc.returncode, code)
                self.assertEqual(sorted((proc.stdout + proc.stderr).splitlines()),
                                 sorted(out.splitlines()))


class InstalledLauncherTests(TempDirTestCase):
    """`python .agentkit/bin/agentkit <command>` in a project installed by `agentkit install`."""

    def setUp(self) -> None:
        super().setUp()
        self.target = self.tmp / "installed"
        self.target.mkdir()
        os.chdir(self.tmp)
        code, out = run_cli("install", "--target", str(self.target), "--ci", "none",
                            "--models", "tool")
        self.assertEqual(code, 0, out)
        os.chdir(self.target)

    def test_R000_04_launcher_exists(self):
        self.assertTrue((self.target / ".agentkit" / "bin" / "agentkit").is_file())

    def test_R000_04_launcher_runs_version_without_pythonpath(self):
        proc = run_launcher(self.target, "version")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, run_cli("version")[1])

    def test_R000_04_launcher_knows_every_command(self):
        for command in COMMANDS:
            with self.subTest(command=command):
                proc = run_launcher(self.target, command, NO_SUCH_OPTION)
                self.assertNotIn(INVALID, proc.stderr + proc.stdout)
                self.assertEqual(proc.returncode, 2)

    def test_R000_04_both_forms_give_the_same_result(self):
        for argv in (("status",), ("lock", "verify"), ("trace",), ("models",),
                     ("spec-status", "999", "tests-draft")):
            with self.subTest(argv=argv):
                installed = run_launcher(self.target, *argv)
                module = run_module(self.target, *argv)
                self.assertEqual(installed.returncode, module.returncode)
                if argv[0] != "spec-status":  # a fresh install passes these
                    self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
                self.assertEqual(installed.stdout, module.stdout)
                self.assertEqual(installed.stderr, module.stderr)

    def test_R000_04_launcher_uses_the_installed_root_from_a_subdirectory(self):
        sub = self.target / "deep" / "er"
        sub.mkdir(parents=True)
        from_sub = run_launcher(self.target, "lock", "verify", cwd=sub)
        from_root = run_launcher(self.target, "lock", "verify")
        self.assertEqual(from_sub.returncode, from_root.returncode)
        self.assertEqual(from_sub.stdout, from_root.stdout)


class CheckProject(RepoTestCase):
    """A git project whose checks all pass: one frozen test, a traced requirement of spec 050
    and an up-to-date code map."""

    def setUp(self) -> None:
        super().setUp()
        self.write(".agentkit/profiles/fixture.toml", PROFILE)
        self.write("src/mod.py", "def hello():\n    return 1\n")
        self.write("tests/test_050_x.py", f"def test_{rid('050', '01', '_')}():\n    pass\n")
        self.write("specs/050-fixture/spec.md",
                   '---\nid: "050"\ntitle: Fixture\nstatus: tests-draft\n---\n\n'
                   f"- **{rid('050', '01')}** The fixture shall work.\n")
        self.write_lock({"tests/test_050_x.py": "050"})
        self.assertEqual(run_cli("codemap")[0], 0)
        self.commit_all()


class ExitCodeTests(CheckProject):

    def test_R000_08_success_exits_0(self):
        for argv in (("version",), ("models",), ("status",), ("trace",),
                     ("trace", "--spec", "050"), ("lock", "verify"), ("lock", "status"),
                     ("lock", "audit"), ("verify",), ("codemap", "--check"),
                     ("lint-instructions",), ("spec-status", "050", "tests-draft")):
            with self.subTest(argv=argv):
                code, out = run_cli(*argv)
                self.assertEqual(code, 0, out)

    def test_R000_08_failed_check_exits_1(self):
        self.write("tests/test_050_x.py", "changed\n")
        self.write("src/other.py", "def added():\n    pass\n")
        self.write("specs/050-fixture/spec.md",
                   '---\nid: "050"\ntitle: Fixture\nstatus: tests-draft\n---\n\n'
                   f"- **{rid('050', '01')}** The fixture shall work.\n"
                   f"- **{rid('050', '02')}** The fixture shall also work.\n")
        self.write("AGENTS.md", "".join(f"line {i}\n" for i in range(400)))
        for argv in (("lock", "verify"), ("lock", "status"), ("verify",),
                     ("codemap", "--check"), ("lint-instructions",),
                     ("trace", "--spec", "050"), ("spec-status", "999", "tests-draft")):
            with self.subTest(argv=argv):
                code, out = run_cli(*argv)
                self.assertEqual(code, 1, out)

    def test_R000_08_usage_error_exits_2(self):
        cases = [(), ("no-such-command",), ("lock",), ("chaos",), ("spec-status",),
                 ("spec-status", "050"), ("handoff",), ("new-spec",),
                 ("new-spec", "050", "a", "b"), ("lock", "freeze"), ("lock", "unfreeze"),
                 ("guard",), ("trace", "--spec"), ("test", "a", "b"), ("check-commit-msg",)]
        cases += [(command, NO_SUCH_OPTION) for command in COMMANDS]
        for argv in cases:
            with self.subTest(argv=argv):
                code, out = run_cli(*argv)
                self.assertEqual(code, 2, out)


# Commands that read agentkit.toml; their specs leave the config-error code at 2.
CONFIG_COMMANDS = (("models",), ("status",), ("trace",), ("lock", "verify"), ("lock", "status"),
                   ("lock", "audit"), ("verify",), ("codemap", "--check"), ("lint-instructions",),
                   ("test",), ("handoff", "050"), ("spec-status", "050", "tests-draft"),
                   ("new-spec", "slug"), ("chaos", "log"), ("update",), ("sync", "--check"),
                   ("pre-commit",), ("autopilot", "050"))


class ConfigErrorTests(TempDirTestCase):

    def test_R000_08_missing_config_exits_2(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        os.chdir(empty)
        for argv in CONFIG_COMMANDS:
            with self.subTest(argv=argv):
                code, out = run_cli(*argv)
                self.assertEqual(code, 2, out)
        self.assertEqual(list(empty.iterdir()), [])

    def test_R000_08_malformed_config_exits_2(self):
        root = self.tmp / "bad"
        self.write(root / "agentkit.toml", "[kit\nprofile = \n")
        os.chdir(root)
        for argv in CONFIG_COMMANDS:
            with self.subTest(argv=argv):
                code, out = run_cli(*argv)
                self.assertEqual(code, 2, out)

    def test_R000_08_unknown_profile_exits_2(self):
        root = self.project("unknown", kit='profile = "no-such-profile"', profile_name="")
        os.chdir(root)
        for argv in CONFIG_COMMANDS:
            with self.subTest(argv=argv):
                code, out = run_cli(*argv)
                self.assertEqual(code, 2, out)


class FailingCheckOutputTests(CheckProject):
    """Each failing check names what failed, outside its one `hint: ` line."""

    def check(self, argv, items):
        code, out = run_cli(*argv)
        self.assertEqual(code, 1, out)
        hints = hint_lines(out)
        self.assertEqual(len(hints), 1, out)
        rest = "\n".join(line for line in out.splitlines() if line not in hints)
        for item in items:
            self.assertIn(item, rest)

    def test_R000_09_lock_verify(self):
        self.write("tests/test_050_x.py", "changed\n")
        self.git("add", "-A")
        for argv in (("lock", "verify"), ("lock", "verify", "--staged"), ("lock", "status"),
                     ("verify",)):
            with self.subTest(argv=argv):
                self.check(argv, ["tests/test_050_x.py"])

    def test_R000_09_codemap_check(self):
        self.write("src/other.py", "def added():\n    pass\n")
        self.check(("codemap", "--check"), ["other.py"])

    def test_R000_09_lint_instructions(self):
        self.write("AGENTS.md", "".join(f"line {i}\n" for i in range(400)))
        self.check(("lint-instructions",), ["AGENTS.md"])

    def test_R000_09_trace(self):
        self.write("specs/050-fixture/spec.md",
                   '---\nid: "050"\ntitle: Fixture\nstatus: tests-draft\n---\n\n'
                   f"- **{rid('050', '01')}** The fixture shall work.\n"
                   f"- **{rid('050', '02')}** The fixture shall also work.\n")
        for argv in (("trace",), ("trace", "--spec", "050")):
            with self.subTest(argv=argv):
                self.check(argv, [rid("050", "02")])
