# 003 guard: progress

- 2026-10-03: plan.md and tasks.md written; `/write-tests 003` under chaos mode.
- 2026-10-03: tests written (`tests/test_003_{paths,shell,degraded,perf}.py`,
  `tests/guard_fixtures.py`); trace 32/32; red on the stub (NotImplementedError only).
  test-auditor pass 1: needs changes (16 findings). Fixed: the `cp` case that contradicted
  R003-19, normal-mode helpers now fail on a degraded fallback, the no-git mocks are asserted
  uncalled, `dd of=` dropped, the R003-21 four-character boundary, prefix-containment and `rd`
  cases, quoted absolute paths, the missing table row, fresh cfg per perf run, chdir away for
  the cfg=None root test, configured paths and outside paths in degraded mode.
  **Open spec question for the owner:** R003-30 (exit 1 on a degraded allow) and R003-31
  (stderr warning when the payload does not parse) have no matching 004 requirement:
  R004-02 turns a bad payload into `{}` silently, R004-10 says an allow exits 0, and
  `Decision` has no degraded flag. 003 tests them only at the `evaluate()` level.
