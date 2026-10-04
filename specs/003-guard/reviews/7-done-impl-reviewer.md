# impl-reviewer: spec 003 (guard) for done

Pass 7. Target: `agentkit/guard.py` at `d2584d1 fix(003): impl-reviewer pass 6 finding`,
checked against `specs/003-guard/spec.md` and `plan.md`.

## Severity bar

The same bar as pass 6, taken from the spec's Context: the shell analysis is an early
warning layer that is "best effort and favours few false positives".

- **HIGH or MEDIUM:** a requirement's text or an example row is not met; test gaming; contract
  drift; a crash or degraded path that loses a deny the spec requires; or a regression
  against an earlier pass.
- **LOW, as an owner note:** a bypass the EARS text does not cover.

## What I checked

- `python3 -m unittest tests.test_003_paths tests.test_003_shell tests.test_003_degraded
  tests.test_003_perf tests.test_020_guard_status`: 124 tests, 16 errors, 1 skipped. All 16
  errors are in 020's `NextActionTests`, `PausedStatusTests` and `StatusSuffixTests` and come
  from the `R006-01` stub in `status.py`, as expected. No 003 test fails.
- `git diff HEAD~1 --stat` touches only `agentkit/guard.py` (+6/−2). No test or fixture changed,
  and the working tree is clean. No test gaming, and no new public names.
- Probes:
  - `probe_fix.py` (pass 1): `bad: 0` for both roots, the plain one and the `Straße` one.
  - `probe2.py` (pass 2): only the three out-of-scope cases are allowed (`"$1"`, symlink,
    here-string).
  - `probe3.py`: `bad: 0`.
  - `probe4.py` (pass 3): every bypass is denied apart from `un$''freeze` (ANSI-C quoting, out
    of scope).
  - `probe5.py` (pass 4): every bypass is denied. The false positives are unchanged.
  - `probe6.py` (pass 6): every case that HEAD~2 denied is denied again.
  - `probe7.py` (new): the cmd.exe switch regex and the alias threshold.

## Pass-6 findings: verification

| # | Pass-6 finding | Status |
|---|---|---|
| 1 | POSIX `-d`, `-p`, `-P`, `-l` switched the parser to PowerShell (regression) | fixed |
| 2 | `xcopy /evil` read as a switch | fixed |

Fix 1 now denies all of these:
- `cp -d /tmp/FooTest.kt app/src/test/`
- `cp -p -t app/src/test /tmp/FooTest.kt`
- `cp -d -t ...`, `cp -P -t ...`, `cp -l -t ...`
- `cp -d -r ...`, `cp -pd ...`, `cp -pt ...`

PowerShell parameters still work through the aliases: `cp -Path ... -Dest ...` and
`copy -Pa ... -De ...` are denied. `cp -p a b` is still allowed.

Fix 2: `xcopy /evil app/src/test` is denied. `/Y`, `/e /i`, `robocopy ... /mir` and
`/exclude:x` still act as switches. `xcopy docs /tmp/docs /e /i` and `robocopy docs /tmp/docs
/mir` are allowed.

## Findings

### 1. LOW (owner note): a few cmd.exe switches are still read as the destination
`xcopy /tmp/FooTest.kt app/src/test /compress` and `copy /tmp/FooTest.kt app/src/test /-y` are
allowed. A lower-case switch word of 4 or more letters and the `/-Y` form are taken as
positionals, so the last one becomes the destination. This is not a regression: `/-y` was
handled the same way at HEAD~1, and `/compress` is rare. R003-19's text is still met, because
every non-flag argument is classified as a write. It is the copy semantics beyond that text
that miss, so this is LOW under the bar. If wanted, add `/-[A-Za-z]` and xcopy's long switches
(`/compress`, `/nooffload`) to the switch pattern.

### 2. LOW (owner notes, carried over)
- R003-13 is applied literally, so grep searches and commit messages that contain "agentkit ... lock
  unfreeze" are denied.
- `pwsh ./x.ps1 -Command <frozen>` is a false positive.
- `cp /tmp/x/* app/src/` and `cp -r /tmp/new specs/` are denied. Both are false positives
  that fail safe.
- `find -exec sh -c '... "$1"'`, symlinks, here-strings and `$''` quoting are allowed. They are
  out of scope (variables, expansion, heredocs).

## Spec conformance

- R003-01 to R003-32 hold in the frozen tests and in the probes, and every example row in the
  spec gives the stated verdict.
- Degraded mode keeps the R003-27 deny for test, lock and kit files even when an action is
  malformed.
- The public API matches the contract exactly.
- The code uses only the standard library and makes no network calls or git calls.
- Paths are matched case-insensitively, including roots whose length changes under casefold.
- Windows drive paths and Git-Bash paths are handled.
- R003-28: a heavy command takes about 1.4 ms, and the perf test passes.

## Summary

The pass-6 regression is fixed, and all earlier probes give the same results as before
(only out-of-scope cases are allowed). The frozen tests pass, with no gaming and no contract
drift. Nothing above LOW remains. The remaining items are owner notes: two rare cmd.exe
switch forms, the literal R003-13 false positives, and the out-of-scope shell features.

verdict: approve
