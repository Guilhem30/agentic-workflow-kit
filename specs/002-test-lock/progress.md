# 002 Test lock: progress

- 2026-10-03: tests written (91) and the spec clarified to match. Stubs raise
  `NotImplementedError("<REQ-ID>")`; every test errors on them, as expected.
- 2026-10-03 (session 2): repo became a bootstrap instance (ADR 0001); spec moved to
  `tests-draft`. Until the lock exists, `.claude/settings.json` asks before any `tests/` edit;
  drop that rule after the bootstrap freeze (last task).

<!-- agentkit:snapshot:begin -->
- 2026-10-03 (UTC), phase `tests-draft`
- Tasks: 0/10 done. First open: 005 status functions (`PHASES`, `find_spec`, `set_status`)
- Tests: `Ran 151 tests`, `FAILED (errors=186)` (expected red: stubs)
- Branch `claude/eager-pasteur-cr0p8s`, 0 uncommitted files

**Next:** owner reviews `tests/test_002_*.py` and `tests/support.py`; on approval, `/implement 002` after 001 is done.
<!-- agentkit:snapshot:end -->
