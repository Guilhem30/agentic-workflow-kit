---
id: "007"
title: Compact test runner (agentkit test)
status: done
depends: ["001"]
---

# 007 Compact test runner

## Context

Raw build and test logs are the biggest token sink. `agentkit test` runs the profile's quiet
test command and prints only a summary and the failures, capped at 60 lines. JUnit XML is the
common format of Gradle, pytest, jest-junit, go-junit-report and cargo-nextest.

## Requirements (EARS)

### Command
- **R007-01** `agentkit test` shall run the profile's `test_cmd`, or `test_cmd_windows` on
  Windows when that is non-empty, through the shell, with the repository root as the working
  directory.
- **R007-02** `agentkit test SCOPE` shall run `test_one_cmd` (or its Windows variant), with
  `{scope}` replaced by SCOPE.
- **R007-03** If the needed command is empty, then `agentkit test` shall exit 2 with a message
  naming the missing profile key.
- **R007-04** The combined stdout and stderr shall be saved to `.agentkit/state/last-test.log`.
- **R007-05** The exit code shall be the test command's exit code.

### Summary from JUnit XML
- **R007-06** agentkit shall parse the files that match `junit_report_glob` and were modified at
  or after the run started (with a 1-second tolerance). It searches the whole tree except `.git`,
  `node_modules`, `.gradle` and `.idea`, including ignored build directories.
- **R007-07** When no report is new and the command succeeded, agentkit shall summarise all the
  matching reports and append ` [no new reports: results are from the previous run / up-to-date tasks]`
  to the first line.
- **R007-08** The first line shall be
  `<PASS|FAIL>: <p> passed, <f> failed, <e> errors, <s> skipped (<t>s, <r> report(s))`.
  It is PASS only when the exit code is 0 and there are no failures or errors.
- **R007-09** Each failing or erroring test case shall add one line
  `<FAILURE|ERROR> <classname>.<name>: <first line of message>` (at most 300 characters),
  followed by at most 4 indented stack frames. Frames from `java.`, `jdk.`, `sun.`,
  `org.junit.`, `org.gradle.`, `kotlin.`, `kotlinx.coroutines.` and `io.kotest.` are excluded.
- **R007-10** When the command failed but no test failed (for example a compile error),
  agentkit shall add a line saying so, then the filtered output (R007-12, at most 30 lines).
- **R007-11** Malformed report files shall be skipped without failing.

### Without JUnit reports
- **R007-12** When no report is found, agentkit shall print `PASS` or `FAIL (exit <n>)` with the
  command, then the output lines that match `output_filter_regex`. If none match, it prints the
  last lines of output instead. At most 40 lines, each cut to 300 characters.

### Limits and state
- **R007-13** The total output shall be at most 60 lines. When cut, the last line shall say how
  many lines were omitted and that the full log is in `.agentkit/state/last-test.log`.
- **R007-14** The first 10 lines of the summary shall be saved to `.agentkit/state/last-test.txt`
  (used by handoff, 006).

## Public API contract

```text
agentkit/runtests.py:
  @dataclass Failure(name, kind, message, detail: list[str])
  @dataclass Summary(tests, failures, errors, skipped, time, failed: list[Failure], reports); passed
  parse_junit(paths: list[Path]) -> Summary
  format_summary(summary, exit_code, cached=False) -> list[str]
  run_tests(cfg, scope=None) -> (exit_code: int, lines: list[str])
```

## Examples and edge cases

- Gradle up-to-date (nothing re-ran, exit 0): the previous results with the cached note.
- 200 failing tests: 60 lines, the last one points at the log.
- A Kotlin compile error: `FAIL (exit 1)`, then the `e: file.kt:12:5 Unresolved reference` lines.

## Additions beyond plan.md

- The cached-results rule (R007-07), the no-JUnit fallback (R007-12), and `last-test.txt`.

## Open questions

None.
