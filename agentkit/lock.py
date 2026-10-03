"""Test-freeze lock (spec 002)."""
from __future__ import annotations

from dataclasses import dataclass


class LockError(Exception):
    """A lock problem. The CLI reports it and exits 1."""


class OwnerCheckError(LockError):
    """An owner-only action refused (agent environment, no confirmation). The CLI exits 2."""


def __getattr__(name: str):
    if name == "LOG_HEADER":
        raise NotImplementedError("R002-25")
    raise AttributeError(name)


@dataclass
class Violation:
    path: str
    kind: str  # "missing" | "modified"


@dataclass
class FreezeResult:
    added: list[str]
    unchanged: list[str]
    errors: list[str]


def load_lock(cfg) -> dict:
    raise NotImplementedError("R002-01")


def verify(cfg, staged: bool = False) -> list[Violation]:
    raise NotImplementedError("R002-16")


def status(cfg) -> dict:
    raise NotImplementedError("R002-18")


def freeze(cfg, paths=None, spec=None, all_candidates=False,
           force=False, confirm=None, user=None, now=None) -> FreezeResult:
    raise NotImplementedError("R002-06")


def unfreeze(cfg, paths, reason, confirm=None, user=None, now=None) -> list[str]:
    raise NotImplementedError("R002-24")


def human_check() -> str | None:
    raise NotImplementedError("R002-20")


def open_console():
    raise NotImplementedError("R002-21")


def restore(cfg, paths=None, ref="HEAD") -> tuple[list[str], list[str]]:
    raise NotImplementedError("R002-26")


def audit(cfg, base="HEAD", staged=False) -> list[str]:
    raise NotImplementedError("R002-27")
