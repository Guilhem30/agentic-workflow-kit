"""Compact test runner: `agentkit test` (spec 007)."""
from __future__ import annotations

import os
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from agentkit.config import ConfigError
from agentkit.util import glob_match

_PRUNE = {".git", "node_modules", ".gradle", ".idea"}
_EXCLUDED_FRAMES = ("java.", "jdk.", "sun.", "org.junit.", "org.gradle.", "kotlin.",
                    "kotlinx.coroutines.", "io.kotest.")
_CACHED_NOTE = " [no new reports: results are from the previous run / up-to-date tasks]"
_MAX_LINES = 60
_MAX_CHARS = 300
_MAX_FRAMES = 4
_FALLBACK_LINES = 40
_COMPILE_LINES = 30
_SAVED_LINES = 10
_MTIME_TOLERANCE = 1.0
_LOG = ".agentkit/state/last-test.log"


@dataclass
class Failure:
    name: str
    kind: str
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
        return max(self.tests - self.failures - self.errors - self.skipped, 0)


def _float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _frames(text: str) -> list[str]:
    """R007-09: the first stack frames (`at ...` lines) outside the excluded packages."""
    frames = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("at "):
            continue
        target = line[3:].strip()
        head = target.split("(", 1)[0]
        bare = head.split("/", 1)[1] if "/" in head else head  # java.base/java.lang.X
        if head.startswith(_EXCLUDED_FRAMES) or bare.startswith(_EXCLUDED_FRAMES):
            continue
        frames.append(line)
        if len(frames) == _MAX_FRAMES:
            break
    return frames


def _suite_time(root: ET.Element) -> float:
    if root.tag == "testsuite" or root.get("time") is not None:
        return _float(root.get("time"))
    return sum(_float(s.get("time")) for s in root.findall("testsuite"))


def parse_junit(paths: list[Path]) -> Summary:
    summary = Summary()
    for path in paths:
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError, ValueError):
            continue  # R007-11
        summary.reports += 1
        summary.time += _suite_time(root)
        for case in root.iter("testcase"):
            summary.tests += 1
            cls, name = case.get("classname", ""), case.get("name", "")
            full = f"{cls}.{name}" if cls else name
            for tag, kind in (("failure", "FAILURE"), ("error", "ERROR")):
                el = case.find(tag)
                if el is None:
                    continue
                if kind == "FAILURE":
                    summary.failures += 1
                else:
                    summary.errors += 1
                text = el.text or ""
                message = el.get("message") or text.strip()
                first = message.strip().splitlines()[0] if message.strip() else ""
                summary.failed.append(Failure(full, kind, first, _frames(text)))
                break
            else:
                if case.find("skipped") is not None:
                    summary.skipped += 1
    return summary


def _cut(line: str) -> str:
    return line[:_MAX_CHARS]


def format_summary(summary, exit_code, cached=False) -> list[str]:
    ok = exit_code == 0 and not summary.failures and not summary.errors
    first = (f"{'PASS' if ok else 'FAIL'}: {summary.passed} passed, {summary.failures} failed, "
             f"{summary.errors} errors, {summary.skipped} skipped "
             f"({summary.time:.2f}s, {summary.reports} report(s))")
    lines = [first + (_CACHED_NOTE if cached else "")]
    for f in summary.failed:
        lines.append(_cut(f"{f.kind.upper()} {f.name}: {f.message}"))
        lines += [_cut("    " + frame) for frame in f.detail[:_MAX_FRAMES]]
    return lines


def _filtered(cfg, output: list[str], limit: int) -> list[str]:
    """R007-12: the lines matching output_filter_regex, else the last non-blank lines."""
    pattern = cfg.profile.get("output_filter_regex") or ""
    matched = []
    if pattern:
        try:
            rx = re.compile(pattern)
            matched = [l for l in output if rx.search(l)][:limit]
        except re.error:
            matched = []
    if not matched:
        matched = [l for l in output if l.strip()][-limit:]
    return [_cut(l) for l in matched]


def _reports(cfg) -> list[Path]:
    patterns = cfg.profile.get("junit_report_glob") or []
    if isinstance(patterns, str):
        patterns = [patterns]
    if not patterns:
        return []
    found = []
    for dirpath, dirnames, filenames in os.walk(cfg.root):
        dirnames[:] = [d for d in dirnames if d not in _PRUNE]
        for name in filenames:
            p = Path(dirpath, name)
            if glob_match(p.relative_to(cfg.root).as_posix(), patterns):
                found.append(p)
    return sorted(found)


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:  # removed since the walk
        return float("-inf")


def _command(cfg, scope) -> str:
    key = "test_cmd" if scope is None else "test_one_cmd"
    cmd = ""
    if os.name == "nt":
        cmd = cfg.profile.get(f"{key}_windows") or ""
    cmd = cmd or cfg.profile.get(key) or ""
    if not cmd:
        raise ConfigError(f"profile key {key!r} is empty: set it in the profile or in "
                          f"agentkit.toml [profile]")  # R007-03
    return cmd if scope is None else cmd.replace("{scope}", scope)


def run_tests(cfg, scope=None) -> tuple[int, list[str]]:
    cmd = _command(cfg, scope)
    start = time.time()
    proc = subprocess.run(cmd, shell=True, cwd=cfg.root, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    code = proc.returncode
    state = cfg.root / ".agentkit" / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "last-test.log").write_bytes(proc.stdout)
    text = proc.stdout.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")
    output = text.split("\n")

    found = _reports(cfg)
    new = [p for p in found if _mtime(p) >= start - _MTIME_TOLERANCE]
    summary = None
    if new:
        summary = parse_junit(new)
        cached = False
    elif found and code == 0:
        summary = parse_junit(found)
        cached = True  # R007-07
    if summary is not None and summary.reports:
        lines = format_summary(summary, code, cached)
        if code != 0 and not summary.failures and not summary.errors:  # R007-10
            lines.append(f"the command failed (exit {code}) but no test failed; its output:")
            lines += _filtered(cfg, output, _COMPILE_LINES)
    else:  # R007-12
        head = "PASS" if code == 0 else f"FAIL (exit {code})"
        lines = [_cut(f"{head}: {cmd}")] + _filtered(cfg, output, _FALLBACK_LINES)

    if len(lines) > _MAX_LINES:  # R007-13
        omitted = len(lines) - (_MAX_LINES - 1)
        lines = lines[:_MAX_LINES - 1] + [f"... {omitted} more line(s) omitted; full log: {_LOG}"]
    (state / "last-test.txt").write_text("\n".join(lines[:_SAVED_LINES]) + "\n",
                                         encoding="utf-8", newline="\n")  # R007-14
    return code, lines
