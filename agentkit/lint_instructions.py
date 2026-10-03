"""Instruction linter: token budgets for always-loaded agent instructions (spec 009)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LintReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    always_loaded_tokens: int = 0

    @property
    def ok(self) -> bool:
        raise NotImplementedError("R009-12")


def estimate_tokens(text) -> int:
    raise NotImplementedError("R009-10")


def lint(cfg) -> LintReport:
    raise NotImplementedError("R009-01")


def _cli(cfg) -> int:
    raise NotImplementedError("R009-12")
