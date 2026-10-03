"""OpenCode: `.opencode/plugins/agentkit.ts` forwards `tool.execute.before` as `{tool, args, cwd}`
and throws when the decision is not `allow`. OpenCode plugins cannot ask, so ask becomes deny."""

from .base import PluginFormat


class OpenCodeFormat(PluginFormat):
    name = "opencode"
    supports_ask = False


FORMAT = OpenCodeFormat()
