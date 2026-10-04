"""Hook formats: Claude-shaped hooks and the plugin protocol (spec 004)."""
from __future__ import annotations

import json
from dataclasses import dataclass

from ..guard import ALLOW, ASK, DENY
from .common import actions_for

_ASK_PREFIX = "needs the human's approval (ask them to make this change): "


@dataclass
class Response:
    stdout: str = ""
    stderr: str = ""
    code: int = 0


def _json(data: dict) -> str:
    return json.dumps(data) + "\n"


def _cwd(value) -> str | None:
    return value if isinstance(value, str) and value else None


class HookFormat:
    """Claude-shaped hook payloads and responses (R004-10 to R004-12, R004-16, R004-17)."""

    def __init__(self, name: str, supports_ask: bool = True):
        self.name = name
        self.supports_ask = supports_ask

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r})"

    def parse(self, payload: dict):
        """(actions, cwd) from `{tool_name, tool_input, cwd}` (R004-03)."""
        tool = payload.get("tool_name")
        actions = actions_for(tool, payload.get("tool_input")) if isinstance(tool, str) and tool \
            else []
        return actions, _cwd(payload.get("cwd"))

    def _verdict(self, decision) -> tuple[str, str]:
        """The verdict and reason this tool can take: ask becomes deny without ask (R004-12)."""
        verdict, reason = decision.verdict, decision.reason
        if verdict == ASK and not self.supports_ask:
            return DENY, _ASK_PREFIX + reason
        if verdict not in (ALLOW, ASK, DENY):
            return DENY, reason
        return verdict, reason

    @staticmethod
    def _degraded_allow(decision, stdout: str = "") -> Response:
        """A degraded allow: exit 1, the guard's message on stderr (R004-22)."""
        return Response(stdout, decision.reason + "\n" if decision.reason else "", 1)

    def pre_response(self, decision) -> Response:
        verdict, reason = self._verdict(decision)
        if verdict == ALLOW:
            return self._degraded_allow(decision) if decision.degraded else Response()
        return Response(_json({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": verdict,
            "permissionDecisionReason": f"agentkit: {reason}"}}))

    def stop_response(self, payload: dict, problems: list[str]) -> Response:
        if not problems:
            return Response()
        text = "\n".join(problems)
        if payload.get("stop_hook_active") is True:
            # A second stop: warn instead of blocking again (R004-17).
            return Response(_json({"systemMessage": text})) if self.name == "claude" \
                else Response()
        return Response(_json({"decision": "block", "reason": text}))

    def session_response(self, text: str) -> Response:
        return Response(_json({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                      "additionalContext": text}}))


class PluginFormat(HookFormat):
    """The plugin protocol of our OpenCode and Pi plugins (R004-13, R004-14, R004-18)."""

    def parse(self, payload: dict):
        """(actions, cwd) from `{tool, args, cwd}` (R004-13)."""
        tool = payload.get("tool")
        actions = actions_for(tool, payload.get("args")) if isinstance(tool, str) and tool \
            else []
        return actions, _cwd(payload.get("cwd"))

    def pre_response(self, decision) -> Response:
        verdict, reason = self._verdict(decision)
        stdout = _json({"decision": verdict, "reason": reason})
        if verdict == ALLOW and decision.degraded:
            return self._degraded_allow(decision, stdout)
        return Response(stdout)

    def stop_response(self, payload: dict, problems: list[str]) -> Response:
        message = "\n".join(problems) if problems else "verify: OK"
        return Response(_json({"ok": not problems, "message": message}))

    def session_response(self, text: str) -> Response:
        return Response(_json({"context": text}))
