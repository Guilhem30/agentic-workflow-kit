"""Base class shared by the hook dialects."""

from __future__ import annotations

import json
from dataclasses import dataclass

from ..guard import ALLOW, ASK, DENY, Decision
from .common import actions_for


@dataclass
class Response:
    stdout: str = ""
    stderr: str = ""
    code: int = 0


class HookFormat:
    """Claude-Code-shaped dialect (`tool_name`/`tool_input`, `hookSpecificOutput`)."""

    name = "base"
    supports_ask = True

    def parse(self, payload: dict) -> tuple[list, str | None]:
        return actions_for(payload.get("tool_name", ""), payload.get("tool_input")), payload.get("cwd")

    def pre_response(self, decision: Decision) -> Response:
        if decision.verdict == ALLOW:
            return Response()  # say nothing: never auto-approve on the user's behalf
        verdict = decision.verdict
        reason = decision.reason
        if verdict == ASK and not self.supports_ask:
            verdict = DENY
            reason = "needs the human's approval (ask them to make this change): " + reason
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": verdict,
                "permissionDecisionReason": "agentkit: " + reason,
            }
        }
        return Response(stdout=json.dumps(out))

    def stop_response(self, payload: dict, problems: list[str]) -> Response:
        if not problems:
            return Response()
        msg = "agentkit verify failed:\n" + "\n".join(f"- {p}" for p in problems)
        if payload.get("stop_hook_active"):
            # Already continued once for this; do not loop forever, warn the human instead.
            return Response(stdout=json.dumps({"systemMessage": msg}))
        return Response(stdout=json.dumps({"decision": "block", "reason": msg}))

    def session_response(self, text: str) -> Response:
        out = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}
        return Response(stdout=json.dumps(out))


class PluginFormat(HookFormat):
    """Protocol spoken with our own TypeScript plugins (OpenCode, Pi): `{tool, args, cwd}` in,
    `{decision, reason}` / `{ok, message}` out, always exit 0."""

    def parse(self, payload: dict) -> tuple[list, str | None]:
        return actions_for(payload.get("tool", ""), payload.get("args")), payload.get("cwd")

    def pre_response(self, decision: Decision) -> Response:
        verdict = decision.verdict
        reason = decision.reason
        if verdict == ASK and not self.supports_ask:
            verdict = DENY
            reason = "needs the human's approval (ask them to make this change): " + reason
        return Response(stdout=json.dumps({"decision": verdict, "reason": reason and "agentkit: " + reason}))

    def stop_response(self, payload: dict, problems: list[str]) -> Response:
        msg = "" if not problems else "agentkit verify failed:\n" + "\n".join(f"- {p}" for p in problems)
        return Response(stdout=json.dumps({"ok": not problems, "message": msg}))

    def session_response(self, text: str) -> Response:
        return Response(stdout=json.dumps({"context": text}))
