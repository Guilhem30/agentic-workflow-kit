"""Role prompts: kit roles in workflow/roles/, overridden by project roles (spec 011)."""
from __future__ import annotations

from pathlib import Path


def _md_files(folder: Path) -> dict[str, Path]:
    if not folder.is_dir():
        return {}
    return {p.stem: p for p in sorted(folder.glob("*.md")) if p.is_file()}


def roles(cfg) -> dict[str, Path]:
    found = _md_files(cfg.kit_source / "workflow" / "roles")
    found.update(_md_files(cfg.root / cfg.path("roles")))  # R011-13: project overrides kit
    return found
