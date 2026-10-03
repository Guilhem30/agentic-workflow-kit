"""Chaos mode: agent-approved gates (spec 020)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class ChaosError(Exception):
    """A chaos refusal. The CLI exits 1."""


class ChaosUsageError(ChaosError):
    """A chaos usage problem. The CLI exits 2."""


GATES = ("approved", "tests-approved", "frozen", "done")
REVIEWS: dict[str, list[tuple[str, str, str]]] = {
    "approved": [("spec-reviewer", "verdict: ready for owner approval", "verdict: needs changes")],
    "tests-approved": [("test-auditor", "verdict: ready to freeze", "verdict: needs changes")],
    "done": [("impl-reviewer", "verdict: approve", "verdict: needs changes")],
    "unfreeze": [("test-auditor", "verdict: unfreeze justified", "verdict: keep frozen"),
                 ("impl-reviewer", "verdict: unfreeze justified", "verdict: keep frozen")],
}
NEEDS_OWNER = "verdict: needs owner"
CAUSES = ("rejections", "verify", "audit", "protected", "base", "owner")
DEFAULT_LOG = "chaos-log.jsonl"


@dataclass
class Settings:
    enabled: bool
    specs: list[str]
    max_rejections: int
    log_rel: str
    escalate_globs: list[str]
    log_path: Path

    def applies(self, spec_id: str) -> bool:
        raise NotImplementedError("R020-05")


def settings(cfg) -> Settings:
    raise NotImplementedError("R020-01")


def read_log(cfg) -> list[dict]:
    raise NotImplementedError("R020-37")


def open_escalations(cfg) -> list[dict]:
    raise NotImplementedError("R020-11")


def parse_verdict(text: str, gate: str, role: str) -> str:
    raise NotImplementedError("R020-13")


def approve(cfg, spec_id, gate, review=None, user=None, now=None) -> dict:
    raise NotImplementedError("R020-15")


def unfreeze(cfg, paths, reason, auditor_review, impl_review, user=None, now=None) -> dict:
    raise NotImplementedError("R020-23")


def clear(cfg, seqs=None, note="", all_open=False, confirm=None, user=None, now=None) -> dict:
    raise NotImplementedError("R020-26")


def format_log(records: list[dict], open_only=False) -> list[str]:
    raise NotImplementedError("R020-27")


def audit(cfg, base="HEAD", staged=False) -> list[str]:
    raise NotImplementedError("R020-28")


def status_suffix(cfg) -> str:
    raise NotImplementedError("R020-32")


def _cli(args) -> int:
    raise NotImplementedError("R020-15")
