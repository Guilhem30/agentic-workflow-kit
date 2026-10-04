# Test audit: spec 007 (test runner), passes 1-3

Reviewer: test-auditor subagent (roles/test-auditor.md). Recorded verbatim in substance by the
main session, because the role is read-only.

All 29 tests fail on NotImplementedError from the stubs; no import or fixture errors. Every
test uses the Public API contract only.

Pass 1 findings and resolutions:
- HIGH R007-09 frames: zero frames passed. Fixed: exactly 4 frames, no 5th indented line.
- MED R007-06 kind casing over-specified. Fixed: compares `.upper()`.
- MED R007-06 time pinned the suite attribute. Fixed: relaxed to `>= 0`.
- MED R007-12 first-vs-last 40 over-specified. Fixed: checks ERR 21..79; the long line at i=41.
- MED R007-13 log path separator on Windows. Fixed: regex accepts either.
- MED gap R007-07 failed command. Fixed: new test expects `FAIL (exit 1)`, no cached note.
- MED gap `<testsuites>` wrapper. Fixed: new test.
- LOW mtime tolerance / `.git`: old reports 5s old; a `.git` report excluded.
- LOW R007-02 Windows variant: distinct `one-win` argv.
- LOW R007-10 30-line cap: new test.
- LOW R007-12 pass line format: accepted as is.

Pass 2: the wrapper totals (tests=3 failures=0) contradicted its contents and would reject a
valid implementation that trusts them. Fixed to tests=4 failures=1 errors=0 skipped=1.

Pass 3: the wrapper line confirmed; a totals-trusting parser passes, a double-counting one (8)
and a root-only one fail.

Checked as asked: the omitted count 142 follows from R007-08/09 (201 lines, 59 kept); the frame
ordering catches any single missing prefix; Windows `cmd /c` quoting of sys.executable is sound.

verdict: ready to freeze
