# 004 Hook dialects: tasks

- [ ] T1 `actions_for`, `patch_paths` (R004-03 to R004-09) → `tests.test_004_mapping`
- [ ] T2 `HookFormat`, `PluginFormat`, the five `FORMAT`s, `FORMATS`, `get_format` → `tests.test_004_cli`, `tests.test_004_responses`
- [ ] T3 `guard --format` with stdin and degraded mode (R004-01, R004-02, R004-10 to R004-14, R004-22) → `tests.test_004_responses`, `tests.test_004_cli`
- [ ] T4 `verify [--format]` and `status --format` (R004-15 to R004-20) → `tests.test_004_verify_status`
- [ ] T5 Conformance fixtures pass (R004-21) → `tests.test_004_conformance`
- [ ] T6 Full suite; `impl-reviewer`; `feat(004)`; `chaos approve 004 done`
