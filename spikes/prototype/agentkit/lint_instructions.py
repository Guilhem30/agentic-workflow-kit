"""`agentkit lint-instructions`: keep always-loaded instructions small and non-duplicated."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .util import parse_front_matter

SKILL_NAME_RX = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MIN_LINE_CHARS = 12


@dataclass
class LintReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    always_loaded_tokens: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


def estimate_tokens(text: str) -> int:
    return (len(text) + 3) // 4


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8").replace("\r\n", "\n")


def _norm_lines(text: str) -> list[str]:
    out = []
    in_front = text.startswith("---")
    for i, line in enumerate(text.splitlines()):
        if in_front:
            if i > 0 and line.strip() == "---":
                in_front = False
            continue
        s = re.sub(r"\s+", " ", line.strip().lstrip("-*>#0123456789. ").strip()).casefold()
        if len(s) >= MIN_LINE_CHARS and not s.startswith("```"):
            out.append(s)
    return out


def instruction_files(cfg: Config) -> dict[str, list[Path]]:
    root = cfg.root
    skills_dir = root / cfg.path("skills")
    return {
        "agents": [p for p in [root / "AGENTS.md"] if p.is_file()],
        "claude": [p for p in [root / "CLAUDE.md"] if p.is_file()],
        "rules": sorted((root / ".claude" / "rules").glob("**/*.md")) if (root / ".claude" / "rules").is_dir() else [],
        "skills": sorted(skills_dir.glob("*/SKILL.md")) if skills_dir.is_dir() else [],
    }


def lint(cfg: Config) -> LintReport:
    b = cfg.budgets
    rep = LintReport()
    files = instruction_files(cfg)
    rel = lambda p: p.relative_to(cfg.root).as_posix()  # noqa: E731

    def line_budget(paths, key):
        for p in paths:
            n = len(_read(p).splitlines())
            if n > b[key]:
                rep.errors.append(f"{rel(p)}: {n} lines > budget {b[key]} ({key})")

    line_budget(files["agents"], "agents_md_lines")
    line_budget(files["claude"], "claude_md_lines")
    line_budget(files["rules"], "rule_md_lines")
    line_budget(files["skills"], "skill_md_lines")

    tokens = 0
    for p in files["agents"]:
        tokens += estimate_tokens(_read(p))
    for p in files["claude"]:
        text = _read(p)
        tokens += estimate_tokens(text)
        if files["agents"] and "@AGENTS.md" not in text:
            rep.errors.append(f"{rel(p)}: must import `@AGENTS.md` (otherwise Claude Code never reads AGENTS.md)")
    for p in files["rules"]:
        meta, _ = parse_front_matter(_read(p))
        if not meta.get("paths"):
            tokens += estimate_tokens(_read(p))
            rep.warnings.append(f"{rel(p)}: no `paths:` front matter, so it is always loaded")
    for p in files["skills"]:
        meta, body = parse_front_matter(_read(p))
        name, desc = str(meta.get("name", "")), str(meta.get("description", ""))
        if not name:
            rep.errors.append(f"{rel(p)}: missing `name`")
        elif name != p.parent.name:
            rep.errors.append(f"{rel(p)}: name '{name}' must equal its directory '{p.parent.name}'")
        elif not SKILL_NAME_RX.match(name) or len(name) > 64:
            rep.errors.append(f"{rel(p)}: name must be lowercase-hyphenated, at most 64 chars")
        if not desc:
            rep.errors.append(f"{rel(p)}: missing `description`")
        elif len(desc) > b["skill_description_chars"]:
            rep.errors.append(f"{rel(p)}: description {len(desc)} chars > budget {b['skill_description_chars']}")
        tokens += estimate_tokens(name + ": " + desc)
    rep.always_loaded_tokens = tokens
    if tokens > b["always_loaded_tokens"]:
        rep.warnings.append(f"always-loaded instructions ~{tokens} tokens > target {b['always_loaded_tokens']}")

    # Duplicated blocks across instruction files waste tokens (and drift apart).
    n = int(b["duplicate_min_lines"])
    seen: dict[tuple, str] = {}
    reported = set()
    all_files = files["agents"] + files["claude"] + files["rules"] + files["skills"]
    for p in all_files:
        lines = _norm_lines(_read(p))
        for i in range(len(lines) - n + 1):
            window = tuple(lines[i : i + n])
            owner = seen.get(window)
            if owner is None:
                seen[window] = rel(p)
            elif owner != rel(p) and (owner, rel(p)) not in reported:
                reported.add((owner, rel(p)))
                rep.errors.append(f"duplicated block ({n}+ lines) in {owner} and {rel(p)}: '{window[0][:60]}...'")
    return rep
