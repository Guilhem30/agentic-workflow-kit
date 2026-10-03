"""Fixtures for the chaos-mode tests of spec 020 (R020-01 to R020-43), shared with the
autopilot tests. This file belongs to spec 020; IDs of other specs are built with rid().
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from tests.support import RepoTestCase, rid, sha256_lf

NOW = datetime(2026, 10, 3, 12, 34, 56, tzinfo=timezone.utc)
NOW_TEXT = "2026-10-03T12:34:56Z"

SPEC_PASS = "verdict: ready for owner approval"
AUDIT_PASS = "verdict: ready to freeze"
IMPL_PASS = "verdict: approve"
FAIL = "verdict: needs changes"
OWNER = "verdict: needs owner"
UNFREEZE_PASS = "verdict: unfreeze justified"
UNFREEZE_FAIL = "verdict: keep frozen"

CHAOS_ON = "[chaos]\nenabled = true\n"


def dumps(record: dict) -> str:
    return json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class ChaosCase(RepoTestCase):
    """A git repository with `[chaos]` enabled, spec 012 in `draft` and everything committed,
    so the base commit is HEAD. Review files live outside the repository."""

    REST = CHAOS_ON
    SPECS = {"012": "draft"}

    def setUp(self) -> None:
        super().setUp()
        for num, status in self.SPECS.items():
            self.spec(num, status)
        if self.USE_GIT:
            self.head = self.commit_all("base")

    # specs -------------------------------------------------------------------------------
    def spec(self, num: str, status: str, slug: str = "fixture", depends=None,
             reqs: tuple[str, ...] = ()) -> Path:
        dep = "" if depends is None else "depends: " + json.dumps(list(depends)) + "\n"
        body = "".join(f"- **{rid(num, r)}** The thing shall work.\n" for r in reqs)
        return self.write(f"specs/{num}-{slug}/spec.md",
                          f'---\nid: "{num}"\ntitle: Fixture {num}\nstatus: {status}\n{dep}---\n\n'
                          f"# {num} Fixture\n\n## Requirements (EARS)\n\n{body}\nBody stays.\n")

    def spec_dir(self, num: str, slug: str = "fixture") -> Path:
        return self.root / "specs" / f"{num}-{slug}"

    # reviews and environment -------------------------------------------------------------
    def review(self, last_line: str, name: str = "review", body: str = "Findings: none.\n") -> str:
        """Write a review file outside the repository; return its absolute path."""
        path = self.tmp / "reviews-in" / f"{name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# Review\n\n{body}\n{last_line}\n", encoding="utf-8")
        return str(path)

    def agent(self) -> None:
        os.environ["AGENTKIT_AGENT"] = "1"

    # log ---------------------------------------------------------------------------------
    @property
    def chaos_log(self) -> Path:
        return self.root / "chaos-log.jsonl"

    def records(self) -> list[dict]:
        if not self.chaos_log.exists():
            return []
        return [json.loads(line) for line in self.chaos_log.read_text(encoding="utf-8").splitlines()]

    def kinds(self) -> list[str]:
        return [r["kind"] for r in self.records()]

    def write_log(self, records: list[dict]) -> None:
        self.chaos_log.write_text("".join(dumps(r) + "\n" for r in records), encoding="utf-8")

    def record(self, seq: int, kind: str, **fields) -> dict:
        """A valid record with the common fields of R020-08; `commit` defaults to HEAD."""
        rec = {"seq": seq, "time": NOW_TEXT, "kind": kind,
               "commit": fields.pop("commit", None) or self.git("rev-parse", "HEAD"),
               "user": "Fixture Owner", "actor": "agent"}
        rec.update(fields)
        return rec

    def cite(self, num: str, seq: int, gate: str, role: str, verdict: str) -> dict:
        """Store a review copy as chaos approve would (R020-14) and return its citation."""
        rel = f"specs/{num}-fixture/reviews/{seq}-{gate}-{role}.md"
        data = f"# Review\n\n{verdict}\n".encode("utf-8")
        self.write(rel, data)
        return {"role": role, "verdict": verdict, "review": rel, "review_sha256": sha256_lf(data)}

    def tree(self) -> dict[str, bytes]:
        """Every file under the root outside .git, with its bytes."""
        out = {}
        for p in sorted(self.root.rglob("*")):
            if p.is_file() and ".git" not in p.relative_to(self.root).parts:
                out[p.relative_to(self.root).as_posix()] = p.read_bytes()
        return out
