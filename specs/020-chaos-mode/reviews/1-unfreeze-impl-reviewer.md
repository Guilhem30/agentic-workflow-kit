# impl-reviewer: unfreeze of tests/test_020_unfreeze_clear.py (test_R020_28_valid_log_passes)

**The test is wrong and the implementation is right.** R020-28 (spec 020 lines 215-218) makes
`audit` exit 1 when the log at REF is not a line prefix of the current log. `chaos.audit`
(agentkit/chaos.py) compares the LF-normalised bytes of the log at the resolved REF with the
current log, counts a log missing at REF as empty, and skips only this check when REF is unknown
or there is no git repository. That reading is correct.

The test's second `self.logged()` call (line 586) runs after `commit_all`, and `record()` sets
`commit` to the new HEAD (tests/chaos_fixtures.py:91). Records #1 and #2 are therefore rewritten
in the worktree log, and the audit rightly reports "rewritten since HEAD". Re-running `cite()`
writes identical review bytes, so the hashes are not involved.

**Simulation** (scratch copy, repo untouched): unmodified, 62/63 pass and only this test fails,
with that exact message. With the fix (`recs = self.logged()` ...
`self.write_log(recs + [record 3])`), 63/63 pass. Control with the prefix check disabled: the
fixed test still passes, but test_R020_28_rewritten_log, _truncated_log and
_staged_rewritten_log fail. The prefix check stays covered by negative tests, and the fixed test
passes because the log really was only appended to.

**Scope:** no hidden change. `git status` shows nothing modified under `tests/`. The request
covers only lines 583 and 586, weakens no assertion and changes no implementation. At re-freeze,
check that the file differs from HEAD in those two lines only.

verdict: unfreeze justified
