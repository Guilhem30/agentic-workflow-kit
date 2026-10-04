"""Fixtures for the install, update and sync tests of spec 010: a fixture kit (a copy of the
kit's package, profiles, workflow and skills, plus fake git hooks, CI files and adapter docs),
a CLI runner that runs that kit's own package, fake adapters, and file snapshots.
IDs of other specs are built with rid()."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from unittest import mock

import agentkit
from tests.support import TempDirTestCase, _rmtree, run_cli

KIT = Path(agentkit.__file__).resolve().parent.parent
FIXTURE_VERSION = "9.9.9-fixture"
KIT_DIRS = ("agentkit", "profiles", "workflow", "skills", "adapters", "githooks", "ci")

BEGIN = "<!-- agentkit:begin (managed by agentkit; edit outside this block) -->"
END = "<!-- agentkit:end -->"

PRE_COMMIT_V1 = "#!/bin/sh\n# fixture pre-commit, version 1\nexit 0\n"
PRE_COMMIT_V2 = "#!/bin/sh\n# fixture pre-commit, version 2\nexit 0\n"
COMMIT_MSG = "#!/bin/sh\n# fixture commit-msg\nexit 0\n"
GITHUB_CI = ("on: [push, pull_request]\n# base: ${{ github.base_ref }}\n"
             "# run: python .agentkit/bin/agentkit test\n")
GITLAB_CI = "agentkit:\n  script:\n    - python .agentkit/bin/agentkit test  # $CI_COMMIT_SHA\n"

FIRST_INSTALL = ("--ci", "none", "--models", "tool")

FAKE_ADAPTERS_MODULE = '''"""Fixture stand-in for the adapter generators of 012 to 016."""


def kit_files(name, cfg, src, ctx):
    return []


def derived_files(name, cfg, ctx):
    return []


def post_install_notes(name):
    return [name + ": fixture note from the kit copy"]
'''


def build_kit(dest: Path, version: str = FIXTURE_VERSION, fake_adapters: bool = False) -> Path:
    """A kit at dest: the real package, profiles, workflow and skills, with fake git hooks,
    CI files and adapter docs, a stray __pycache__, and its own version string. With
    fake_adapters, its agentkit/adapters.py is replaced by FAKE_ADAPTERS_MODULE."""
    for name in ("agentkit", "profiles", "workflow", "skills"):
        shutil.copytree(KIT / name, dest / name, ignore=shutil.ignore_patterns("__pycache__"))
    cli = dest / "agentkit" / "cli.py"
    text = cli.read_text(encoding="utf-8")
    text, n = re.subn(r'^VERSION = ".*"$', f'VERSION = "{version}"', text, flags=re.M)
    assert n == 1, "fixture kit: VERSION line not found in agentkit/cli.py"
    cli.write_bytes(text.encode("utf-8"))
    files = {"githooks/pre-commit": PRE_COMMIT_V1, "githooks/commit-msg": COMMIT_MSG,
             "ci/github-actions.yml": GITHUB_CI, "ci/gitlab-ci.yml": GITLAB_CI,
             "adapters/README.md": "# Fixture adapters\n"}
    for rel, content in files.items():
        p = dest / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content.encode("utf-8"))
    if fake_adapters:
        (dest / "agentkit" / "adapters.py").write_bytes(FAKE_ADAPTERS_MODULE.encode("utf-8"))
    stray = dest / "agentkit" / "__pycache__" / "stray.cpython-311.pyc"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_bytes(b"not bytecode")
    return dest


def kit_files(kit: Path, name: str) -> dict[str, bytes]:
    """{relative path: bytes} of kit/name, without __pycache__."""
    base = kit / name
    return {p.relative_to(base).as_posix(): p.read_bytes() for p in sorted(base.rglob("*"))
            if p.is_file() and "__pycache__" not in p.relative_to(base).parts}


def snapshot(root: Path) -> dict[str, tuple[bytes, int]]:
    """{relative path: (bytes, mtime_ns)} of every file under root, .git excluded."""
    out = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if p.is_file() and rel.parts[0] != ".git":
            out[rel.as_posix()] = (p.read_bytes(), p.stat().st_mtime_ns)
    return out


def age_files(root: Path, when: int = 1_000_000_000) -> None:
    """Set every file's mtime under root (.git excluded) to a fixed past time."""
    for p in root.rglob("*"):
        if p.is_file() and p.relative_to(root).parts[0] != ".git":
            os.utime(p, (when, when))


