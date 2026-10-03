# 002 Test lock: plan

## Approach

Implement `agentkit/lock.py` per the API contract. Hashes are SHA-256 after CRLF→LF. The lock
is written deterministically (R002-02). Git is called through `subprocess` with list arguments
only: candidates, staged content, `restore` and `audit`. Owner checks (`human_check`,
`open_console`) refuse in agent environments and read the confirmation from the console, not
stdin, so an agent cannot pipe an answer in.

002 needs the status part of 005 (bootstrap, spec 000): `specs.PHASES`, `find_spec` and
`set_status` in `agentkit/specs.py`, written to 005's contract. Their own tests come with 005.

## Files

- `agentkit/lock.py`; `agentkit/specs.py` (status functions only); `agentkit/cli.py`
  (`lock …` subcommands, exit-code mapping)

## Test strategy

Frozen tests: `tests/test_002_*.py`, plus `tests/support.py` (frozen by path). After this spec
is green, the owner runs the bootstrap freeze (plan.md, Execution order step 2).
