"""`agentkit trace`: every testable requirement ID of a spec must appear in at least one test file."""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import Config
from .specs import Spec, find_spec, list_specs, norm_id, req_regex, spec_requirements
from .util import glob_match, list_repo_files

TRACED_PHASES = ("tests-draft", "tests-approved", "frozen", "done")


@dataclass
class TraceResult:
    spec: str
    required: list[str]
    covered: dict[str, list[str]] = field(default_factory=dict)
    unknown: dict[str, list[str]] = field(default_factory=dict)  # IDs in tests that the spec does not declare
    manual: set[str] = field(default_factory=set)

    @property
    def missing(self) -> list[str]:
        return [r for r in self.required if r not in self.covered]

    @property
    def ok(self) -> bool:
        return not self.missing


def _test_index(cfg: Config) -> dict[str, dict[str, list[str]]]:
    """spec id -> requirement id -> [test files mentioning it]."""
    rx = req_regex(cfg)
    index: dict[str, dict[str, list[str]]] = {}
    files = list_repo_files(cfg.root, cfg.profile.get("build_output_globs", []))
    for rel in files:
        if not glob_match(rel, cfg.test_globs):
            continue
        try:
            text = (cfg.root / rel).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in rx.finditer(text):
            rid = norm_id(m)
            hits = index.setdefault(m.group(1), {}).setdefault(rid, [])
            if rel not in hits:
                hits.append(rel)
    return index


def trace_specs(cfg: Config, spec_id: str | None = None) -> list[TraceResult]:
    if spec_id:
        s = find_spec(cfg, spec_id)
        specs: list[Spec] = [s] if s else []
        if not s:
            raise ValueError(f"spec {spec_id} not found")
    else:
        specs = [s for s in list_specs(cfg) if s.status in TRACED_PHASES]
    index = _test_index(cfg)
    results = []
    for s in specs:
        required, manual = spec_requirements(cfg, s)
        found = index.get(s.id, {})
        res = TraceResult(spec=s.id, required=required, manual=manual)
        for rid, files in found.items():
            if rid in required:
                res.covered[rid] = files
            elif rid not in manual:
                res.unknown[rid] = files
        results.append(res)
    return results


def format_results(results: list[TraceResult]) -> list[str]:
    lines = []
    for r in results:
        state = "OK" if r.ok else "MISSING"
        lines.append(f"spec {r.spec}: {len(r.covered)}/{len(r.required)} requirements traced [{state}]")
        for rid in r.missing:
            lines.append(f"  missing test for {rid}")
        for rid, files in sorted(r.unknown.items()):
            lines.append(f"  warning: {rid} used in {files[0]} but not declared in the spec")
    if not results:
        lines.append("no spec in a traced phase (tests-draft or later)")
    return lines
