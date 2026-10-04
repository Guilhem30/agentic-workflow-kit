"""The `dsh` hook format (spec 004)."""
from __future__ import annotations

from .base import HookFormat

FORMAT = HookFormat("dsh", supports_ask=False)
