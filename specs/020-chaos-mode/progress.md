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

<!-- agentkit:snapshot:begin -->
- 2026-10-03 (UTC), phase `tests-draft`
- Tests: 020 errors only on stubs; trace 020 42/42, trace 002 34/34
- Branch `claude/eager-pasteur-cr0p8s`

**Next:** owner reviews the 020 tests and `tests/test_002_chaos.py`; on approval, set
`tests-approved` and the owner runs `lock freeze --spec 020` and
`lock freeze tests/test_002_chaos.py tests/chaos_fixtures.py`.
<!-- agentkit:snapshot:end -->
