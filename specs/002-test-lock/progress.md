# 002 Test lock: progress

- 2026-10-03: tests written (91) and the spec clarified to match. Stubs raise
  `NotImplementedError("<REQ-ID>")`; every test errors on them, as expected.
- 2026-10-03 (session 2): repo became a bootstrap instance (ADR 0001); spec moved to
  `tests-draft`. Until the lock exists, `.claude/settings.json` asks before any `tests/` edit;
  drop that rule after the bootstrap freeze (last task).
- 2026-10-03: 020 amendment applied: notes on R002-20, R002-21, R002-24; new R002-33 (`audit`
  also runs `chaos.audit`) and R002-34 (agent refusal of `lock freeze --spec` under chaos). No
  tests yet. They depend on 020's `chaos` module, which depends on 002, so they cannot be part of
  the bootstrap freeze of 002. Proposal for the owner: write them in `tests/test_002_chaos.py`
  during `/write-tests 020` and freeze them by path then.

<!-- agentkit:snapshot:begin -->
- 2026-10-03 (UTC), phase `tests-draft`
- Tasks: 0/10 done. First open: 005 status functions (`PHASES`, `find_spec`, `set_status`)
- Tests: `Ran 151 tests`, `FAILED (errors=186)` (expected red: stubs)
- Branch `claude/eager-pasteur-cr0p8s`, 0 uncommitted files

**Next:** owner reviews `tests/test_002_*.py` and `tests/support.py`; on approval, `/implement 002` after 001 is done.
<!-- agentkit:snapshot:end -->
