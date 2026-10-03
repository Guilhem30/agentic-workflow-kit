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
- 2026-10-03: `chaos approve 005 tests-approved` (#8) and `frozen` (#9, 6 files). Implemented
  `new_spec` and `agentkit new-spec [NNN] slug [--title T]`. impl-reviewer: 4 passes. Fixes:
  - stricter number and slug checks
  - BOM front matter
  - `dropped` made terminal
  - a missing spec.md now gives a message, not a traceback
  - names outside the contract made private
  - a title injecting a status refused
  - block lists in `depends`
  - nothing created on an unencodable title

  Pass 4 gave `verdict: approve`, then `chaos approve 005 done` (#10).

<!-- agentkit:snapshot:begin -->
- 2026-10-03 (UTC), phase `done` (chaos log #10)
- Tests: all 005 tests pass (81). Full suite: only 020's status classes fail (16 errors on the
  006 stub). `trace`: 001, 002, 003, 005, 020 OK. `lock verify` and `chaos audit` OK.
- **Owner questions (open):**
  1. R005-11's own text contains the literal `[manual]`, so it counts as excluded (a trace
     warning). Proposed: "markers inside backticks do not count".
  2. R005-19/R005-20: the code takes the scoped reading. `trace --spec`, `spec-status` and
     `new-spec` refuse only a duplicated number they handle. Plain `trace` reports every
     duplicate and every bad `depends`. The literal reading (any duplicate blocks everything)
     is untested either way.
  3. R005-18 "terminal": `spec-status` refuses every change to a dropped spec. 002's
     owner-only `lock freeze --spec --force` can still freeze one; add a guard in 002?
- Known LOW gaps: titles with `Cf` characters (ZWJ emoji, soft hyphen) are refused; a quoted
  title loses its quotes; a lone `\r` in hand-edited front matter is read two ways; the
  duplicate-number check exists in three places.
- `workflow/templates/{spec,plan,tasks,progress}.md` are minimal; 011 owns their content.

**Next:** spec 004 (hook-dialects) under chaos mode, same cycle. Settle 003's owner question 1
(R003-30/31 vs R004-02/R004-10) before 004's tests freeze.
<!-- agentkit:snapshot:end -->
