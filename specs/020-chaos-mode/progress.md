# 020 chaos-mode: progress

- 2026-10-03: reserved through /feature; spec is a skeleton in phase `draft`. Next: `/spec 020`.
- 2026-10-03: spec written, reviewed twice by spec-reviewer, owner answered the open questions
  and approved the spec and its amendments. ADR 0002 accepted. Amendments to 000, 001, 002,
  003, 005, 006, 010, 011, 012, 014 and 018 are approved but not yet applied.
  **Next:** apply the amendments, then `/write-tests 020`.
- 2026-10-03: amendments to 000, 001, 002, 003, 005, 006, 010, 011, 012, 014 and 018 applied.
  002 gained R002-33 and R002-34 (tests open, see 002's progress).
  **Next:** `/write-tests 020`.
- 2026-10-03: `/write-tests 020`: stubs (`chaos.py`; `guard.py` and `status.py` per 003/006
  contracts), `tests/chaos_fixtures.py` and `tests/test_020_{config,log_verdict,approve,
  unfreeze_clear,guard_status}.py`; trace 42/42. 002's R002-33/34 tests in
  `tests/test_002_chaos.py`. test-auditor: needs changes (15 findings, all fixed but one that
  contradicted R020-08), second pass `verdict: ready to freeze`. Spec moved to `tests-draft`.
  Red state: stubs raise NotImplementedError; R020-31 and R002-33/34 fail on exit codes.
- 2026-10-03: owner enabled `[chaos]` (ed186c8) and delegated this gate ("in chaos mode you shouldn't need me to approve freeze"). As the one bootstrap exception, the agent set `tests-approved` and ran `lock freeze --spec 020` (6 files). Every later gate goes through `chaos approve`.
- 2026-10-03: implemented (`chaos.py`, lock R002-33 hook, CLI refusals). First agent unfreeze (chaos log #1) fixed `test_R020_28_valid_log_passes`, whose fixture rebuilt the committed log; re-audited and re-frozen through `chaos approve` (#2, #3). impl-reviewer: two passes, all findings fixed except two spec questions for the owner.

<!-- agentkit:snapshot:begin -->
- 2026-10-03 (UTC), phase `frozen` (chaos log #3); chaos mode is ON in agentkit.toml
- Tasks: 11/14 done. Open: guard rules (with 003), status line (with 006, which also cuts line 1 to 200), WORKFLOW.md section (with 011)
- Tests: all 020 tests pass except tests/test_020_guard_status.py (32 errors on the 003/006 stubs)
- Chaos log: #1 unfreeze, #2 tests-approved, #3 frozen (020); #4 done (002). `chaos audit` OK

**Next (new session):** spec 003 under chaos mode, then 005, 004, 006 (020 then goes `done`
through `chaos approve 020 done`), 007, 008, 009, 010, 011, 012, 013, 014, 015, 016, 017, 018,
019. Every spec is already `approved`. Per spec: /write-tests NNN; test-auditor review saved to
a file outside the repo (last line `verdict: ready to freeze`); `agentkit chaos approve NNN
tests-approved --review FILE`; `agentkit chaos approve NNN frozen`; /implement NNN;
impl-reviewer review to a file; `agentkit chaos approve NNN done --review FILE`; commit per
gate, /handoff, push. On an escalation stop and tell the owner (`agentkit chaos log --open`);
never run `chaos clear`. Expected escalations: 011/012/019 touch AGENTS.md, CLAUDE.md or roles/.
Owner questions settled 2026-10-03: R020-25 reworded ("shall not refuse because of
`human_check()`"); the R002-33 deleted-log gap goes to spec 022 (R022-04).
<!-- agentkit:snapshot:end -->
