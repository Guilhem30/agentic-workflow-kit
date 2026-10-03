---
id: "017"
title: Language profiles
status: approved
---

# 017 Language profiles

## Context

Profiles hold everything language-specific (001). Each profile is a small preset, covered by
a smoke test on a tiny fixture repository. Smoke tests do not run the language toolchain.

## Requirements (EARS)

- **R017-01** The kit shall ship these profiles: `kotlin-gradle`, `python-pytest`, `node-ts`,
  `go`, `rust-cargo`, `dotnet`, `generic`, and `python-unittest` (used by the kit itself).
- **R017-02** Every profile shall parse with `tomllib` and set `name` (equal to the file name)
  and `description`.
- **R017-03** Every profile except `generic` shall set `test_cmd`, `junit_report_glob` (or a
  non-empty `output_filter_regex` when its runner has no JUnit output), `frozen_globs`,
  `source_globs`, `build_output_globs`, `req_id_regex` and at least one
  `codemap.symbol_regexes` entry.
- **R017-04** For each profile, a smoke test with a fixture repo containing one test file in the
  language's convention, named with a requirement ID, and one source file with a public symbol,
  shall show all of the following:
  - the test file matches `frozen_globs` and `test_globs`;
  - the source file matches `source_globs` and not `frozen_globs`;
  - `trace` finds the requirement ID;
  - `codemap` lists the public symbol and not a private one;
  - a file in the build output directory matches `build_output_globs`.
- **R017-05** `kotlin-gradle` shall:
  - use `./gradlew --quiet --console=plain test` (and `gradlew.bat` on Windows);
  - pass `{scope}` through to Gradle;
  - read reports from `**/build/test-results/**/*.xml`;
  - freeze `**/src/test*/**` and `**/src/androidTest*/**`;
  - treat `**/build/**`, `**/.gradle/**`, `**/.kotlin/**` and `**/.cxx/**` as build output;
  - list public Kotlin classes, interfaces, objects, typealiases and top-level functions
    (including extension functions) in codemap.
- **R017-06** `kotlin-gradle` shall set `ci_setup` steps for Temurin JDK 17 and Gradle.
- **R017-07** The `rust-cargo` profile shall match lowercase IDs (`r004_07_…`). The `go` profile
  shall match IDs preceded by a letter (`TestR004_07`).
- **R017-08** Each profile file shall document, in a comment, its runner prerequisites (for
  example the `JunitXml.TestLogger` package for dotnet, nextest's JUnit config for Rust, and
  `gotestsum` for Go).

## Public API contract

`profiles/<name>.toml`, with the keys of R001-10.

## Examples and edge cases

| Profile | Test file in the fixture | ID form |
|---|---|---|
| kotlin-gradle | `core/src/test/kotlin/RuleTest.kt` with `` fun `R004-07 rejects`() `` | `R004-07` |
| python-pytest | `tests/test_rules.py` with `def test_R004_07_rejects()` | `R004_07` |
| node-ts | `src/rules.test.ts` with `it("R004-07 rejects")` | `R004-07` |
| go | `rules/rules_test.go` with `func TestR004_07Rejects(t *testing.T)` | `R004_07` |
| rust-cargo | `tests/rules.rs` with `fn r004_07_rejects()` | `r004_07` |
| dotnet | `Rules.Tests/RuleTests.cs` with `public void R004_07_Rejects()` | `R004_07` |

## Additions beyond plan.md

- The `python-unittest` profile (the kit uses only the standard library, so it cannot use pytest).
- Per-profile Windows commands and `ci_setup`.

## Open questions

None. (Decided 2026-10-03: Vitest, the most used runner in 2026. It overtook Jest in weekly npm
downloads in May 2026, and about 70% of new projects choose it.)
