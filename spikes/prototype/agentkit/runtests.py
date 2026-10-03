"""`agentkit test [scope]`: run the profile's test command quietly and print a compact summary
(parsed from JUnit XML when available), capped at MAX_LINES lines."""

from __future__ import annotations

import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .util import glob_match, list_repo_files, run, write_text_lf

MAX_LINES = 60
TRACE_LINES = 4


@dataclass
class Failure:
    name: str
    kind: str  # failure | error
    message: str
    detail: list[str] = field(default_factory=list)


@dataclass
class Summary:
    tests: int = 0
    failures: int = 0
    errors: int = 0
    skipped: int = 0
    time: float = 0.0
    failed: list[Failure] = field(default_factory=list)
    reports: int = 0

    @property
    def passed(self) -> int:
        return self.tests - self.failures - self.errors - self.skipped


def parse_junit(paths: list[Path]) -> Summary:
    s = Summary()
    for p in paths:
        try:
            root = ET.parse(p).getroot()
        except (ET.ParseError, OSError):
            continue
        s.reports += 1
        for case in root.iter("testcase"):
            s.tests += 1
            try:
                s.time += float(case.get("time") or 0)
            except ValueError:
                pass
            name = f"{case.get('classname', '')}.{case.get('name', '')}".strip(".")
            for kind in ("failure", "error"):
                el = case.find(kind)
                if el is not None:
                    if kind == "failure":
                        s.failures += 1
                    else:
                        s.errors += 1
                    msg = (el.get("message") or "").strip().splitlines()
                    body = [l.rstrip() for l in (el.text or "").strip().splitlines() if l.strip()]
                    first = msg[0] if msg else (body[0] if body else kind)
                    detail = [l.strip() for l in body if _is_useful_trace(l)][:TRACE_LINES]
                    s.failed.append(Failure(name, kind, first[:300], detail))
                    break
            else:
                if case.find("skipped") is not None:
                    s.skipped += 1
    return s


_NOISE = re.compile(r"^\s*at (java\.|jdk\.|sun\.|org\.junit\.|org\.gradle\.|kotlin\.|kotlinx\.coroutines\.|io\.kotest\.)")


def _is_useful_trace(line: str) -> bool:
    return line.strip().startswith("at ") and not _NOISE.match(line)


def format_summary(s: Summary, exit_code: int, cached: bool = False) -> list[str]:
    state = "PASS" if exit_code == 0 and not s.failures and not s.errors else "FAIL"
    head = f"{state}: {s.passed} passed, {s.failures} failed, {s.errors} errors, {s.skipped} skipped ({s.time:.1f}s, {s.reports} report(s))"
    if cached:
        head += " [no new reports: results are from the previous run / up-to-date tasks]"
    lines = [head]
    for f in s.failed:
        lines.append(f"{f.kind.upper()} {f.name}: {f.message}")
        lines.extend("    " + d for d in f.detail)
    return cap(lines)


def cap(lines: list[str], limit: int = MAX_LINES) -> list[str]:
    if len(lines) <= limit:
        return lines
    return lines[: limit - 1] + [f"... {len(lines) - limit + 1} more line(s) in .agentkit/state/last-test.log"]


def filter_output(output: str, cfg: Config, limit: int = 40) -> list[str]:
    """Fallback when there is no JUnit report: keep error-looking lines, else the tail."""
    lines = [l.rstrip() for l in output.splitlines() if l.strip()]
    rx = re.compile(cfg.profile.get("output_filter_regex") or r"(?i)error|fail")
    keep = [l for l in lines if rx.search(l)]
    picked = keep[-limit:] if keep else lines[-limit:]
    return [l[:300] for l in picked]


def resolve_command(cfg: Config, scope: str | None) -> str:
    prof = cfg.profile
    win = os.name == "nt"
    if scope:
        cmd = (win and prof.get("test_one_cmd_windows")) or prof.get("test_one_cmd")
        if not cmd:
            raise ValueError("profile has no test_one_cmd; run `agentkit test` without a scope")
        return cmd.replace("{scope}", scope)
    cmd = (win and prof.get("test_cmd_windows")) or prof.get("test_cmd")
    if not cmd:
        raise ValueError("profile has no test_cmd")
    return cmd


def find_reports(cfg: Config, since: float | None) -> list[Path]:
    globs = cfg.profile.get("junit_report_glob") or []
    if not globs:
        return []
    out = []
    for rel in _walk_reports(cfg.root, globs):
        p = cfg.root / rel
        if since is None or p.stat().st_mtime >= since:
            out.append(p)
    return out


def _walk_reports(root: Path, globs: list[str]) -> list[str]:
    # Reports live in ignored build dirs, so git ls-files cannot see them: walk instead.
    found = []
    skip = {".git", "node_modules", ".gradle", ".idea", ".agentkit"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for name in filenames:
            if not name.endswith(".xml"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), root).replace("\\", "/")
            if glob_match(rel, globs):
                found.append(rel)
    return found


def run_tests(cfg: Config, scope: str | None = None) -> tuple[int, list[str]]:
    cmd = resolve_command(cfg, scope)
    start = time.time() - 1
    proc = run(cmd, cwd=cfg.root, shell=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    write_text_lf(cfg.state_dir / "last-test.log", output)
    reports = find_reports(cfg, start)
    cached = False
    if not reports and proc.returncode == 0:
        reports = find_reports(cfg, None)
        cached = bool(reports)
    if reports:
        summary = parse_junit(reports)
        lines = format_summary(summary, proc.returncode, cached)
        if proc.returncode != 0 and not summary.failed:
            lines = cap(lines + ["command failed without failing tests; relevant output:"] + filter_output(output, cfg, 30))
    else:
        state = "PASS" if proc.returncode == 0 else f"FAIL (exit {proc.returncode})"
        lines = cap([f"{state}: `{cmd}`"] + filter_output(output, cfg))
    write_text_lf(cfg.state_dir / "last-test.txt", "\n".join(lines[:10]) + "\n")
    return proc.returncode, lines
