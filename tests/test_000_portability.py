"""Spec 000: standard library only on CPython 3.11+ (R000-01), the kit's CI on three operating
systems (R000-02) and no network access (R000-03)."""
from __future__ import annotations

import socket
import subprocess
import sys
import tomllib
import unittest
from unittest import mock

from tests.process_fixtures import (CLAUDE_WRITE, COMMANDS, KIT_ROOT, PY, clean_env,
                                    imported_modules, package_sources, parse, run_python, tooling_sources,
                                    stdin_patch)
from tests.support import FIXTURE_PROFILE, RepoTestCase, run_cli

ALLOWED_TOP = set(sys.stdlib_module_names) | {"agentkit", "__future__"}

NETWORK_MODULES = ("socket", "ssl", "http", "urllib.request", "urllib.response", "ftplib",
                   "smtplib", "poplib", "imaplib", "nntplib", "telnetlib", "xmlrpc",
                   "socketserver", "webbrowser")

GIT_NETWORK = {"fetch", "pull", "push", "clone", "ls-remote", "submodule", "lfs"}
NETWORK_PROGRAMS = {"curl", "wget", "ssh", "scp", "nc", "pip", "pip3"}

# Imports every module of the package with site-packages disabled, then runs one command.
IMPORT_ALL = r"""
import importlib, pkgutil, sys
sys.path.insert(0, sys.argv[1])
import agentkit
names = [m.name for m in pkgutil.walk_packages(agentkit.__path__, "agentkit.")
         if m.name != "agentkit.__main__"]  # importing it would run the CLI
for name in names:
    importlib.import_module(name)
assert sys.flags.no_site and "site" not in sys.modules, "site was imported"
assert not [p for p in sys.path if "site-packages" in p or "dist-packages" in p], sys.path
print(len(names))
from agentkit.cli import main
sys.exit(main(["version"]))
"""


