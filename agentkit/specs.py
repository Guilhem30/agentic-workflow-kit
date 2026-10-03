"""Spec folders, phases and requirement IDs (spec 005)."""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

PHASES = ["draft", "approved", "tests-draft", "tests-approved", "frozen", "done"]
DROPPED = "dropped"

_FOLDER_RE = re.compile(r"([0-9]{3})-([a-z0-9][a-z0-9-]*)")  # used with fullmatch
_MARKER_RE = re.compile(r"\[(manual|removed)\]", re.IGNORECASE)
_DECLARE_RE = re.compile(r"^(\s*)[-*]\s+\**`?([^*`\s]+)`?\**")

_NEXT_ACTIONS = {
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
        return _NEXT_ACTIONS.get(self.status, "").format(id=self.id)


_BOM = "\ufeff"


def _front_matter(text: str) -> tuple[dict, tuple[int, int] | None]:
    """Parse the leading `---` block (after an optional BOM) into {key: raw value}; also
    return its span. The first occurrence of a key wins, as in set_status(). A key with an
    empty value followed by indented `- item` lines is a block list, returned as JSON."""
    # Lines end at "\n" only, as in set_status() (str.splitlines() also splits on \x0c, \x85...).
    lines = text.split("\n")
    lines = [line + "\n" for line in lines[:-1]] + ([lines[-1]] if lines[-1] else [])
    if not lines or lines[0].lstrip(_BOM).strip() != "---":
        return {}, None
    values: dict[str, str] = {}
    pos = len(lines[0])
    last_key = None
    items: dict[str, list[str]] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            for key, found in items.items():
                values[key] = json.dumps(found)
            return values, (len(lines[0]), pos)
        item = re.match(r"^\s*-(?:\s+(.*?))?\s*$", line)
        if item and last_key is not None and values.get(last_key) == "":
            items.setdefault(last_key, []).append(_unquote(item.group(1) or ""))
        else:
            m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*?)\s*$", line)
            last_key = None
            if m and m.group(1) not in values:
                values[m.group(1)] = m.group(2)
                last_key = m.group(1)
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


def _read_spec(folder: Path) -> Spec | None:
    m = _FOLDER_RE.fullmatch(folder.name)
    if not m or not folder.is_dir():
        return None
    spec_md = folder / "spec.md"
    meta: dict = {}
    if spec_md.is_file():
        meta, _ = _front_matter(spec_md.read_text(encoding="utf-8", errors="replace"))
    status = _unquote(meta.get("status", "")) or "draft"
    title = _unquote(meta.get("title", "")) or _default_title(m.group(2))
    return Spec(id=m.group(1), slug=m.group(2), dir=folder, status=status, title=title,
                depends=_parse_list(meta.get("depends", "")), spec_md=spec_md)


def list_specs(cfg) -> list[Spec]:
    """Every spec folder (R005-01), sorted by number then folder name; duplicates included."""
    root = cfg.specs_dir
    if not root.is_dir():
        return []
    specs = [s for s in (_read_spec(d) for d in root.iterdir()) if s is not None]
    return sorted(specs, key=lambda s: (s.id, s.dir.name))


def find_spec(cfg, spec_id) -> Spec | None:
    for spec in list_specs(cfg):
        if spec.id == spec_id:
            return spec
    return None


def _duplicates(cfg, spec_id: str) -> list[Spec]:
    found = [s for s in list_specs(cfg) if s.id == spec_id]
    return found if len(found) > 1 else []


def set_status(spec, status) -> None:
    """Rewrite only the `status:` line of the front matter (R005-06)."""
    path = spec.spec_md or spec.dir / "spec.md"
    # surrogateescape round-trips bytes that are not UTF-8 instead of failing on them.
    raw = path.read_bytes().decode("utf-8", "surrogateescape")
    meta, span = _front_matter(raw)
    if span is None:
        eol = "\r\n" if "\r\n" in raw else "\n"
        bom = _BOM if raw.startswith(_BOM) else ""
        raw = f"{bom}---{eol}status: {status}{eol}---{eol}" + raw[len(bom):]
    else:
        start, end = span
        block = raw[start:end]
        # [^\r\n]* keeps a CRLF file's "\r" at the end of the line.
        new_block, n = re.subn(r"(?m)^status\s*:[^\r\n]*", f"status: {status}", block, count=1)
        if n == 0:
            eol = "\r\n" if "\r\n" in block else "\n"
            new_block = block + f"status: {status}{eol}"
        raw = raw[:start] + new_block + raw[end:]
    path.write_bytes(raw.encode("utf-8", "surrogateescape"))
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


_TEMPLATE_FILES = ("spec.md", "plan.md", "tasks.md", "progress.md")
_ID_RE = re.compile(r"[0-9]{3}")  # used with fullmatch


def _slug_ok(slug) -> bool:
    return isinstance(slug, str) and _FOLDER_RE.fullmatch("000-" + slug) is not None


def _default_title(slug: str) -> str:
    return slug.replace("-", " ").capitalize()


def new_spec(cfg, spec_id, slug, title="") -> Path:
    """Create <specs>/NNN-slug/ from the kit templates (R005-04, R005-05, R005-17, R005-19);
    return the folder. Raises ValueError and creates nothing on a bad number or slug, an
    existing number or a duplicated one."""
    if not _slug_ok(slug):
        raise ValueError(f"invalid slug {slug!r}: use lower-case letters, digits and hyphens, "
                         "starting with a letter or digit")
    existing = list_specs(cfg)
    if spec_id is None:
        highest = max((int(s.id) for s in existing), default=-1)
        if highest >= 999:
            raise ValueError("no free spec number: 999 is taken")
        spec_id = f"{highest + 1:03d}"
    elif not isinstance(spec_id, str) or not _ID_RE.fullmatch(spec_id):
        raise ValueError(f"invalid spec number {spec_id!r}: use three digits")
    taken = sorted(s.dir.name for s in existing if s.id == spec_id)
    if len(taken) > 1:
        raise ValueError(f"duplicate spec number {spec_id}: {', '.join(taken)}")
    if taken:
        raise ValueError(f"spec {spec_id} already exists: {taken[0]}")
    title = title or _default_title(slug)
    if any(unicodedata.category(c) in ("Cc", "Cf", "Cs", "Zl", "Zp") for c in title):
        raise ValueError("the title must be a single line without control characters")
    values = {"id": spec_id, "slug": slug, "title": title}
    src = cfg.kit_source / "workflow" / "templates"
    rendered = {}
    for name in _TEMPLATE_FILES:
        text = (src / name).read_text(encoding="utf-8").replace("\r\n", "\n")
        for key, value in values.items():
            text = text.replace("{{" + key + "}}", value)
        rendered[name] = text.encode("utf-8")  # fails here, before anything is created
    folder = cfg.specs_dir / f"{spec_id}-{slug}"
    try:
        folder.mkdir(parents=True, exist_ok=False)
    except OSError as exc:  # for example a case-insensitive clash with an ignored folder
        raise ValueError(f"cannot create {folder.name}: {exc}") from exc
    for name, text in rendered.items():
        (folder / name).write_bytes(text)
    return folder
