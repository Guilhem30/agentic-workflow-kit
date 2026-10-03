"""Instruction linter: token budgets for always-loaded agent instructions (spec 009)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from agentkit.config import ConfigError

_DEFAULT_BUDGETS = {  # R009-02
    "agents_md_lines": 150,
    "claude_md_lines": 40,
    "rule_md_lines": 80,
    "skill_md_lines": 500,
    "skill_description_chars": 200,
    "duplicate_min_lines": 3,
    "always_loaded_tokens": 3000,
}
_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_MARKERS = re.compile(r"^(?:[-*+]\s+|>\s*|#{1,6}\s+|\d+[.)]\s+)+")
_MIN_CHARS = 12


@dataclass
class LintReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    always_loaded_tokens: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


def estimate_tokens(text) -> int:
    return (len(text) + 3) // 4  # R009-10


def _split_front_matter(text: str) -> tuple[dict, list[str]]:
    """({key: value}, body lines) for a leading `---` block; ({}, all lines) without one."""
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return _parse_meta(lines[1:i]), lines[i + 1:]
    return {}, lines


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def _parse_meta(lines: list[str]) -> dict:
    """Top-level `key: value` pairs; `>` and `|` block scalars take their indented lines."""
    meta, i = {}, 0
    while i < len(lines):
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*?)\s*$", lines[i])
        i += 1
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        if value[:1] in (">", "|"):
            block = []
            while i < len(lines) and (not lines[i].strip() or lines[i][:1] in " \t"):
                block.append(lines[i].strip())
                i += 1
            value = (" " if value[0] == ">" else "\n").join(b for b in block if b)
        meta.setdefault(key, _unquote(value))
    return meta


def _line_count(text: str) -> int:
    return text.count("\n") + (1 if text and not text.endswith("\n") else 0)


def _normalised(body: list[str]) -> list[tuple[str, str]]:
    """R009-08: (normalised, original) for the lines that take part in duplicate detection."""
    out = []
    for line in body:
        raw = line.strip()
        if not raw or raw.startswith("```") or raw.startswith("~~~"):
            continue
        norm = " ".join(_MARKERS.sub("", raw).split()).lower()
        if len(norm) < _MIN_CHARS:
            continue
        out.append((norm, raw))
    return out


def _inputs(cfg) -> list[tuple[str, str, str]]:
    """(kind, repo-relative path, text) for every checked file (R009-01)."""
    root = cfg.root
    out = []
    for name, kind in (("AGENTS.md", "agents"), ("CLAUDE.md", "claude")):
        if (root / name).is_file():
            out.append((kind, name, (root / name).read_bytes().decode("utf-8-sig", "replace")))
    rules = root / ".claude" / "rules"
    if rules.is_dir():
        for p in sorted(rules.rglob("*.md")):
            if p.is_file():
                out.append(("rule", p.relative_to(root).as_posix(),
                            p.read_bytes().decode("utf-8-sig", "replace")))
    skills = root / cfg.path("skills")
    if skills.is_dir():
        for p in sorted(skills.glob("*/SKILL.md")):
            if p.is_file():
                out.append(("skill", p.relative_to(root).as_posix(),
                            p.read_bytes().decode("utf-8-sig", "replace")))
    return out


def _budgets(cfg) -> dict:
    merged = dict(_DEFAULT_BUDGETS)
    for key, value in cfg.budgets.items():
        if key not in merged:
            continue
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ConfigError(f"budgets.{key}: must be a non-negative integer")
        merged[key] = value
    return merged


def lint(cfg) -> LintReport:
    report = LintReport()
    budgets = _budgets(cfg)
    files = _inputs(cfg)
    limits = {"agents": "agents_md_lines", "claude": "claude_md_lines",
              "rule": "rule_md_lines", "skill": "skill_md_lines"}
    tokens = 0
    texts = {rel: text for _, rel, text in files}
    for kind, rel, text in files:
        meta, _ = _split_front_matter(text)
        n, limit = _line_count(text), budgets[limits[kind]]
        if n > limit:  # R009-03
            report.errors.append(f"{rel}: {n} lines, budget {limit} ({limits[kind]})")
        if kind in ("agents", "claude"):
            tokens += estimate_tokens(text)
        elif kind == "rule":
            if "paths" not in meta:  # R009-09
                report.warnings.append(f"{rel}: no `paths:` front matter, so it is always loaded")
                tokens += estimate_tokens(text)
        else:
            tokens += _check_skill(report, rel, meta, budgets)
    if "AGENTS.md" in texts and "CLAUDE.md" in texts and "@AGENTS.md" not in texts["CLAUDE.md"]:
        report.errors.append("CLAUDE.md: does not import AGENTS.md with `@AGENTS.md`")  # R009-04
    _check_duplicates(report, files, budgets["duplicate_min_lines"])
    report.always_loaded_tokens = tokens
    if tokens > budgets["always_loaded_tokens"]:  # R009-11
        report.warnings.append(f"always-loaded instructions ~{tokens} tokens, budget "
                               f"{budgets['always_loaded_tokens']}")
    return report


def _check_skill(report, rel, meta, budgets) -> int:
    """R009-05, R009-06; returns the tokens of `name: description` (R009-10)."""
    dirname = rel.rsplit("/", 2)[-2]
    name, desc = meta.get("name"), meta.get("description")
    if not name:
        report.errors.append(f"{rel}: `name` is missing")
    elif name != dirname:
        report.errors.append(f"{rel}: name {name!r} differs from its directory {dirname!r}")
    elif not _NAME_RE.match(name) or len(name) > 64:
        report.errors.append(f"{rel}: name {name!r} must match {_NAME_RE.pattern}, at most 64 chars")
    if not desc:
        report.errors.append(f"{rel}: `description` is missing")
    elif len(desc) > budgets["skill_description_chars"]:
        report.errors.append(f"{rel}: description has {len(desc)} characters, budget "
                             f"{budgets['skill_description_chars']}")
    return estimate_tokens(f"{name or ''}: {desc or ''}")


def _check_duplicates(report, files, size: int) -> None:
    """R009-07: one error per pair of files sharing `size` consecutive normalised lines."""
    if size < 1:
        return
    windows = []
    for _, rel, text in files:
        _, body = _split_front_matter(text)
        lines = _normalised(body)
        seen = {}
        for i in range(len(lines) - size + 1):
            key = tuple(norm for norm, _ in lines[i:i + size])
            seen.setdefault(key, lines[i][1])
        windows.append((rel, seen))
    for i, (a, wa) in enumerate(windows):
        for b, wb in windows[i + 1:]:
            shared = [first for key, first in wa.items() if key in wb]
            if shared:
                report.errors.append(f"duplicated block in {a} and {b}, starting: {shared[0]}")


def _cli(cfg) -> int:
    report = lint(cfg)
    for e in report.errors:
        print(f"error: {e}")
    for w in report.warnings:
        print(f"warning: {w}")
    state = "OK" if report.ok else "FAILED"
    print(f"lint-instructions: {state} (always-loaded instructions ~{report.always_loaded_tokens} tokens)")
    return 0 if report.ok else 1  # R009-12
