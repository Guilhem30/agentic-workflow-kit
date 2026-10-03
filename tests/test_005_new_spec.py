"""Spec 005: `new_spec()` and `agentkit new-spec` (R005-04, R005-05, R005-17, R005-19)."""
from __future__ import annotations

import re
from pathlib import Path

import agentkit
from agentkit import specs
from tests.spec_fixtures import SpecCase
from tests.support import run_cli

FILES = ("spec.md", "plan.md", "tasks.md", "progress.md")
PLACEHOLDER = re.compile(r"\{\{\s*(id|slug|title)\s*\}\}")
TEMPLATES = Path(agentkit.__file__).resolve().parent.parent / "workflow" / "templates"


def rendered(name: str, num: str, slug: str, title: str) -> str:
    """The kit template with the three placeholders replaced (R005-04)."""
    text = (TEMPLATES / name).read_text(encoding="utf-8")
    return text.replace("{{id}}", num).replace("{{slug}}", slug).replace("{{title}}", title)


class NewSpecTests(SpecCase):

    def created(self, num, slug, title=None, specs_dir="specs"):
        folder = self.root / specs_dir / f"{num}-{slug}"
        self.assertTrue(folder.is_dir(), folder)
        if title is None:
            title = slug.replace("-", " ").capitalize()
        for name in FILES:
            self.assertTrue((folder / name).is_file(), name)
            data = (folder / name).read_bytes()
            self.assertNotIn(b"\r", data, name)
            text = data.decode("utf-8")
            self.assertIsNone(PLACEHOLDER.search(text), name)
            self.assertEqual(text, rendered(name, num, slug, title), name)
        return folder

    def refused(self, *args):
        """new_spec() raises, and not because it is unimplemented."""
        with self.assertRaises(Exception) as cm:
            specs.new_spec(self.cfg(), *args)
        self.assertNotIsInstance(cm.exception, NotImplementedError)

    def test_R005_04_creates_four_files(self):
        path = specs.new_spec(self.cfg(), "007", "my-thing")
        folder = self.created("007", "my-thing")
        self.assertIn(path.resolve(), (folder.resolve(), (folder / "spec.md").resolve()))
        spec = specs.find_spec(self.cfg(), "007")
        self.assertEqual(spec.status, "draft")
        self.assertEqual(spec.title, "My thing")
        self.assertEqual(spec.slug, "my-thing")
        self.assertIn("007", (folder / "spec.md").read_text(encoding="utf-8"))
        self.assertIn("My thing", (folder / "spec.md").read_text(encoding="utf-8"))

    def test_R005_04_explicit_title(self):
        specs.new_spec(self.cfg(), "007", "my-thing", title="Données ✓ et plus")
        folder = self.created("007", "my-thing", "Données ✓ et plus")
        self.assertEqual(specs.find_spec(self.cfg(), "007").title, "Données ✓ et plus")
        self.assertIn("Données ✓ et plus", (folder / "spec.md").read_bytes().decode("utf-8"))

    def test_R005_04_default_title_multi_word(self):
        specs.new_spec(self.cfg(), "012", "adapter-claude-code")
        self.assertEqual(specs.find_spec(self.cfg(), "012").title, "Adapter claude code")

    def test_R005_04_cli(self):
        code, out = run_cli("new-spec", "007", "my-thing", "--title", "Custom title")
        self.assertEqual(code, 0, out)
        self.created("007", "my-thing", "Custom title")
        self.assertEqual(specs.find_spec(self.cfg(), "007").title, "Custom title")

    def test_R005_04_cli_default_title(self):
        code, out = run_cli("new-spec", "008", "hook-dialects")
        self.assertEqual(code, 0, out)
        self.created("008", "hook-dialects", "Hook dialects")

    def test_R005_04_configured_specs_path(self):
        self.write("agentkit.toml", '[kit]\nprofile = "fixture"\n\n[paths]\nspecs = "docs/specs"\n')
        self.spec("009", "not-counted")  # under specs/, which is no longer the specs path
        self.write("docs/specs/002-old/spec.md", "---\nstatus: done\n---\n")
        specs.new_spec(self.cfg(), None, "next")
        self.created("003", "next", specs_dir="docs/specs")
        specs.new_spec(self.cfg(), "010", "explicit")
        self.created("010", "explicit", specs_dir="docs/specs")
        self.assertFalse((self.root / "specs" / "003-next").exists())

    def test_R005_04_creates_specs_directory(self):
        self.assertFalse((self.root / "specs").exists())
        specs.new_spec(self.cfg(), "000", "vision")
        self.created("000", "vision")

    def test_R005_05_existing_number(self):
        self.spec("007", "old")
        before = self.tree()
        self.refused("007", "new-one")
        self.assertEqual(self.tree(), before)
        code, out = run_cli("new-spec", "007", "new-one")
        self.assertEqual(code, 1)
        self.assertIn("007", out)
        self.assertEqual(self.tree(), before)

    def test_R005_05_existing_number_same_slug(self):
        self.spec("007", "same")
        before = self.tree()
        code, _ = run_cli("new-spec", "007", "same")
        self.assertEqual(code, 1)
        self.assertEqual(self.tree(), before)

    def test_R005_05_invalid_slug(self):
        self.spec("001", "ok")
        before = self.tree()
        for slug in ("Bad", "-lead", "a_b", "a b", "../escape", "a/b", "dot.ted", "émoji"):
            self.refused("007", slug)
            self.refused(None, slug)
            self.assertEqual(self.tree(), before, slug)
            # A slug that looks like an option is an argparse usage error (exit 2, R000-08).
            allowed = (1, 2) if slug.startswith("-") else (1,)
            code, _ = run_cli("new-spec", "007", slug)
            self.assertIn(code, allowed, slug)
            code, _ = run_cli("new-spec", slug)
            self.assertIn(code, allowed, slug)
            self.assertEqual(self.tree(), before, slug)
        self.assertFalse((self.root / "escape").exists())

    def test_R005_05_invalid_number_creates_nothing(self):
        before = self.tree()
        for num in ("7", "0007", "abc", "-01"):
            code, _ = run_cli("new-spec", num, "thing")
            self.assertNotEqual(code, 0, num)
        self.assertEqual(self.tree(), before)

    def test_R005_17_first_number_is_000(self):
        path = specs.new_spec(self.cfg(), None, "vision")
        self.created("000", "vision")
        self.assertIn("000-vision", path.as_posix())

    def test_R005_17_next_free_number(self):
        self.spec("000", "a")
        self.spec("001", "b")
        self.spec("005", "c", status="dropped")
        self.write("specs/900notes/x.md", "ignored\n")
        specs.new_spec(self.cfg(), None, "next")
        self.created("006", "next")

    def test_R005_17_highest_plus_one_not_a_gap(self):
        self.spec("000", "a")
        self.spec("004", "b")
        specs.new_spec(self.cfg(), None, "after")
        self.created("005", "after")
        self.assertFalse(any(p.name.startswith("001-") for p in (self.root / "specs").iterdir()))

    def test_R005_17_cli_prints_the_number(self):
        self.spec("010", "x")
        code, out = run_cli("new-spec", "next-one")
        self.assertEqual(code, 0, out)
        self.assertIn("011", out)
        self.created("011", "next-one")
        code, out = run_cli("new-spec", "and-another", "--title", "T")
        self.assertEqual(code, 0, out)
        self.assertIn("012", out)
        self.assertEqual(specs.find_spec(self.cfg(), "012").title, "T")

    def test_R005_19_new_spec_refuses_duplicates(self):
        self.spec("003", "guard")
        self.spec("003", "other")
        before = self.tree()
        code, out = run_cli("new-spec", "003", "third")
        self.assertEqual(code, 1)
        self.assertIn("003-guard", out)
        self.assertIn("003-other", out)
        self.assertEqual(self.tree(), before)
