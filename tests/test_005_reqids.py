"""Spec 005: requirement IDs in a spec (R005-09 to R005-11). The fixture spec is 004, like the
spec's examples; its IDs are built with rid()."""
from __future__ import annotations

from agentkit import specs
from tests.spec_fixtures import SpecCase
from tests.support import rid


def r(n: str, sep: str = "-") -> str:
    return rid("004", n, sep)


class ReqIdTests(SpecCase):

    def reqs(self, body, num="004"):
        self.spec(num, status="approved", body=body)
        return specs.spec_requirements(self.cfg(), specs.find_spec(self.cfg(), num))

    def test_R005_09_ids_found_and_normalised(self):
        testable, excluded = self.reqs(
            f"- **{r('01')}** first\n- **{r('02', '_')}** underscore form\n- {r('03')} plain\n")
        self.assertEqual(testable, [r("01"), r("02"), r("03")])
        self.assertEqual(excluded, set())

    def test_R005_09_declaration_order_without_duplicates(self):
        testable, _ = self.reqs(f"- **{r('03')}** c\n- **{r('01')}** a\n- **{r('03')}** again\n")
        self.assertEqual(sorted(testable), [r("01"), r("03")])
        self.assertEqual(len(testable), 2)

    def test_R005_10_other_specs_ignored(self):
        other = rid("001", "05")
        testable, excluded = self.reqs(
            f"- **{r('01')}** uses {other}\n- **{other}** declared in the wrong spec\n")
        self.assertEqual(testable, [r("01")])
        self.assertNotIn(other, excluded)

    def test_R005_11_markers_exclude(self):
        testable, excluded = self.reqs(
            f"- **{r('01')}** tested\n"
            f"- **{r('02')}** checked by hand. [manual]\n"
            f"- **{r('03')}** withdrawn [REMOVED]\n"
            f"- **{r('04')}** [Manual] mixed case\n")
        self.assertEqual(testable, [r("01")])
        self.assertEqual(excluded, {r("02"), r("03"), r("04")})

    def test_R005_11_marker_on_a_continuation_line(self):
        testable, excluded = self.reqs(
            f"- **{r('01')}** a long requirement\n"
            "  that continues here [manual]\n"
            f"- **{r('02')}** next item\n"
            "  continues without a marker\n")
        self.assertEqual(testable, [r("02")])
        self.assertEqual(excluded, {r("01")})

    def test_R005_11_marker_after_the_item_does_not_count(self):
        testable, excluded = self.reqs(
            f"- **{r('01')}** tested\n"
            "Not indented, so not part of the item [manual]\n"
            f"- **{r('02')}** tested too\n\n"
            "## Notes\n\n[removed] is a marker word.\n")
        self.assertEqual(testable, [r("01"), r("02")])
        self.assertEqual(excluded, set())


class CustomRegexTests(SpecCase):
    REST = '[profile]\nreq_id_regex = "REQ(\\\\d{3})\\\\.(\\\\d{2})"\n'

    def test_R005_09_profile_regex(self):
        self.spec("004", status="approved",
                  body="- **REQ004.01** first\n- **REQ004.02** second [manual]\n")
        testable, excluded = specs.spec_requirements(self.cfg(), specs.find_spec(self.cfg(), "004"))
        self.assertEqual(testable, [r("01")])
        self.assertEqual(excluded, {r("02")})
