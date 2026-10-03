"""Hook payload dialects. Each module turns a tool's hook input into neutral actions
and renders the guard's decision in that tool's response format."""

from __future__ import annotations

from . import claude, codex, dsh, opencode, pi
from .base import Response

FORMATS = {
    "claude": claude.FORMAT,
    "codex": codex.FORMAT,
    "dsh": dsh.FORMAT,
    "opencode": opencode.FORMAT,
    "pi": pi.FORMAT,
}


def get_format(name: str):
    try:
        return FORMATS[name]
    except KeyError:
        raise SystemExit(f"unknown --format {name}; expected one of {', '.join(sorted(FORMATS))}")


__all__ = ["FORMATS", "Response", "get_format"]
