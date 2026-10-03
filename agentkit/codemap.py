"""Codemap: a compact map of source files and their public symbols (spec 008)."""
from __future__ import annotations


def build(cfg) -> str:
    raise NotImplementedError("R008-01")


def write(cfg, check=False) -> bool:
    raise NotImplementedError("R008-07")


def _cli(cfg, check) -> int:
    raise NotImplementedError("R008-08")
