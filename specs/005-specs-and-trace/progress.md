# 005 specs-and-trace: progress

- 2026-10-03: plan.md and tasks.md written; `/write-tests 005` under chaos mode. Most of
  `specs.py`, `trace.py` and the `spec-status`/`trace` commands were written during the
  bootstrap (002 and 020 needed them), so many 005 tests pass on arrival. `new_spec` and the
  `new-spec` command are the red part.
- 2026-10-03: tests written (`tests/test_005_{folders,status,new_spec,reqids,trace}.py`,
  `tests/spec_fixtures.py`) and minimal templates `workflow/templates/{spec,plan,tasks,progress}.md`
  (011 owns their final content); trace 19/19 (R005-11 counts as excluded, see below). Red:
  only the `new_spec`/`new-spec` tests. test-auditor: round 1 needs changes (13 findings),
  round 2 needs changes (a literal foreign ID in a comment), round 3 `verdict: ready to freeze`.
  **Owner questions:** (1) R005-11's own text contains the literal `[manual]`, so it counts as
  excluded; suggest "markers inside backticks do not count". (2) R005-19: does a duplicate
  number anywhere block commands on other specs (literal), or only the number being handled?
  The frozen tests cover only what both readings share.
