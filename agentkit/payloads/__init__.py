"""Hook dialects (spec 004): one HookFormat per agent tool."""
from __future__ import annotations

from .base import HookFormat
from . import claude, codex, dsh, opencode, pi

FORMATS: dict[str, HookFormat] = {m.FORMAT.name: m.FORMAT for m in (claude, codex, dsh, opencode, pi)}


def get_format(name: str) -> HookFormat:
    """The format named `name`; KeyError for an unknown name (the CLI's choices exit 2)."""
    return FORMATS[name]
