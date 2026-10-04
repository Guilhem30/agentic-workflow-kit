"""Fixtures for the workflow-content tests of spec 011: the kit root, a front-matter reader for
the YAML subset the kit's Markdown files use, and template rendering with sample contexts.
IDs of other specs are built with rid()."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import agentkit

KIT = Path(agentkit.__file__).resolve().parent.parent
TEMPLATES = KIT / "workflow" / "templates"
ROLES = KIT / "workflow" / "roles"
SKILLS = KIT / "skills"

BEGIN = "<!-- agentkit:begin (managed by agentkit; edit outside this block) -->"
END = "<!-- agentkit:end -->"

SPEC_FOLDER_TEMPLATES = ("spec.md", "plan.md", "tasks.md", "progress.md")
INSTALL_TEMPLATES = ("AGENTS.md.tmpl", "agentkit.toml.tmpl", "adr.md", "specs-README.md",
                     "unfreeze-log.md")
SPEC_KEYS = frozenset({"id", "slug", "title"})
INSTALL_KEYS = frozenset({"python", "version", "profile", "adapters", "ci_providers", "ci_os",
                          "models", "specs", "lock", "unfreeze_log", "codemap", "skills",
                          "roles", "chaos_log"})

ROLE_NAMES = ("spec-writer", "spec-reviewer", "test-writer", "test-auditor", "implementer",
              "impl-reviewer", "summarizer")
SKILL_NAMES = ("kickoff", "feature", "spec", "write-tests", "freeze", "implement", "handoff",
               "autopilot")

# A sample new-spec context, and two install contexts: the defaults, and one where every value
# differs from the defaults, so that a template that hard-codes a default cannot pass.
SPEC_CTX = {"id": "042", "slug": "sample-feature", "title": "Sample feature"}
DEFAULT_CTX = {"python": "python3", "version": "1.2.3", "profile": "generic",
               "adapters": '["claude-code"]', "ci_providers": '["github"]',
               "ci_os": '["linux"]', "models": "tool", "specs": "specs",
               "lock": "tests.lock.json", "unfreeze_log": "tests.unfreeze-log.md",
               "codemap": "docs/CODEMAP.md", "skills": ".agents/skills", "roles": "roles",
               "chaos_log": "chaos-log.jsonl"}
ODD_CTX = {"python": "py -3.12", "version": "9.8.7", "profile": "odd-profile",
           "adapters": '["codex"]', "ci_providers": '["gitlab"]', "ci_os": '["macos"]',
           "models": "kit", "specs": "work/specs", "lock": "work/frozen.lock.json",
           "unfreeze_log": "work/unfreeze-history.md", "codemap": "work/MAP.md",
           "skills": "work/skills", "roles": "work/roles", "chaos_log": "work/chaos-audit.jsonl"}

PLACEHOLDER = re.compile(r"\{\{(.*?)\}\}", re.S)


def placeholders(text: str) -> set[str]:
    """The inner text of every {{…}} in text, unstripped."""
    return set(PLACEHOLDER.findall(text))


def render(text: str, ctx: dict[str, str]) -> str:
    """Replace {{key}} for the keys in ctx; leave everything else as it is."""
    return PLACEHOLDER.sub(lambda m: ctx.get(m.group(1), m.group(0)), text)


class FrontMatterError(ValueError):
    pass


def _scalar(raw: str):
    v = raw.strip()
    if v[:1] in (">", "|"):
        raise FrontMatterError(f"block scalars are not supported: {raw!r}")
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_scalar(x) for x in inner.split(",")] if inner else []
    if v in ("true", "false"):
        return v == "true"
    return v


def front_matter(text: str) -> dict:
    """Parse the front matter between the leading '---' lines: top-level `key: value`, flow
    lists, quoted strings, booleans, and one level of nested mappings or block lists. Kit
    content must stay within this subset: block scalars (`>`, `|`) are rejected, and an inline
    `# comment` is read as part of the value."""
    if not text.startswith("---\n"):
        raise FrontMatterError("no front matter")
    end = text.find("\n---\n", 3)
    if end < 0:
        raise FrontMatterError("unterminated front matter")
    data: dict = {}
    current = None
    for line in text[4:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0] in " \t":
            if current is None:
                raise FrontMatterError(f"unexpected indented line: {line!r}")
            item = line.strip()
            if item.startswith("- "):
                if data[current] == {}:
                    data[current] = []
                if not isinstance(data[current], list):
                    raise FrontMatterError(f"mixed mapping and list: {line!r}")
                data[current].append(_scalar(item[2:]))
            else:
                key, sep, value = item.partition(":")
                if not sep or not isinstance(data[current], dict):
                    raise FrontMatterError(f"bad nested line: {line!r}")
                data[current][key.strip()] = _scalar(value)
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise FrontMatterError(f"not a key: {line!r}")
        key = key.strip()
        if key in data:
            raise FrontMatterError(f"duplicate key: {key}")
        if value.strip():
            data[key] = _scalar(value)
            current = None
        else:
            data[key] = {}
            current = key
    return data


def body(text: str) -> str:
    """The text after the front matter (the whole text when there is none)."""
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 3)
    return text[end + 5:] if end >= 0 else text


class ContentCase(unittest.TestCase):
    """Reads kit files, failing (not erroring) when one is missing or unreadable."""

    def read(self, path: Path) -> str:
        if not path.is_file():
            self.fail(f"missing kit file: {path.relative_to(KIT).as_posix()}")
        return path.read_bytes().decode("utf-8")

    def meta(self, path: Path) -> dict:
        text = self.read(path)
        try:
            return front_matter(text)
        except FrontMatterError as exc:
            self.fail(f"{path.relative_to(KIT).as_posix()}: {exc}")

    def block(self, rendered: str) -> str:
        """The agentkit block of a rendered AGENTS.md, marker lines included."""
        self.assertEqual(rendered.count(BEGIN), 1, "exactly one begin marker")
        self.assertEqual(rendered.count(END), 1, "exactly one end marker")
        start = rendered.index(BEGIN)
        stop = rendered.index(END)
        self.assertLess(start, stop, "begin marker before end marker")
        return rendered[start:stop + len(END)]

    def agents_md(self, ctx: dict[str, str]) -> str:
        return render(self.read(TEMPLATES / "AGENTS.md.tmpl"), ctx)
