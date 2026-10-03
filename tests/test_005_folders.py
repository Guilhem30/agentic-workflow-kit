"""Spec 005: spec folders, front matter, phases, dropped specs, duplicate numbers and
`depends` (R005-01 to R005-03, R005-18 to R005-20)."""
from __future__ import annotations

from agentkit import specs
from tests.spec_fixtures import SpecCase
from tests.support import run_cli


class FolderTests(SpecCase):

    def test_R005_01_valid_folders_are_specs(self):
        self.spec("001", "config")
        self.spec("002", "a")
        self.spec("010", "9lives-and-more-")
        found = {(s.id, s.slug) for s in specs.list_specs(self.cfg())}
        self.assertEqual(found, {("001", "config"), ("002", "a"), ("010", "9lives-and-more-")})

    def test_R005_01_other_directories_are_ignored(self):
        self.spec("001", "config")
        for name in ("notes", "12-short", "0001-long", "003-Upper", "004-_under", "005-",
                     "006_snake", "007-has_underscore", "abc-def", "008-dot.ted"):
            self.write(f"specs/{name}/spec.md", "---\nstatus: draft\n---\n")
        self.write("specs/009-file-not-dir", "a file\n")
        self.write("specs/README.md", "# index\n")
        self.assertEqual([s.id for s in specs.list_specs(self.cfg())], ["001"])

    def test_R005_01_no_specs_directory(self):
        self.assertEqual(specs.list_specs(self.cfg()), [])
        self.assertIsNone(specs.find_spec(self.cfg(), "001"))

    def test_R005_01_find_spec_fields(self):
        folder = self.spec("004", "hook-dialects", status="approved", title="Hook dialects")
        spec = specs.find_spec(self.cfg(), "004")
        self.assertEqual(spec.id, "004")
        self.assertEqual(spec.slug, "hook-dialects")
        self.assertEqual(spec.dir.resolve(), folder.resolve())
        self.assertEqual(spec.spec_md.resolve(), (folder / "spec.md").resolve())
        self.assertEqual(spec.status, "approved")
        self.assertEqual(spec.title, "Hook dialects")
        self.assertIsNone(specs.find_spec(self.cfg(), "005"))

    def test_R005_01_configured_specs_path(self):
        self.write("agentkit.toml", '[kit]\nprofile = "fixture"\n\n[paths]\nspecs = "docs/specs"\n')
        self.write("docs/specs/003-guard/spec.md", "---\nstatus: frozen\n---\n")
        self.spec("001", "elsewhere")  # under specs/, which is no longer the specs path
        self.assertEqual([(s.id, s.status) for s in specs.list_specs(self.cfg())],
                         [("003", "frozen")])

    def test_R005_02_front_matter(self):
        self.write("specs/004-x/spec.md",
                   '---\nid: "004"\ntitle: "Quoted title"\nstatus: tests-draft\n---\n\n# body\n'
                   "status: done\n")
        spec = specs.find_spec(self.cfg(), "004")
        self.assertEqual(spec.status, "tests-draft")
        self.assertEqual(spec.title, "Quoted title")

    def test_R005_02_missing_status_means_draft(self):
        self.spec("004", status=None)
        self.assertEqual(specs.find_spec(self.cfg(), "004").status, "draft")

    def test_R005_02_no_front_matter_means_draft(self):
        self.spec("004", front=False, body="status: done\n")
        self.assertEqual(specs.find_spec(self.cfg(), "004").status, "draft")

    def test_R005_03_phase_order(self):
        self.assertEqual(specs.PHASES,
                         ["draft", "approved", "tests-draft", "tests-approved", "frozen", "done"])

    def test_R005_03_next_action_is_text(self):
        for phase in specs.PHASES + [specs.DROPPED]:
            self.spec("004", status=phase)
            self.assertIsInstance(specs.find_spec(self.cfg(), "004").next_action(), str)


class DroppedTests(SpecCase):

    def test_R005_18_dropped_constant_outside_the_order(self):
        self.assertEqual(specs.DROPPED, "dropped")
        self.assertNotIn(specs.DROPPED, specs.PHASES)

    def test_R005_18_dropped_spec_keeps_folder_and_number(self):
        self.spec("004", status="draft")
        self.commit_all()
        code, _ = run_cli("spec-status", "004", "dropped")
        self.assertEqual(code, 0)
        spec = specs.find_spec(self.cfg(), "004")
        self.assertEqual(spec.status, "dropped")
        self.assertTrue((self.root / "specs/004-fixture/spec.md").is_file())
        self.assertIn("004", [s.id for s in specs.list_specs(self.cfg())])


class DuplicateTests(SpecCase):

    def setUp(self):
        super().setUp()
        self.spec("003", "guard", status="tests-draft")
        self.spec("003", "other", status="draft")
        self.spec("004", "fine", status="draft")

    def assert_names_both(self, out):
        self.assertIn("003-guard", out)
        self.assertIn("003-other", out)

    def test_R005_19_trace_refuses_duplicates(self):
        code, out = run_cli("trace")
        self.assertEqual(code, 1)
        self.assert_names_both(out)

    def test_R005_19_trace_spec_refuses_duplicates(self):
        code, out = run_cli("trace", "--spec", "003")
        self.assertEqual(code, 1)
        self.assert_names_both(out)

    def test_R005_19_spec_status_refuses_duplicates(self):
        before = self.tree()
        code, out = run_cli("spec-status", "003", "approved")
        self.assertEqual(code, 1)
        self.assert_names_both(out)
        self.assertEqual(self.tree(), before)


class DependsTests(SpecCase):

    def test_R005_20_depends_parsed(self):
        self.spec("001", status="done")
        self.spec("002", status="done", depends='["001"]')
        self.spec("003", status="draft", depends="[]")
        self.spec("004", status="draft")
        got = {s.id: s.depends for s in specs.list_specs(self.cfg())}
        self.assertEqual(got, {"001": [], "002": ["001"], "003": [], "004": []})

    def test_R005_20_valid_depends_pass(self):
        self.spec("001", status="draft")
        self.spec("002", status="draft", depends='["001"]')
        self.spec("003", status="draft", depends='["001", "002"]')
        code, _ = run_cli("trace")
        self.assertEqual(code, 0)

    def check_bad(self, depends, entry, extra=()):
        self.spec("001", status="draft")
        for num, dep in extra:
            self.spec(num, status="draft", depends=dep)
        self.spec("004", status="draft", depends=depends)
        code, out = run_cli("trace")
        self.assertEqual(code, 1, out)
        self.assertIn("004", out)
        self.assertIn(entry, out)
        return out

    def test_R005_20_unknown_entry(self):
        self.check_bad('["001", "042"]', "042")

    def test_R005_20_self_entry(self):
        self.check_bad('["004"]', "004")

    def test_R005_20_cycle(self):
        out = self.check_bad('["006"]', "006", extra=[("006", '["004"]')])
        self.assertIn("006", out)

    def test_R005_20_longer_cycle(self):
        self.spec("001", status="draft", depends='["002"]')
        self.spec("002", status="draft", depends='["003"]')
        self.spec("003", status="draft", depends='["001"]')
        code, out = run_cli("trace")
        self.assertEqual(code, 1)
        for num in ("001", "002", "003"):
            self.assertIn(num, out)

    def test_R005_20_checked_for_untraced_phases_too(self):
        # Only draft specs: nothing to trace, but the bad entry still fails.
        self.spec("004", status="draft", depends='["099"]')
        code, out = run_cli("trace")
        self.assertEqual(code, 1)
        self.assertIn("099", out)
