# 020 chaos-mode: progress

History is in git (`git log -- specs/020-chaos-mode/`) and the chaos log.

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
