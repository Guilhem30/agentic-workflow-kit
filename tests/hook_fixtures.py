"""Fixtures for the hook-dialect tests of spec 004 (R004-01 to R004-22). This file belongs to
spec 004; IDs of other specs are built with rid().
"""
from __future__ import annotations

import contextlib
import io
import json
from unittest import mock

from agentkit.guard import ALLOW, ASK, DENY, Decision, ReadAction, ShellAction, WriteAction
from tests.guard_fixtures import FROZEN, GuardCase

FORMAT_NAMES = ("claude", "codex", "dsh", "opencode", "pi")
CLAUDE_SHAPED = ("claude", "codex", "dsh")
PLUGINS = ("opencode", "pi")
ALLOWING = "agentkit guard error (allowing)"
DEGRADED = "agentkit guard error"
ASK_PREFIX = "needs the human's approval (ask them to make this change): "
RESTORE_HINT = "agentkit lock restore"

__all__ = ["ALLOW", "ALLOWING", "ASK", "ASK_PREFIX", "CLAUDE_SHAPED", "DEGRADED", "DENY",
           "Decision", "FORMAT_NAMES", "FROZEN", "HookCase", "PLUGINS", "ReadAction",
           "RESTORE_HINT", "ShellAction", "WriteAction", "normalize", "verdict_of"]


def normalize(actions) -> dict:
    """{"write"|"read": set of paths, "shell": set of commands}, ignoring order and empties, so
    that tests do not depend on how paths are split across actions."""
    out: dict[str, set] = {}
    for action in actions:
        if isinstance(action, WriteAction):
            out.setdefault("write", set()).update(action.paths)
        elif isinstance(action, ReadAction):
            out.setdefault("read", set()).update(action.paths)
        elif isinstance(action, ShellAction):
            out.setdefault("shell", set()).add(action.command)
        else:
            raise AssertionError(f"not a neutral action: {action!r}")
    return {k: v for k, v in out.items() if v}


def verdict_of(fmt: str, code: int, stdout: str) -> str:
    """The verdict a tool reads from a pre-tool response (R004-10 to R004-14)."""
    if fmt in PLUGINS:
        return json.loads(stdout)["decision"]
    if not stdout.strip():
        return ALLOW
    return json.loads(stdout)["hookSpecificOutput"]["permissionDecision"]


class HookCase(GuardCase):
    """003's guard repository (app/src/test/FooTest.kt frozen), driven through the CLI."""

    def hook(self, *argv: str, stdin: str = "") -> tuple[int, str, str]:
        """Run agentkit in-process with `stdin`; return (code, stdout, stderr)."""
        from agentkit import cli
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(stdin)), contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            try:
                code = cli.main(list(argv))
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        return code, out.getvalue(), err.getvalue()

    def claude_payload(self, tool: str, tool_input: dict, **extra) -> str:
        return json.dumps({"tool_name": tool, "tool_input": tool_input, "cwd": str(self.root),
                           **extra})

    def plugin_payload(self, tool: str, args: dict) -> str:
        return json.dumps({"tool": tool, "args": args, "cwd": str(self.root)})

    def payload(self, fmt: str, tool: str, tool_input: dict) -> str:
        if fmt in PLUGINS:
            return self.plugin_payload(tool, tool_input)
        return self.claude_payload(tool, tool_input)

    def break_config(self) -> None:
        """A syntax error in agentkit.toml: the guard runs degraded (R004-22)."""
        self.write("agentkit.toml", "[kit\nprofile = \n")

    def violate(self) -> None:
        """Modify the frozen file so that lock verify fails."""
        self.write(FROZEN, "// tampered\n")
