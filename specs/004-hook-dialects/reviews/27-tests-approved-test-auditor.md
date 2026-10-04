# Spec 004 test audit (test-auditor, pass 2 on pass-1 findings + fix diff)

Stub run: 91 tests, 452 errors, all NotImplementedError (R004-01 5, -02 101, -03 158, -05 5, -10 26, -13 22, -15 66, -16 15, -18 4, -20 50). No import or fixture errors.

Pass-1 findings:
1. Fixed: hook_fixtures.py stdin is a UTF-8 TextIOWrapper (has .buffer and .reconfigure).
2. Fixed: deny reason checked for every plugin format.
3. Fixed: test separates Decision.degraded from the reason text.
4. Fixed: TwoFrozenFilesTests reports a modified and a missing file (plain, claude, pi).
5. Fixed: lock.verify spy test deleted.
6. Fixed: normalize ignores empty shell commands.
7. Accepted as an open spec note for the owner (status --format dsh output unspecified; exit 0 covered by R004-20).
8. Kept (acceptable).
9. Fixed: bad payloads tested for verify (plugins) and status (plugins, claude, codex).

New, non-blocking: test_004_responses.py:126 asserts empty stderr for a non-degraded allow with reasons; minor over-specification, not holding the freeze.

verdict: ready to freeze
