---
name: freeze
description: OWNER ONLY. Freeze a spec's approved tests into tests.lock.json and commit them. Never invoke on your own initiative.
metadata:
  agentkit-tier: fast
  agentkit-effort: low
  agentkit-user-only: "true"
  agentkit-args: "NNN"
---
# Freeze

Run this only when the owner invoked it explicitly for spec NNN.

1. If the `agentkit lock` command (spec 002) is not implemented yet, stop. Say that the
   bootstrap freeze happens once 002 is implemented (plan.md, Execution order step 2).
2. `specs/NNN-*/spec.md` must be `tests-approved`. If not, stop and say why.
3. Run `python3 -m agentkit lock status`. It must be clean.
4. Run `python3 -m agentkit lock freeze --spec NNN` and show the owner the frozen files. Freeze
   any missing file (such as a shared fixture) by path:
   `python3 -m agentkit lock freeze --spec NNN <path>`.
5. Commit the tests, the lock and the spec status: `test(NNN): freeze tests`. The pre-commit
   hook must pass.
6. Report the result and suggest clearing the context before `/implement NNN`.
