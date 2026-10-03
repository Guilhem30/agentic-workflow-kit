"""The `claude` hook format (spec 004)."""
from __future__ import annotations

from .base import HookFormat

FORMAT = HookFormat("claude", supports_ask=True)
