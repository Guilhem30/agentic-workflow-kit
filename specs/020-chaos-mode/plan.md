# 020 chaos-mode: plan

## Approach

A new module `agentkit/chaos.py` owns the `[chaos]` settings, the JSON Lines log, verdict
parsing and the five commands. `approve` and `unfreeze` follow the single check order of
R020-38: usage (exit 2), preconditions, review, pause and trace (no record), critical checks
(escalate), verdict (reject or approve). Records are appended last, after the status or lock change succeeded, so a crash never
leaves an approval for a change that did not happen.

Reuse instead of re-implementing: `lock.verify`, `lock.audit`, `lock.freeze`, `lock.human_check`,
`lock.open_console` and the unfreeze-log writer (made a private helper shared with
`lock.unfreeze`); `specs.find_spec`/`set_status`; `trace.trace_specs`; `util.glob_match`. Git
is called through `subprocess` with list arguments, as in 002.

Changed paths since the base commit = `git diff --name-only --no-renames <base>` plus
`git ls-files --others --exclude-standard` (spec Conventions).

The edits to `guard.py`, `status.py` and `cli.py` are small hooks that call into `chaos`; with
chaos off they return early, which is what R020-36 tests.

Before implementing: the owner applies the amendments listed in the spec, and ADR 0002 records
the principle 5 change.

## Files

- New: `agentkit/chaos.py`
- Changed: `agentkit/cli.py` (`chaos …` subcommands, R020-31), `agentkit/guard.py`
  (R020-29, R020-30), `agentkit/status.py` (R020-32 to R020-34), `agentkit/lock.py` (private
  helper for the unfreeze-log entry only; no public change)
- Docs: `workflow/WORKFLOW.md` chaos section (R020-35), ADR 0002

## Test strategy

`tests/test_020_*.py`, on `support.RepoTestCase` with a git repo per test:
- `test_020_config.py`: R020-01 to R020-06, R020-36;
- `test_020_log_verdict.py`: R020-07 to R020-14, R020-37 (record shape, verdict normalisation);
- `test_020_approve.py`: R020-15 to R020-22, R020-38, R020-43, one test per escalation cause;
- `test_020_unfreeze_clear.py`: R020-23 to R020-28, R020-39 to R020-41 (`confirm`, `user`, `now` injected; agent
  environment simulated with `AGENTKIT_AGENT=1`, cleared otherwise);
- `test_020_guard_status.py`: R020-29 to R020-34, R020-42, through `guard.evaluate` and
  `status.status_lines`. These need 003 and 006 implemented first.

IDs of other specs are built with `support.rid()`.
