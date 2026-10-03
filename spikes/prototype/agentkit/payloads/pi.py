"""Pi: `.pi/extensions/agentkit.ts` forwards `tool_call` events as `{tool, args, cwd}`; on `ask`
the extension asks the user with `ctx.ui.confirm`."""

from .base import PluginFormat


class PiFormat(PluginFormat):
    name = "pi"
    supports_ask = True


FORMAT = PiFormat()
