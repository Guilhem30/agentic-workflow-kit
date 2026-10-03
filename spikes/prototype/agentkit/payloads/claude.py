"""Claude Code: PreToolUse / Stop / SessionStart command hooks."""

from .base import HookFormat


class ClaudeFormat(HookFormat):
    name = "claude"
    supports_ask = True


FORMAT = ClaudeFormat()
