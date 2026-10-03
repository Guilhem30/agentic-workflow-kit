# 002 Test lock: tasks

- [ ] 005 status functions: `PHASES`, `find_spec`, `set_status` (bootstrap, per 005's contract)
- [ ] Lock file format, hashing, deterministic write, `load_lock` (R002-01 to R002-05)
- [ ] `freeze`: paths, `--spec`, `--all`, errors, status → `frozen` (R002-06 to R002-15) → `tests.test_002_freeze`
- [ ] Forced freeze with owner checks and log entry (R002-31, R002-32)
- [ ] `verify` and `status`, including `--staged` (R002-16 to R002-18) → `tests.test_002_verify`
- [ ] `unfreeze`: agent refusal, console confirmation, log (R002-19 to R002-25) → `tests.test_002_unfreeze`
- [ ] `restore` and `audit` (R002-26 to R002-30) → `tests.test_002_restore_audit`
- [ ] CLI `lock …` subcommands and exit codes
- [ ] Full suite; `impl-reviewer` review; `feat(002)` commit
- [ ] Owner: bootstrap freeze of 001/002 tests and `tests/support.py`; drop the interim
      `Edit(tests/**)` ask rule from `.claude/settings.json`
