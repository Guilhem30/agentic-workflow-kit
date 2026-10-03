"""Spec folders, phases and requirement IDs (spec 005)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

PHASES = ["draft", "approved", "tests-draft", "tests-approved", "frozen", "done"]
DROPPED = "dropped"

FOLDER_RE = re.compile(r"^(\d{3})-([a-z0-9][a-z0-9-]*)$")
_MARKER_RE = re.compile(r"\[(manual|removed)\]", re.IGNORECASE)
_DECLARE_RE = re.compile(r"^(\s*)[-*]\s+\**`?([^*`\s]+)`?\**")

NEXT_ACTIONS = {
    "draft": "run /spec {id}, then HUMAN approves",
    "approved": "run /write-tests {id}",
    "tests-draft": "HUMAN reviews the tests",
    "tests-approved": "HUMAN runs /freeze {id}",
    "frozen": "run /implement {id}",
}


@dataclass
class Spec:
    id: str
    slug: str
    dir: Path
    status: str
    title: str
    depends: list[str] = field(default_factory=list)
    spec_md: Path | None = None

    def next_action(self) -> str:
        return NEXT_ACTIONS.get(self.status, "").format(id=self.id)


def _front_matter(text: str) -> tuple[dict, tuple[int, int] | None]:
    """Parse the leading `---` block into {key: raw value}; also return its span."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, None
    values: dict[str, str] = {}
    pos = len(lines[0])
    for line in lines[1:]:
        if line.strip() == "---":
            return values, (len(lines[0]), pos)
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*?)\s*$", line)
        if m:
            values[m.group(1)] = m.group(2)
        pos += len(line)
    return {}, None


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _parse_list(value: str) -> list[str]:
    value = value.strip()
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(v) for v in parsed]
    except ValueError:
        pass
    return [_unquote(v) for v in value.strip("[]").split(",") if v.strip()]


def read_spec(folder: Path) -> Spec | None:
    m = FOLDER_RE.match(folder.name)
    if not m or not folder.is_dir():
        return None
    spec_md = folder / "spec.md"
    meta: dict = {}
    if spec_md.is_file():
        meta, _ = _front_matter(spec_md.read_text(encoding="utf-8", errors="replace"))
    status = _unquote(meta.get("status", "")) or "draft"
    title = _unquote(meta.get("title", "")) or m.group(2).replace("-", " ").capitalize()
    return Spec(id=m.group(1), slug=m.group(2), dir=folder, status=status, title=title,
                depends=_parse_list(meta.get("depends", "")), spec_md=spec_md)


def list_specs(cfg) -> list[Spec]:
    """Every spec folder (R005-01), sorted by number then folder name; duplicates included."""
    root = cfg.specs_dir
    if not root.is_dir():
        return []
    specs = [s for s in (read_spec(d) for d in root.iterdir()) if s is not None]
    return sorted(specs, key=lambda s: (s.id, s.dir.name))


def find_spec(cfg, spec_id) -> Spec | None:
    for spec in list_specs(cfg):
        if spec.id == spec_id:
            return spec
    return None


def duplicates(cfg, spec_id: str) -> list[Spec]:
    found = [s for s in list_specs(cfg) if s.id == spec_id]
    return found if len(found) > 1 else []


def set_status(spec, status) -> None:
    """Rewrite only the `status:` line of the front matter (R005-06)."""
    path = spec.spec_md or spec.dir / "spec.md"
    raw = path.read_bytes().decode("utf-8")
    meta, span = _front_matter(raw)
    if span is None:
        eol = "\r\n" if "\r\n" in raw else "\n"
        raw = f"---{eol}status: {status}{eol}---{eol}" + raw
    else:
        start, end = span
        block = raw[start:end]
        # [^\r\n]* keeps a CRLF file's "\r" at the end of the line.
        new_block, n = re.subn(r"(?m)^status\s*:[^\r\n]*", f"status: {status}", block, count=1)
        if n == 0:
            eol = "\r\n" if "\r\n" in block else "\n"
            new_block = block + f"status: {status}{eol}"
        raw = raw[:start] + new_block + raw[end:]
    path.write_bytes(raw.encode("utf-8"))
    spec.status = status


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def spec_requirements(cfg, spec) -> tuple[list[str], set[str]]:
    """The spec's declared IDs (R005-09 to R005-11): (testable, excluded)."""
    rx = re.compile(cfg.profile["req_id_regex"])
    text = (spec.spec_md or spec.dir / "spec.md").read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    testable: list[str] = []
    excluded: set[str] = set()
    i = 0
    while i < len(lines):
        m = _DECLARE_RE.match(lines[i])
        idm = rx.search(m.group(2)) if m else None
        if not (m and idm and idm.group(1) == spec.id and idm.start() == 0):
            i += 1
            continue
        indent = len(m.group(1))
        item = [lines[i]]
        j = i + 1
        while j < len(lines):
            line = lines[j]
            if not line.strip():
                k = j + 1
                while k < len(lines) and not lines[k].strip():
                    k += 1
                if k < len(lines) and _indent(lines[k]) > indent:
                    j = k
                    continue
                break
            if _indent(line) <= indent:
                break
            item.append(line)
            j += 1
        rid = f"R{idm.group(1)}-{idm.group(2)}"
        if _MARKER_RE.search("\n".join(item)):
            excluded.add(rid)
        elif rid not in testable:
            testable.append(rid)
        i = j
    excluded -= set(testable)
    return testable, excluded


def new_spec(cfg, spec_id, slug, title="") -> Path:
    raise NotImplementedError("R005-04")
