"""Requirement traceability (spec 005)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from agentkit import _git, specs
from agentkit.util import glob_match

_TRACED_PHASES = ("tests-draft", "tests-approved", "frozen", "done")


@dataclass
class TraceResult:
    spec: str
    required: list[str]
    covered: dict[str, list[str]] = field(default_factory=dict)
    unknown: dict[str, list[str]] = field(default_factory=dict)

    @property
    def missing(self) -> list[str]:
        return [rid for rid in self.required if rid not in self.covered]

    @property
    def ok(self) -> bool:
        return not self.missing


class _TraceError(LookupError):
    """A spec-tree problem (R005-16, R005-19, R005-20); the CLI exits 1."""


def _test_ids(cfg) -> dict[str, list[str]]:
    """{normalised ID: [files]} over the test files (R005-13)."""
    rx = re.compile(cfg.profile["req_id_regex"])
    found: dict[str, list[str]] = {}
    for rel in _git.repo_files(cfg.root):
        if not glob_match(rel, cfg.test_globs) or glob_match(rel, cfg.profile["build_output_globs"]):
            continue
        try:
            text = (cfg.root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in rx.finditer(text):
            rid = f"R{m.group(1)}-{m.group(2)}"
            files = found.setdefault(rid, [])
            if rel not in files:
                files.append(rel)
    return found


def _check_tree(cfg, only: str | None = None) -> list[str]:
    """Duplicate numbers (R005-19) and bad `depends` (R005-20); problems as text."""
    all_specs = specs.list_specs(cfg)
    by_id: dict[str, list] = {}
    for s in all_specs:
        by_id.setdefault(s.id, []).append(s)
    problems = []
    for sid, group in sorted(by_id.items()):
        if len(group) > 1 and (only is None or sid == only):
            names = ", ".join(sorted(s.dir.name for s in group))
            problems.append(f"duplicate spec number {sid}: {names}")
    for s in all_specs:
        if only is not None and s.id != only:
            continue
        for dep in s.depends:
            if dep == s.id:
                problems.append(f"spec {s.id}: depends on itself ({dep})")
            elif dep not in by_id:
                problems.append(f"spec {s.id}: depends on {dep}, which does not exist")
    # cycles
    graph = {sid: group[0].depends for sid, group in by_id.items()}
    state: dict[str, int] = {}

    def visit(sid, path):
        state[sid] = 1
        for dep in graph.get(sid, []):
            if dep == sid or dep not in graph:
                continue
            if state.get(dep) == 1:
                cyc = path[path.index(dep):] + [dep]
                if only is None or only in cyc:
                    problems.append(f"spec {sid}: dependency cycle {' -> '.join(cyc)} (entry {dep})")
            elif state.get(dep) is None:
                visit(dep, path + [dep])
        state[sid] = 2

    for sid in sorted(graph):
        if state.get(sid) is None:
            visit(sid, [sid])
    return problems


def trace_specs(cfg, spec_id=None) -> list[TraceResult]:
    if spec_id is not None:
        spec = specs.find_spec(cfg, spec_id)
        if spec is None:
            raise _TraceError(f"spec {spec_id} does not exist")
        chosen = [spec]
    else:
        chosen = [s for s in specs.list_specs(cfg) if s.status in _TRACED_PHASES]
    ids = _test_ids(cfg)
    results = []
    for spec in chosen:
        if not spec.spec_md.is_file():
            raise _TraceError(f"spec {spec.id}: {spec.dir.name}/spec.md does not exist")
        required, excluded = specs.spec_requirements(cfg, spec)
        res = TraceResult(spec=spec.id, required=required)
        for rid, files in ids.items():
            if not rid.startswith(f"R{spec.id}-"):
                continue
            if rid in required:
                res.covered[rid] = files
            else:
                res.unknown[rid] = files
        results.append(res)
    return results


def format_results(results) -> list[str]:
    lines = []
    for r in results:
        lines.append(f"spec {r.spec}: {len(r.covered)}/{len(r.required)} requirements traced "
                     f"[{'OK' if r.ok else 'MISSING'}]")
        lines += [f"  untraced: {rid}" for rid in r.missing]
        lines += [f"  warning: {rid} is not a testable requirement of {r.spec} (in {files[0]})"
                  for rid, files in sorted(r.unknown.items())]
    return lines


def _trace_command(cfg, spec_id: str | None = None) -> tuple[int, list[str]]:
    """What `agentkit trace [--spec NNN]` prints and its exit code (R005-12 to R005-20)."""
    problems = _check_tree(cfg, only=spec_id)
    if problems:
        return 1, problems
    try:
        results = trace_specs(cfg, spec_id)
    except _TraceError as exc:
        return 1, [str(exc)]
    if not results:
        return 0, ["no spec in phase tests-draft or later; nothing to trace"]
    return (0 if all(r.ok for r in results) else 1), format_results(results)
