"""Tool calls to neutral actions (R004-03 to R004-09)."""
from __future__ import annotations


def actions_for(tool_name: str, tool_input) -> list:
    raise NotImplementedError("R004-03")


def patch_paths(text: str) -> list[str]:
    raise NotImplementedError("R004-05")
