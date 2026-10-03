# 003 Guard: tasks

- [x] T1 Context: root, cwd, frozen set and indexes, protected paths (R003-04 to R003-06) → `tests.test_003_paths`
- [x] T2 Path rules for writes and reads (R003-07 to R003-12) → `tests.test_003_paths`
- [x] T3 Decision merge and reason text (R003-01 to R003-03) → `tests.test_003_paths`
- [x] T4 Tokeniser, fallback, segments and prefix words (R003-16, R003-26) → `tests.test_003_shell`
- [x] T5 Working-directory tracking (R003-17, R003-32) → `tests.test_003_shell`
- [x] T6 Redirections, write commands, git path commands (R003-18 to R003-20) → `tests.test_003_shell`
- [x] T7 Forbidden commands (R003-13 to R003-15) → `tests.test_003_shell`
- [x] T8 Interpreters, globs, directories, basenames, read-only (R003-21 to R003-25) → `tests.test_003_shell`
- [x] T9 Degraded mode (R003-27, R003-29 to R003-31) → `tests.test_003_degraded`
- [x] T10 Performance (R003-28) → `tests.test_003_perf`
- [x] T11 020's guard rules pass (`tests.test_020_guard_status`, guard classes)
- [ ] T12 Full suite; `impl-reviewer`; `feat(003)`; `chaos approve 003 done`
