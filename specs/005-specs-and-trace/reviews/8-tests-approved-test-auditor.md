# Test audit: spec 005 (specs-and-trace), round 3 (commit 5f3560e)

## What changed since 01569dd

Only `tests/test_005_new_spec.py` changed, in two places:
- **Line 117:** the comment now reads "spec 000's usage rule". `grep -oE "R[0-9]{3}[-_][0-9]{2}"` over `tests/test_005_*.py` and `tests/spec_fixtures.py` finds no ID from another spec. Each file belongs only to spec 005 (R002-07), and `trace` sees no stray IDs.
- **Line 64:** `test_R005_04_default_title_multi_word` now goes through `created("012", "adapter-claude-code", "Adapter claude code")`. On its own it now catches a missing default title, as confirmed by the probe below.

## Stub check

The 5 modules run 81 tests: 7 failures and 8 errors. Every red test is a new_spec or new-spec test:
- the 8 errors are `NotImplementedError: R005-04`
- the failures are argparse exit 2 because the `new-spec` subcommand is missing, plus the `refused()` guard against the stub

No test fails on an import or fixture error.

## Probes

**Single-defect probes** (scratchpad `probe2.py`). I ran a correct `new_spec`, then the same code with one defect injected at a time. Every defect is caught by the API tests:

| Defect | Result |
|---|---|
| no default title | 7 API tests fail, now including `default_title_multi_word` |
| empty side files | caught |
| slug replaced with "" | caught |
| hardcoded `specs/` | caught by `configured_specs_path` |
| folder created before the existence check | caught by `existing_number` at the API tree comparison |

With no defect injected, only the CLI assertions fail, because the CLI is absent.

**Passability check.** In the scratch copy I used a plain argparse `new-spec` implementation together with the round-3 test file. All 81 tests pass.

## Findings

None. Every finding from rounds 1 and 2 is fixed, deferred to 006 (R005-18 `status`), or resolved. For R005-19, only the reading both interpretations share is tested, and the open question is recorded for the owner. Every non-manual requirement R005-01 to R005-20 has tests that assert the stated behaviour, including the spec's examples, boundaries and error paths. Nothing is flaky, the tests assert nothing beyond the contract and plan, and all access goes through the public API or the CLI.

verdict: ready to freeze
