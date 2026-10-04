# Test audit: spec 008 (codemap), passes 1-2

Reviewer: test-auditor subagent (roles/test-auditor.md), recorded by the main session because
the role is read-only. All 18 tests fail on NotImplementedError; no import or fixture errors.

Pass 1 findings and resolutions:
- HIGH "generated" asserted absent from the whole map, clashing with the R008-05 header. Fixed:
  the excluded symbol is bogus_sym and absent strings are checked in entries only.
- MED the named group was also the last group. Fixed: test_R008_02_name_group_not_last.
- MED map bytes on disk not checked for LF. Fixed: read_bytes, no CR, equals build().
- MED "repository file" undefined; ignored files untested. Fixed: R008-01 worded as tracked or
  untracked, not ignored (as 002), plus test_R008_01_ignored_files_skipped.
- LOW a title heading would break the headings check. Fixed: last three headings compared.
- LOW "entry" and "first appearance" wording. Fixed in R008-04 and R008-02 (no behaviour change).
- LOW accepted: weak header check, mtime-based staleness, the bool returned by write().

Pass 2: all fixes hold; the spec wording matches the tests. Optional: a no-git case for R008-01.

verdict: ready to freeze
