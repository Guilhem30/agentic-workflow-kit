"""Guard: neutral actions and allow/ask/deny decisions (spec 003)."""
from __future__ import annotations

from dataclasses import dataclass, field

ALLOW, ASK, DENY = "allow", "ask", "deny"


@dataclass
class WriteAction:
    paths: list[str]


@dataclass
class ReadAction:
    paths: list[str]


@dataclass
class ShellAction:
    command: str


@dataclass
class Decision:
    verdict: str
    reasons: list[str] = field(default_factory=list)

    @property
    def reason(self) -> str:
        return "; ".join(self.reasons)


def evaluate(cfg, actions: list, cwd: str | None = None) -> Decision:
    raise NotImplementedError("R003-01")
