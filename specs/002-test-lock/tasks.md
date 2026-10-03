# 002 Test lock: tasks

- [x] 005 status functions: `PHASES`, `find_spec`, `set_status` (bootstrap, per 005's contract)
- [x] Lock file format, hashing, deterministic write, `load_lock` (R002-01 to R002-05)
- [x] `freeze`: paths, `--spec`, `--all`, errors, status → `frozen` (R002-06 to R002-15) → `tests.test_002_freeze`
- [x] Forced freeze with owner checks and log entry (R002-31, R002-32)
- [x] `verify` and `status`, including `--staged` (R002-16 to R002-18) → `tests.test_002_verify`
- [x] `unfreeze`: agent refusal, console confirmation, log (R002-19 to R002-25) → `tests.test_002_unfreeze`
- [x] `restore` and `audit` (R002-26 to R002-30) → `tests.test_002_restore_audit`
- [ ] Chaos amendment (R002-33, R002-34): needs 020's `chaos` module; tests in
  `tests/test_002_chaos.py`, implemented after 020 (see progress)
- [x] CLI `lock …` subcommands and exit codes
- [x] Full suite; `impl-reviewer` review; `feat(002)` commit
- [x] Owner: bootstrap freeze of 001/002 tests and `tests/support.py`
- [ ] Drop the interim `Edit(tests/**)` ask rule from `.claude/settings.json` once the guard
      hooks (003, 004, 012) protect frozen tests; until then it is the only in-session block
