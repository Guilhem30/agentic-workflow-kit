"""Spec folders: `specs/NNN-slug/{spec,plan,tasks,progress}.md` with a `status:` front matter field."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .util import dump_front_matter, parse_front_matter, write_text_lf

PHASES = ["draft", "approved", "tests-draft", "tests-approved", "frozen", "done"]

NEXT_ACTION = {
    "draft": "HUMAN: review spec {id}; when approved set `status: approved`",
    "approved": "run /write-tests {id}",
    "tests-draft": "HUMAN: review tests of {id} (`agentkit trace` must pass), then approve",
    "tests-approved": "HUMAN: run /freeze {id}",
    "frozen": "run /implement {id}",
    "done": "",
}

_DIR_RX = re.compile(r"^(\d{3})(?:-([a-z0-9][a-z0-9-]*))?$")


@dataclass
class Spec:
    id: str
    slug: str
    dir: Path
    status: str
    title: str

    @property
    def spec_md(self) -> Path:
        return self.dir / "spec.md"

    def next_action(self) -> str:
        return NEXT_ACTION.get(self.status, "fix unknown status '{}'".format(self.status)).format(id=self.id)


def list_specs(cfg: Config) -> list[Spec]:
    out = []
    if not cfg.specs_dir.is_dir():
        return out
    for d in sorted(cfg.specs_dir.iterdir()):
        m = _DIR_RX.match(d.name)
        if not d.is_dir() or not m:
            continue
        spec_md = d / "spec.md"
        meta = {}
        if spec_md.is_file():
            meta, _ = parse_front_matter(spec_md.read_text(encoding="utf-8"))
        out.append(
            Spec(
                id=m.group(1),
                slug=m.group(2) or "",
                dir=d,
                status=str(meta.get("status", "draft")),
                title=str(meta.get("title", m.group(2) or "")),
            )
        )
    return out


def find_spec(cfg: Config, spec_id: str) -> Spec | None:
    spec_id = spec_id.zfill(3)
    for s in list_specs(cfg):
        if s.id == spec_id:
            return s
    return None


def set_status(spec: Spec, status: str) -> None:
    if status not in PHASES:
        raise ValueError(f"unknown status {status}; expected one of {PHASES}")
    text = spec.spec_md.read_text(encoding="utf-8")
    meta, body = parse_front_matter(text)
    meta["status"] = status
    write_text_lf(spec.spec_md, dump_front_matter(meta) + body.lstrip("\n"))
    spec.status = status


def req_regex(cfg: Config) -> re.Pattern:
    return re.compile(cfg.profile["req_id_regex"])


def norm_id(match: re.Match) -> str:
    return f"R{match.group(1)}-{match.group(2)}"


def spec_requirements(cfg: Config, spec: Spec) -> tuple[list[str], set[str]]:
    """(testable IDs in declaration order, manual IDs). Only IDs of this spec count.

    A requirement line containing `[manual]` is excluded from traceability.
    """
    if not spec.spec_md.is_file():
        return [], set()
    rx = req_regex(cfg)
    ids: list[str] = []
    manual: set[str] = set()
    for line in spec.spec_md.read_text(encoding="utf-8").splitlines():
        for m in rx.finditer(line):
            if m.group(1) != spec.id:
                continue
            rid = norm_id(m)
            if "[manual]" in line.lower():
                manual.add(rid)
            if rid not in ids:
                ids.append(rid)
    return [i for i in ids if i not in manual], manual


def new_spec(cfg: Config, spec_id: str, slug: str, title: str = "") -> Path:
    spec_id = spec_id.zfill(3)
    if find_spec(cfg, spec_id):
        raise ValueError(f"spec {spec_id} already exists")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
        raise ValueError("slug must be lowercase letters, digits and hyphens")
    d = cfg.specs_dir / f"{spec_id}-{slug}"
    tmpl_dir = cfg.kit_source / "workflow" / "templates"
    for name in ("spec.md", "plan.md", "tasks.md", "progress.md"):
        src = tmpl_dir / name
        text = src.read_text(encoding="utf-8") if src.is_file() else f"# {name}\n"
        text = (
            text.replace("{{id}}", spec_id)
            .replace("{{slug}}", slug)
            .replace("{{title}}", title or slug.replace("-", " ").capitalize())
        )
        write_text_lf(d / name, text)
    return d
