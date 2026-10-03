# Test audit: spec 006 (status and handoff), passes 1-2

Reviewer: test-auditor subagent (roles/test-auditor.md), recorded by the main session because
the role is read-only. R006-02/03/06 chaos parts are covered by the frozen 020 tests and were
cross-checked for agreement only.

All 33 tests fail on NotImplementedError; no import or fixture errors; only `status_lines`,
`snapshot` and the CLI are used.

Pass 1 findings and resolutions:
- MED handoff twice-test asserted "first" absent (clashes with "first open task"). Fixed: next-AAA/next-BBB markers.
- MED UTC not tested (NOW already UTC). Fixed: test_R006_10_timestamp_in_utc with 14:34+02:00.
- LOW git count used untracked files only. Fixed: two tracked files modified.
- LOW no-git test could see a parent repository. Fixed: GIT_CEILING_DIRECTORIES.
- LOW Windows path length from a 151-char slug. Fixed: 21 chars; the 200-char cap still exercised.
- LOW /kickoff case did not exclude the /spec line. Fixed: asserts no "new-spec".
- LOW gap: dropped blocker. Fixed: test_R006_13_dropped_blocker_still_blocks.
- Accepted by the main session: branch and count on one line; "first active spec" = first listed
  (matches the spec's 9-spec example); "099" in the error output.

Pass 2: every fix verified; nothing else affected.

verdict: ready to freeze
