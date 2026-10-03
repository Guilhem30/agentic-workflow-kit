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
- 2026-10-03: R002-33/34 implemented with 020 (`_chaos_audit`, the R002-34 refusal); impl-reviewer approved; `chaos approve 002 done` (chaos log #4).

<!-- agentkit:snapshot:begin -->
- 2026-10-03 (UTC), phase `done` (chaos log #4)
- Tasks: 12/13 done. Open: drop the interim `Edit(tests/**)` ask rule once the guard hooks exist (003, 004, 012)
- Tests: `tests/test_002_*.py` all pass; `lock verify`, `lock audit` OK

**Next:** none for 002. Open spec question for the owner: R002-33 does not audit a chaos log that
existed at REF and was deleted (`lock audit` passes, `chaos audit` reports it); amending it needs
`audit()` to also run when the log exists at REF.
<!-- agentkit:snapshot:end -->
