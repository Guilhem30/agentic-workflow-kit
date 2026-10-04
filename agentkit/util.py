"""Shared helpers (spec 001: globs)."""
from __future__ import annotations

import functools
import re
from collections.abc import Iterable


@functools.lru_cache(maxsize=1024)
def glob_to_regex(pattern: str) -> re.Pattern:
    """Compile a glob into a case-insensitive regex that matches a whole repo-relative path
    (R001-14, R001-15)."""
    p = pattern.replace("\\", "/")
    out: list[str] = []
    i = 0
    while i < len(p):
        if p.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif p.startswith("**", i):
            out.append(".*")
            i += 2
        elif p[i] == "*":
            out.append("[^/]*")
            i += 1
        elif p[i] == "?":
            out.append("[^/]")
            i += 1
        elif p[i] == "[":
            j = i + 1
            if j < len(p) and p[j] == "!":
                j += 1
            if j < len(p) and p[j] == "]":
                j += 1
            end = p.find("]", j)
            if end < 0:
                out.append(re.escape("["))
                i += 1
                continue
            body = p[i + 1:end]
            negate = body.startswith("!")
            if negate:
                body = body[1:]
            body = body.replace("^", "\\^")  # backslashes became "/" above
            out.append("[^/" + body + "]" if negate else "[" + body + "]")
            i = end + 1
        else:
            out.append(re.escape(p[i]))
            i += 1
    return re.compile("".join(out), re.IGNORECASE | re.DOTALL)


def glob_match(path: str, patterns: Iterable[str]) -> bool:
    """True when the path matches any pattern (R001-14 to R001-16)."""
    norm = path.replace("\\", "/")
    return any(glob_to_regex(pat).fullmatch(norm) for pat in patterns)
