"""Spec 001: glob matching."""
from __future__ import annotations

import unittest

from agentkit.util import glob_match, glob_to_regex


class GlobTests(unittest.TestCase):

    def check(self, cases):
        for pattern, path, expected in cases:
            with self.subTest(pattern=pattern, path=path):
                self.assertIs(glob_match(path, [pattern]), expected)

    def test_R001_14_spec_examples(self):
        self.check([
            ("**/src/test/**", "core/model/src/test/kotlin/A.kt", True),
            ("**/src/test/**", "src/test/A.kt", True),
            ("tests/**", "tests", False),
            ("*.md", "docs/a.md", False),
            ("**/*.md", "a.md", True),
        ])

    def test_R001_14_double_star_slash_matches_zero_or_more_dirs(self):
        self.check([
            ("docs/**/x.md", "docs/x.md", True),
            ("docs/**/x.md", "docs/a/b/x.md", True),
            ("**/*.md", "docs/x/a.md", True),
            ("tests/**", "tests/a/b.py", True),
        ])

    def test_R001_14_double_star_matches_anything(self):
        self.check([("**", "a/b/c.txt", True), ("a**", "ab/c/d", True)])

    def test_R001_14_star_and_question_stay_in_one_segment(self):
        self.check([
            ("*.md", "a.md", True),
            ("src/*.kt", "src/a/b.kt", False),
            ("src/*.kt", "src/b.kt", True),
            ("a/?.txt", "a/b.txt", True),
            ("a/?.txt", "a/bc.txt", False),
            ("a?b", "a/b", False),
        ])

    def test_R001_14_character_classes(self):
        self.check([
            ("[ab].txt", "a.txt", True),
            ("[ab].txt", "c.txt", False),
            ("[!ab].txt", "c.txt", True),
            ("[!ab].txt", "a.txt", False),
        ])

    def test_R001_14_any_of_several_patterns(self):
        self.assertTrue(glob_match("b/x", ["a/**", "b/**"]))
        self.assertFalse(glob_match("c/x", ["a/**", "b/**"]))
        self.assertFalse(glob_match("c/x", []))

    def test_R001_14_glob_to_regex_compiles_whole_path_match(self):
        rx = glob_to_regex("**/src/test/**")
        self.assertIsNotNone(rx.fullmatch("core/src/test/A.kt"))
        self.assertIsNone(rx.fullmatch("core/src/main/A.kt"))

    def test_R001_15_case_insensitive(self):
        self.check([
            ("**/BUILD/**", "app/build/x", True),
            ("Tests/**", "tests/A.KT", True),
            ("*.KT", "a.kt", True),
        ])
        self.assertIsNotNone(glob_to_regex("**/BUILD/**").fullmatch("app/build/x"))

    def test_R001_16_backslash_paths(self):
        self.check([
            ("tests/**", "tests\\unit\\a.py", True),
            ("**/src/test/**", "core\\model\\src\\test\\A.kt", True),
            ("*.md", "docs\\a.md", False),
        ])
