"""Compact test runner: `agentkit test` (spec 007)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Failure:
    name: str
    kind: str
    message: str
    detail: list[str] = field(default_factory=list)


@dataclass
class Summary:
    tests: int = 0
    failures: int = 0
    errors: int = 0
    skipped: int = 0
    time: float = 0.0
    failed: list[Failure] = field(default_factory=list)
    reports: int = 0

    @property
    def passed(self) -> int:
        raise NotImplementedError("R007-08")


def parse_junit(paths: list[Path]) -> Summary:
    raise NotImplementedError("R007-06")


def format_summary(summary, exit_code, cached=False) -> list[str]:
    raise NotImplementedError("R007-08")


def run_tests(cfg, scope=None) -> tuple[int, list[str]]:
    raise NotImplementedError("R007-01")
