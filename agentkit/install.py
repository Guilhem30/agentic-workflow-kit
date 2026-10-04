"""install, update and sync: the kit's files in a repository, with once, managed, block and
derived modes and a manifest for 3-way updates (spec 010)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parent.parent

_MD_MARKERS = ("<!-- agentkit:begin (managed by agentkit; edit outside this block) -->",
               "<!-- agentkit:end -->")


@dataclass
class Planned:
    path: str
    content: bytes
    mode: str
    initial: bytes | None = None
    markers: tuple[str, str] = _MD_MARKERS
    placement: str = "bottom"
    executable: bool = False


@dataclass
class Report:
    written: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    drift: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        raise NotImplementedError("R010-22")


def render(text: str, ctx: dict) -> str:
    raise NotImplementedError("R010-03")


def plan_kit(cfg, src: Path, ci, owner: str) -> list[Planned]:
    raise NotImplementedError("R010-08")


def plan_derived(cfg) -> list[Planned]:
    raise NotImplementedError("R010-18")


def apply(root: Path, planned: list[Planned], manifest: dict, force: bool = False,
          check: bool = False, derived_scope: bool = False) -> Report:
    raise NotImplementedError("R010-12")


def install(target, profile=None, adapters=None, ci=None, ci_os=None, models=None, owner="",
            python=None, src=KIT_ROOT, force=False, self_hosted=False) -> Report:
    raise NotImplementedError("R010-01")


def update(root, src, force=False) -> Report:
    raise NotImplementedError("R010-17")


def sync(cfg, check=False) -> Report:
    raise NotImplementedError("R010-18")
