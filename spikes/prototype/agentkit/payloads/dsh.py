"""DeepSeek Harness via its `dsh-hooks-codex` bridge, which replays `.codex/hooks.json`.

The bridge only exposes `tool_input: {command}` for every tool, so file-edit paths are invisible
here: edits to frozen files are caught by the Stop hook (verify) and the neutral layers instead."""

from .codex import CodexFormat


class DshFormat(CodexFormat):
    name = "dsh"


FORMAT = DshFormat()
