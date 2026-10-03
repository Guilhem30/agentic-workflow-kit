"""The next /autopilot step (spec 021)."""
from __future__ import annotations

from dataclasses import dataclass, field


class AutopilotError(Exception):
    """An autopilot refusal. The CLI exits 1."""

    def __init__(self, message: str, lines: list[str] | None = None, hint: str = ""):
        super().__init__(message)
        self.message = message
        self.lines = list(lines or [])
        self.hint = hint

    def __str__(self) -> str:
        return self.message


class AutopilotUsageError(AutopilotError):
    """An autopilot usage problem. The CLI exits 2."""


WORK_DIR = ".autopilot"


@dataclass
class Step:
    spec: str
    name: str
    gate: str | None
    writer: str | None
    reviewer: str | None
    review: str | None
    set_phase: str | None
    approve: str | None
    last: str | None
    findings: list[str] = field(default_factory=list)
    reason: str | None = None


def next_step(cfg, spec_id: str) -> Step:
    raise NotImplementedError("R021-01")


def format_step(step: Step) -> list[str]:
    raise NotImplementedError("R021-05")


def _cli(args) -> int:
    raise NotImplementedError("R021-05")
