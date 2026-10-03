# 001 Config and profiles: progress

- 2026-10-03: tests written (61) and the spec clarified to match. Stubs raise
  `NotImplementedError("<REQ-ID>")`; every test errors on them, as expected.
- 2026-10-03 (session 2): repo became a bootstrap instance (ADR 0001); spec moved to
  `tests-draft`. The tier table now lists `/kickoff`, a text change only; no test is affected.
  `profiles/generic.toml` is still missing and is a 001 task (R001-08).
- 2026-10-03: 020 amendment applied: R001-05 also lists `[chaos]`. The `[chaos]` keys are
  validated by 020 (R020-02), so 001 only passes the table through; `test_R001_05_reads_all_tables`
  does not cover `[chaos]` yet (owner may ask for one assertion).

<!-- agentkit:snapshot:begin -->
- 2026-10-03 (UTC), phase `tests-draft`
- Tasks: 0/9 done. First open: Globs (R001-14 to R001-16)
- Tests: `Ran 151 tests`, `FAILED (errors=186)` (expected red: stubs)
- Branch `claude/eager-pasteur-cr0p8s`, 0 uncommitted files

**Next:** owner reviews `tests/test_001_*.py` and says "tests for 001 approved"; then `/implement 001`.
<!-- agentkit:snapshot:end -->
