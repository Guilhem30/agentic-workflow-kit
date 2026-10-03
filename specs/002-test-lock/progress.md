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
- 2026-10-03: owner approved the tests (`tests/test_002_*.py` and `tests/support.py`); spec moved to `tests-approved`.
- 2026-10-03: implemented; impl-reviewer approved after two passes; committed `feat(001,002)`.
- 2026-10-03: owner froze the 001/002 tests and `tests/support.py`; `tests/test_002_chaos.py` added (draft).

<!-- agentkit:snapshot:begin -->
- 2026-10-03 (UTC), phase `frozen`
- Tasks: 11/13 done. First open: Chaos amendment (R002-33, R002-34)
- Tests: 001/002 frozen by the owner (8 files incl. `tests/support.py`); `lock verify` OK.
  `tests/test_002_chaos.py` (R002-33/34) is written, not yet approved or frozen.
- Branch `claude/eager-pasteur-cr0p8s`

**Next:** owner reviews `tests/test_002_chaos.py` with 020's tests, then freezes it by path;
implement R002-33/34 with `/implement 020`.
<!-- agentkit:snapshot:end -->
