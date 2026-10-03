"""Shared helpers (spec 001: globs)."""
from __future__ import annotations

import re
from collections.abc import Iterable


def glob_to_regex(pattern: str) -> re.Pattern:
    raise NotImplementedError("R001-14")


def glob_match(path: str, patterns: Iterable[str]) -> bool:
    raise NotImplementedError("R001-14")
