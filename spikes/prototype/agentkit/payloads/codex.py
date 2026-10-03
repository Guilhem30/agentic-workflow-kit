"""Codex CLI: `.codex/hooks.json`, same schema as Claude Code. File edits arrive as
`apply_patch` with the patch text in `tool_input.command`. PreToolUse can only deny."""

from .base import HookFormat


class CodexFormat(HookFormat):
    name = "codex"
    supports_ask = False


FORMAT = CodexFormat()
