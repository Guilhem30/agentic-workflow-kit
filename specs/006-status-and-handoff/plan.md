# 006 status-and-handoff: plan

## Approach

`agentkit/status.py` reuses `specs.list_specs`, `lock` verification and `chaos.status_suffix`
(020). `agentkit/handoff.py` builds the block; a private `_cli` writes it into progress.md.

## Test strategy

`tests/test_006_status.py` and `tests/test_006_handoff.py` on fixture repos; 020's frozen status
tests (`tests/test_020_guard_status.py`) cover the chaos parts.
