# 011 workflow-content: progress

History is in git (`git log -- specs/011-workflow-content/`).

- 2026-10-04: tests written (`tests/test_011_{templates,roles,skills}.py`, fixtures in
  `tests/content_fixtures.py`), stub `agentkit/roles.py`. Phase `tests-draft`.
- Spec changes from the owner's answers: R011-07 key lists, `roles(cfg)` (R011-13), R011-08
  lints with the kit skills. R011-10: impl-reviewer `standard` (owner-approved 716e46a).
  Wording: R011-04 (trace read the backticked marker as manual), R011-06 (markers counted).
- test-auditor: needs changes (M1-M3) → fixed in 7305d0a → re-check `verdict: ready to freeze`.
- Open for the owner: L3, the AGENTS.md command table must use `{{python}} .agentkit/bin/agentkit`
  (follows R010-07; R011-05 does not say it).

**Next:** owner reviews the tests; on approval set `tests-approved` (or `chaos approve 011
tests-approved --review <re-check>`), then `/freeze 011`.
