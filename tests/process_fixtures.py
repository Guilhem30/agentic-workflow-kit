"""Fixtures for the cross-cutting tests of spec 000: the kit's source tree, the command list
of the CLI contract, and running agentkit in a child Python process.

IDs of other specs are built with support.rid()."""
from __future__ import annotations

import ast
import io
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import agentkit

KIT_ROOT = Path(agentkit.__file__).resolve().parents[1]
PACKAGE = KIT_ROOT / "agentkit"

# Every top-level command named by the Public API contract of spec 000.
COMMANDS = ("install", "update", "sync", "lock", "guard", "verify", "status", "handoff",
            "trace", "new-spec", "spec-status", "test", "codemap", "lint-instructions",
            "models", "pre-commit", "check-commit-msg", "chaos", "autopilot", "version")

NO_SUCH_OPTION = "--agentkit-test-no-such-option"

PY = f'"{sys.executable}"'

# A small Write payload in the claude dialect, for the hook commands.
CLAUDE_WRITE = ('{"hook_event_name": "PreToolUse", "tool_name": "Write", '
                '"tool_input": {"file_path": "notes.txt", "content": "x"}}')


def package_sources() -> list[Path]:
    """Every Python file of the agentkit package, payloads included."""
    return sorted(p for p in PACKAGE.rglob("*.py") if "__pycache__" not in p.parts)


def tooling_sources() -> list[Path]:
    """Every Python file the kit ships to run: the package plus the scripts under adapters/
    (copied into .agentkit/adapters by install, run by the agent tools)."""
    scripts = (KIT_ROOT / "adapters").rglob("*.py") if (KIT_ROOT / "adapters").is_dir() else []
    return package_sources() + sorted(p for p in scripts if "__pycache__" not in p.parts)


def parse(path: Path, feature_version: tuple[int, int] | None = None) -> ast.Module:
    source = path.read_text(encoding="utf-8")
    if feature_version is None:
        return ast.parse(source, filename=str(path))
    return ast.parse(source, filename=str(path), feature_version=feature_version)


def imported_modules(tree: ast.Module) -> list[tuple[str, int]]:
    """(dotted module name, line) for every absolute import, `from x import y` giving both
    `x` and `x.y`, and every importlib.import_module / __import__ call with a literal name."""
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.module, node.lineno))
            found.extend((f"{node.module}.{alias.name}", node.lineno) for alias in node.names)
        elif isinstance(node, ast.Call) and node.args:
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            first = node.args[0]
            if (name in ("import_module", "__import__") and isinstance(first, ast.Constant)
                    and isinstance(first.value, str) and not first.value.startswith(".")):
                found.append((first.value, node.lineno))
    return found


def clean_env(**extra: str | None) -> dict[str, str]:
    """os.environ (already cleaned by TempDirTestCase) without Python variables that change
    imports or encodings, plus `extra` (None removes a name)."""
    env = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME", "PYTHONUTF8", "PYTHONIOENCODING", "PYTHONSTARTUP",
                 "PYTHONSAFEPATH", "PYTHONWARNINGS"):
        env.pop(name, None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for name, value in extra.items():
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    return env


def run_python(argv: list[str], cwd: Path, env: dict[str, str],
               stdin: str = "") -> subprocess.CompletedProcess:
    """Run `python <argv>`; stdout and stderr are decoded as UTF-8 with LF endings."""
    proc = subprocess.run([sys.executable, *argv], cwd=cwd, env=env, capture_output=True,
                          input=stdin.encode("utf-8"), timeout=300)
    out = proc.stdout.decode("utf-8", "replace").replace("\r\n", "\n")
    err = proc.stderr.decode("utf-8", "replace").replace("\r\n", "\n")
    return subprocess.CompletedProcess(proc.args, proc.returncode, out, err)


def run_module(cwd: Path, *args: str, env: dict[str, str] | None = None,
               python_flags: tuple[str, ...] = ()) -> subprocess.CompletedProcess:
    """`python -m agentkit <args>` from the kit repo (the package found through PYTHONPATH)."""
    env = clean_env(PYTHONPATH=str(KIT_ROOT)) if env is None else env
    return run_python([*python_flags, "-m", "agentkit", *args], cwd, env)


def run_launcher(root: Path, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """`python .agentkit/bin/agentkit <args>` in an installed project (from `cwd`, default its
    root), without PYTHONPATH."""
    return run_python([str(root / ".agentkit" / "bin" / "agentkit"), *args], cwd or root,
                      clean_env())


def stdin_patch(text: str):
    return mock.patch("sys.stdin", io.TextIOWrapper(io.BytesIO(text.encode("utf-8")),
                                                     encoding="utf-8"))


def written_files(root: Path, before: dict[str, bytes] | None = None) -> dict[str, bytes]:
    """{posix path: bytes} for every file under root outside .git, skipping those whose bytes
    equal `before[path]` (files the command did not write)."""
    files: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if ".git" in rel.parts or "__pycache__" in rel.parts or not path.is_file():
            continue
        data = path.read_bytes()
        key = rel.as_posix()
        if before is not None and before.get(key) == data:
            continue
        files[key] = data
    return files
