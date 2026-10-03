# 022 Owner decisions on open spec questions: plan

## Approach

Four small changes behind existing functions. No new public API.

## Files

- `agentkit/guard.py`: add `.git/config` to the always-protected paths (next to the lock, the log,
  `agentkit.toml` and `.agentkit/**`, around `protected = [...]`).
- `agentkit/specs.py`: strip paired inline code spans before `_MARKER_RE` is matched.
- `agentkit/lock.py`: in `freeze()`, check for `dropped` before the forced-freeze confirmation;
  in `_chaos_audit()`, also run when the log exists at `base` (through `_git`).

## Test strategy

One module, `tests/test_022_decisions.py`, one class per requirement, using the existing fixture
repos (`tests/support.py`, `tests/chaos_fixtures.py`). Small spec: per the implement skill, tests,
freeze and implementation may run in one session under chaos mode.