def block_region(text: str, begin: str = BEGIN, end: str = END) -> str:
    """The text strictly between the begin and end marker lines."""
    lines = text.splitlines(keepends=True)
    starts = [i for i, l in enumerate(lines) if l.rstrip("\r\n").startswith(begin)]
    ends = [i for i, l in enumerate(lines) if l.rstrip("\r\n").startswith(end)]
    assert len(starts) == 1 and len(ends) == 1 and starts[0] < ends[0], text
    return "".join(lines[starts[0] + 1:ends[0]])


def manifest_entry(manifest, path: str):
    """The mapping recorded for path anywhere in the manifest, or None."""
    if isinstance(manifest, dict):
        if isinstance(manifest.get(path), dict):
            return manifest[path]
        for value in manifest.values():
            found = manifest_entry(value, path)
            if found is not None:
                return found
    elif isinstance(manifest, list):
        for value in manifest:
            if isinstance(value, dict) and value.get("path") == path:
                return value
            found = manifest_entry(value, path)
            if found is not None:
                return found
    return None


def all_strings(data) -> list[str]:
    if isinstance(data, str):
        return [data]
    if isinstance(data, dict):
        return [s for k, v in data.items() for s in all_strings(k) + all_strings(v)]
    if isinstance(data, list):
        return [s for v in data for s in all_strings(v)]
    return []


class FakeAdapters:
    """Stands in for the adapter generators of 012 to 016. claude-code derives
    .claude/skills/<name>/SKILL.md from each skill in <paths.skills>."""

    def __init__(self):
        self.kit = {}            # adapter name -> list of Planned
        self.kit_calls: list[str] = []
        self.derived_calls: list[str] = []

    def kit_files(self, name, cfg, src, ctx):
        self.kit_calls.append(name)
        return list(self.kit.get(name, []))

    def derived_files(self, name, cfg, ctx):
        from agentkit.install import Planned
        self.derived_calls.append(name)
        if name != "claude-code":
            return []
        skills = cfg.root / cfg.path("skills")
        out = []
        for d in sorted(skills.iterdir()) if skills.is_dir() else []:
            source = d / "SKILL.md"
            if source.is_file():
                out.append(Planned(path=f".claude/skills/{d.name}/SKILL.md", mode="derived",
                                   content=b"<!-- generated -->\n" + source.read_bytes()))
        return out

    def post_install_notes(self, name):
        return [f"{name}: fixture note, trust the hooks with /hooks"]


