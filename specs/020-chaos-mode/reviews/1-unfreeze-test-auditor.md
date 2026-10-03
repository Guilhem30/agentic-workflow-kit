# test-auditor: unfreeze of tests/test_020_unfreeze_clear.py (test_R020_28_valid_log_passes)

No edits to the repo.

**Reproduced:** the test fails at line 587; `chaos.audit` returns
`['chaos-log.jsonl: rewritten since HEAD (the chaos log is append-only)']`.

**Root cause is the test, not `audit`:** `record()` (tests/chaos_fixtures.py:88-94) defaults
`commit` to `git rev-parse HEAD`. After `commit_all("log")` moves HEAD, the second
`self.logged()` call (line 586) rebuilds records 1 and 2 with a different `commit` value, so the
committed log is no longer a line prefix of the worktree log. That is exactly the "rewritten"
case R020-28 requires `audit` to report (spec 020 lines 215-220; R020-07: earlier lines are never
rewritten). chaos.py's prefix check follows the spec; changing `audit` to pass this test would
break test_R020_28_rewritten_log and the spec. The test contradicts its own spec, so it cannot
pass honestly.

**Fix verified** in a scratchpad copy (`recs = self.logged()` ...
`self.write_log(recs + [self.record(3, ...)])`): the target test passes; all 63 tests in the
patched copy pass; no assertion removed or loosened (both `assertEqual(..., [])` stay); it still
tests what its name says (an append-only log passes); no new API surface.

**Weakness (low, out of scope):** unlike test_R020_28_no_log_passes it does not check the CLI exit
code.

verdict: unfreeze justified
