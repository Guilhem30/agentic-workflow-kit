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

<!-- agentkit:snapshot:begin -->
- 2026-10-03 (UTC), phase `tests-approved` (implemented per ADR 0001; `done` after the freeze)
- Tasks: 10/12 done. First open: Chaos amendment (R002-33, R002-34)
- Tests: 001/002 `Ran 151 tests`, `OK`; full suite red only on 020 stubs
- Branch `claude/eager-pasteur-cr0p8s`; implementation in `feat(001,002)`

**Next:** owner runs `python -m agentkit lock freeze --spec 002` and `python -m agentkit lock freeze tests/support.py`; then drop the interim `Edit(tests/**)` ask rule. R002-33/34 follow 020.
<!-- agentkit:snapshot:end -->
