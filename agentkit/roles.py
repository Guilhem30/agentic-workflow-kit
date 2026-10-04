"""Role prompts: kit roles in workflow/roles/, overridden by project roles (spec 011)."""
from __future__ import annotations

from pathlib import Path


def roles(cfg) -> dict[str, Path]:
    raise NotImplementedError("R011-13")
