"""Adapter dispatch: the kit files, derived files and post-install notes of each adapter
(spec 010; the generators themselves are specs 012 to 016)."""
from __future__ import annotations


def kit_files(name: str, cfg, src, ctx: dict) -> list:
    raise NotImplementedError("R010-08")


def derived_files(name: str, cfg, ctx: dict) -> list:
    raise NotImplementedError("R010-18")


def post_install_notes(name: str) -> list[str]:
    raise NotImplementedError("R010-22")