class StandardLibraryOnlyTests(unittest.TestCase):

    def test_R000_01_package_has_sources(self):
        names = {p.relative_to(KIT_ROOT).as_posix() for p in package_sources()}
        self.assertIn("agentkit/cli.py", names)
        self.assertIn("agentkit/__main__.py", names)

    def test_R000_01_imports_only_the_standard_library(self):
        bad = []
        for path in tooling_sources():
            for name, line in imported_modules(parse(path)):
                if name.split(".")[0] not in ALLOWED_TOP:
                    bad.append(f"{path.relative_to(KIT_ROOT).as_posix()}:{line}: {name}")
        self.assertEqual(bad, [])

    def test_R000_01_syntax_is_python_3_11(self):
        bad = []
        for path in tooling_sources():
            try:
                parse(path, feature_version=(3, 11))
            except SyntaxError as exc:
                bad.append(f"{path.relative_to(KIT_ROOT).as_posix()}:{exc.lineno}: {exc.msg}")
        self.assertEqual(bad, [])

    def test_R000_01_every_module_imports_without_site_packages(self):
        # -I: no PYTHONPATH, no user site, no script directory; -S: no site-packages at all.
        proc = run_python(["-I", "-S", "-c", IMPORT_ALL, str(KIT_ROOT)], KIT_ROOT, clean_env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        count, version = proc.stdout.splitlines()[:2]
        self.assertEqual(int(count), len(package_sources()) - 2)  # without __init__, __main__
        self.assertTrue(version.startswith("agentkit "), proc.stdout)


class KitCiTests(unittest.TestCase):

    def test_R000_02_kit_ci_runs_on_linux_windows_and_macos(self):
        data = tomllib.loads((KIT_ROOT / "agentkit.toml").read_text(encoding="utf-8"))
        ci = data.get("ci", {})
        self.assertLessEqual({"linux", "windows", "macos"}, set(ci.get("os", [])))
        providers = ci.get("providers", [])
        self.assertTrue(providers)
        self.assertNotIn("none", providers)


class NoNetworkSourceTests(unittest.TestCase):

    def test_R000_03_no_network_module_is_imported(self):
        bad = []
        for path in tooling_sources():
            for name, line in imported_modules(parse(path)):
                if any(name == m or name.startswith(m + ".") for m in NETWORK_MODULES):
                    bad.append(f"{path.relative_to(KIT_ROOT).as_posix()}:{line}: {name}")
        self.assertEqual(bad, [])


class _Blocked(OSError):
    pass


class NoNetworkAtRunTimeTests(RepoTestCase):
    """Every command runs with sockets blocked and child processes recorded."""

    def setUp(self) -> None:
        super().setUp()
        self.write(".agentkit/profiles/fixture.toml",
                   FIXTURE_PROFILE
                   + 'test_globs = ["tests/**/*.py"]\nsource_globs = ["src/**/*.py"]\n'
                   + f"test_cmd = '{PY} -c \"print(1)\"'\n"
                   + f"test_one_cmd = '{PY} -c \"print(1)\"'\n"
                   + "\n[codemap]\nsymbol_regexes = ['^def (?P<name>\\w+)']\n")
        self.write("src/mod.py", "def hello():\n    return 1\n")
        self.write("tests/test_050_x.py", "import unittest\n")
        self.write_spec("050", "tests-draft")
        self.write("msg.txt", "fix: a message\n")
        self.other = self.tmp / "other"
        self.other.mkdir()
        self.commit_all()
        self.attempts: list[str] = []
        self.children: list[list[str]] = []

    def _block(self, what):
        def blocked(*args, **kwargs):
            self.attempts.append(f"{what}{args[1:] if what.startswith('socket.') else args}")
            raise _Blocked(f"network blocked by the test: {what}")
        return blocked

    def _recording_popen(self):
        real = subprocess.Popen
        children = self.children

        class Recording(real):
            def __init__(self, args, *rest, **kwargs):
                if isinstance(args, (str, bytes)):
                    argv = [args if isinstance(args, str) else args.decode()]
                else:
                    argv = [str(a) for a in args]
                children.append(argv)
                super().__init__(args, *rest, **kwargs)
        return Recording

    def _network_child(self, argv: list[str]) -> bool:
        words = " ".join(argv).replace('"', " ").replace("'", " ").split()
        names = [w.replace("\\", "/").rsplit("/", 1)[-1].lower() for w in words]
        names = [n[:-4] if n.endswith(".exe") else n for n in names]
        if any(n in NETWORK_PROGRAMS for n in names):
            return True
        for i, n in enumerate(names):
            if n != "git":
                continue
            rest = names[i + 1:]
            while rest and rest[0].startswith("-"):  # global options; -C and -c take a value
                rest = rest[2:] if rest[0] in ("-c", "-C") else rest[1:]
            if rest and rest[0] in GIT_NETWORK:
                return True
            if rest[:2] == ["remote", "update"]:
                return True
        return False

    def test_R000_03_commands_open_no_connection(self):
        commands = [
            ("version",), ("models",), ("status",), ("trace",), ("trace", "--spec", "050"),
            ("lock", "status"), ("lock", "verify"), ("lock", "freeze", "tests/test_050_x.py"),
            ("lock", "verify", "--staged"), ("lock", "restore"), ("lock", "audit"),
            ("new-spec", "051", "second"), ("spec-status", "051", "tests-draft"),
            ("handoff", "050", "--note", "n"), ("codemap",), ("codemap", "--check"),
            ("lint-instructions",), ("test",), ("test", "tests.test_050_x"),
            ("guard", "--format", "claude"), ("verify", "--format", "claude"),
            ("status", "--format", "claude"), ("verify",),
            ("chaos", "log"), ("chaos", "audit"), ("chaos", "approve", "050", "approved"),
            ("install", "--target", str(self.other), "--ci", "none", "--models", "tool"),
            ("update",), ("sync", "--check"), ("sync",), ("pre-commit",),
            ("check-commit-msg", "msg.txt"), ("autopilot", "050"),
        ]
        patches = [
            mock.patch.object(socket.socket, "connect", self._block("socket.connect")),
            mock.patch.object(socket.socket, "connect_ex", self._block("socket.connect_ex")),
            mock.patch.object(socket.socket, "sendto", self._block("socket.sendto")),
            mock.patch.object(socket, "create_connection", self._block("create_connection")),
            mock.patch.object(socket, "getaddrinfo", self._block("getaddrinfo")),
            mock.patch.object(socket, "gethostbyname", self._block("gethostbyname")),
            mock.patch.object(subprocess, "Popen", self._recording_popen()),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.assertEqual({c[0] for c in commands}, set(COMMANDS))
        for argv in commands:
            with self.subTest(argv=argv):
                self.attempts.clear()
                self.children.clear()
                with stdin_patch(CLAUDE_WRITE if "--format" in argv else ""):
                    run_cli(*argv)
                self.assertEqual(self.attempts, [])
                self.assertEqual([c for c in self.children if self._network_child(c)], [])


if __name__ == "__main__":
    unittest.main()