class InstallCase(TempDirTestCase):
    """A fixture kit shared by the class (self.kit unless a test builds its own)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._kit_tmp = Path(tempfile.mkdtemp(prefix="agentkit-kit-")).resolve()
        cls.shared_kit = build_kit(cls._kit_tmp / "kit")

    @classmethod
    def tearDownClass(cls):
        _rmtree(cls._kit_tmp)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        os.environ["GIT_CEILING_DIRECTORIES"] = str(self.tmp)
        self.kit = self.shared_kit
        self.target = self.tmp / "repo"
        self.target.mkdir()

    def own_kit(self, name: str = "kit2", version: str = FIXTURE_VERSION,
                fake_adapters: bool = False) -> Path:
        """A fixture kit this test may change."""
        return build_kit(self.tmp / name, version, fake_adapters)

    # running the fixture kit's own CLI ----------------------------------------------------
    def kit_cli(self, *args: str, kit: Path | None = None, cwd: Path | None = None
                ) -> tuple[int, str]:
        kit = kit or self.kit
        cwd = cwd or self.tmp / "elsewhere"
        cwd.mkdir(exist_ok=True)
        env = dict(os.environ)
        env["PYTHONPATH"] = str(kit)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run([sys.executable, "-m", "agentkit", *args], cwd=cwd, env=env,
                              capture_output=True, text=True, encoding="utf-8", timeout=300)
        return proc.returncode, proc.stdout + proc.stderr

    def cli_install(self, *args: str, target: Path | None = None, kit: Path | None = None,
                    expect: int | None = 0) -> str:
        code, out = self.kit_cli("install", "--target", str(target or self.target), *args,
                                 kit=kit)
        if expect is not None:
            self.assertEqual(code, expect, out)
        return out

    def run_launcher(self, root: Path, *args: str, cwd: Path | None = None) -> tuple[int, str]:
        cwd = cwd or self.tmp / "elsewhere"
        cwd.mkdir(exist_ok=True)
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run([sys.executable, str(root / ".agentkit" / "bin" / "agentkit"),
                               *args], cwd=cwd, env=env, capture_output=True, text=True,
                              encoding="utf-8", timeout=120)
        return proc.returncode, proc.stdout + proc.stderr

    # in-process API, with fake adapters ---------------------------------------------------
    def write_config(self, root: Path | None = None, adapters: str = "[]", models: str = "tool",
                     providers: str = "[]", oses: str = "[]", kit_extra: str = "",
                     rest: str = "") -> Path:
        root = root or self.target
        return self.write(root / "agentkit.toml",
                          f'# fixture config, kept by install\n[kit]\nprofile = "generic"\n'
                          f"adapters = {adapters}\n{kit_extra}\n"
                          f"[ci]\nproviders = {providers}\nos = {oses}\n\n"
                          f'[models]\nmode = "{models}"\n\n{rest}')

    def fake_adapters(self) -> FakeAdapters:
        """Patch the adapter dispatch (agentkit.adapters, and any copy in agentkit.install)."""
        import agentkit.adapters as adapters_mod
        import agentkit.install as install_mod
        fake = FakeAdapters()
        for name in ("kit_files", "derived_files", "post_install_notes"):
            for mod in (adapters_mod, install_mod):
                if mod is adapters_mod or hasattr(mod, name):
                    patcher = mock.patch.object(mod, name, getattr(fake, name))
                    patcher.start()
                    self.addCleanup(patcher.stop)
        return fake

    def api_install(self, root: Path | None = None, kit: Path | None = None, **kw):
        from agentkit import install as install_mod
        return install_mod.install(root or self.target, src=kit or self.kit, **kw)

    def cli_in(self, root: Path, *args: str) -> tuple[int, str]:
        """Run agentkit in-process from root (fake adapters stay in effect)."""
        os.chdir(root)
        return run_cli(*args)

    # reading results ----------------------------------------------------------------------
    def toml(self, root: Path | None = None) -> dict:
        return tomllib.loads((root or self.target).joinpath("agentkit.toml")
                             .read_text(encoding="utf-8"))

    def manifest(self, root: Path | None = None) -> dict:
        return json.loads((root or self.target).joinpath(".agentkit", "manifest.json")
                          .read_text(encoding="utf-8"))

    def text(self, rel: str, root: Path | None = None) -> str:
        return (root or self.target).joinpath(rel).read_text(encoding="utf-8")

    def files_with_bytes(self, data: bytes, root: Path | None = None) -> list[str]:
        """Files under root, outside .agentkit/ and .git/, whose bytes are exactly data."""
        root = root or self.target
        return [rel for rel, (content, _) in snapshot(root).items()
                if content == data and not rel.startswith(".agentkit/")]

    def assertEmptyDir(self, path: Path):
        self.assertEqual(sorted(p.name for p in path.iterdir()), [])

    @staticmethod
    def sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
