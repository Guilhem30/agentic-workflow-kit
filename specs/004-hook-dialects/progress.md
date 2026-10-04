# 004 hook-dialects: progress

- 2026-10-03: owner settled 003's question 1: amend 004 to honor R003-30/31 (R004-02 bad
  payload is a degraded allow, new R004-22, `Decision.degraded`). Clarified exit codes in
  R004-16, R004-18 and R004-20. `/write-tests 004` started.

<!-- agentkit:snapshot:begin -->
- 2026-10-04 00:23 (UTC), phase `done`
- Tasks: 6/6 done
- Last `agentkit test`:
  PASS: python3 -m unittest discover -s tests -t .
  Ran 741 tests in 20.771s
  OK (skipped=1)
- Branch `claude/eager-pasteur-cr0p8s`, 1 uncommitted change(s)
- Note: Done through chaos (log #27 tests-approved, #28 frozen, #29 done). #25 escalation (owner's agentkit.toml change) cleared by the owner. Open spec note: R004-20 leaves status --format dsh output unspecified (prints the Claude SessionStart shape).

**Next:** none for 004; next spec per the resume point in specs/README.md (022, 010, 011, 012)
<!-- agentkit:snapshot:end -->
