"""Fixtures for the spec-folder and trace tests of spec 005 (R005-01 to R005-20).
IDs of other specs are built with rid()."""
from __future__ import annotations

from pathlib import Path

from tests.support import RepoTestCase


class SpecCase(RepoTestCase):
    """A git repository with the fixture profile (frozen and test globs: tests/**,
    **/src/test/**, fixtures/**) and an empty specs/ directory."""

    def spec(self, num: str, slug: str = "fixture", status: str | None = "draft",
             body: str = "", depends: str | None = None, title: str | None = None,
             front: bool = True) -> Path:
        """Write specs/<num>-<slug>/spec.md and return its folder."""
        lines = []
        if front:
            lines.append("---")
            lines.append(f'id: "{num}"')
            lines.append(f"title: {title or 'Fixture ' + num}")
            if status is not None:
                lines.append(f"status: {status}")
            if depends is not None:
                lines.append(f"depends: {depends}")
            lines.append("---")
            lines.append("")
        text = "\n".join(lines) + f"# {num} Fixture\n\n" + body
        self.write(f"specs/{num}-{slug}/spec.md", text)
        return self.root / "specs" / f"{num}-{slug}"

    def tree(self) -> dict[str, bytes]:
        """Every file under the root except .git, as {relative path: bytes}."""
        out = {}
        for p in sorted(self.root.rglob("*")):
            if p.is_file() and ".git" not in p.relative_to(self.root).parts:
                out[p.relative_to(self.root).as_posix()] = p.read_bytes()
        return out
