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
- 2026-10-03: test-auditor passes 2 and 3 (`verdict: ready to freeze`); `chaos approve 003
  tests-approved` (#5) and `frozen` (#6, 5 files). Implemented `agentkit/guard.py`.
  impl-reviewer: 7 passes (the first reviewer could not write its file, so passes 2-7 ran as
  a general-purpose agent applying `roles/impl-reviewer.md`); every finding fixed or graded LOW
  under the spec's "best effort" bar; pass 7 `verdict: approve`. `chaos approve 003 done` (#7).

<!-- agentkit:snapshot:begin -->
- 2026-10-03 (UTC), phase `done` (chaos log #7)
- Tests: all 003 tests pass; 020's guard classes pass. Full suite: only 020's status classes
  fail (16 errors on the 006 stub).
- **Owner questions (open):**
  1. R003-30/31 vs 004: R004-02 turns a bad payload into `{}` silently, R004-10 says allow
     exits 0, and `Decision` has no degraded flag. Settle before 004's tests freeze.
  2. R003-13 is applied literally (quotes and backslashes removed), so a grep or commit message
     containing "agentkit" and "lock unfreeze" is denied. Narrow the requirement?
  3. Beyond R003-16's lists the guard also skips shell keywords (`if then else elif do while
     until ! { }`), `function`, `coproc`, `timeout`, `nice`, and analyses `bash -c`, `eval`,
     `cmd /c`, `su -c`, `env -S` scripts, plus copy-into-directory semantics. Keep or amend?
  4. `.git/config` is writable (it can set core.hooksPath). Add to R003-09 or `[guard]
     deny_globs`?
- Known LOW gaps (out of scope per spec): variables (`"$1"`), symlinks, here-strings, `$''`
  quoting, trailing cmd switches read as destination (`xcopy a b /compress`).

**Next:** spec 005 (specs-and-trace) under chaos mode, same cycle.
<!-- agentkit:snapshot:end -->
