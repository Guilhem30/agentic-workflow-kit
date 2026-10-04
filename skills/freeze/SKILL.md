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

1. `specs/NNN-*/spec.md` must be `tests-approved`. If not, stop and say why.
2. Run `{{python}} .agentkit/bin/agentkit lock status`. It must be clean.
3. Run `{{python}} .agentkit/bin/agentkit lock freeze --spec NNN` and show the owner the
   frozen files. Where chaos mode applies, the command refuses and names
   `{{python}} .agentkit/bin/agentkit chaos approve NNN frozen`; run that instead. Freeze any missing file (such as a
   shared fixture) by path: `{{python}} .agentkit/bin/agentkit lock freeze --spec NNN <path>`.
4. Commit the tests, the lock and the spec status: `test(NNN): freeze tests`. The pre-commit
   hook must pass.
5. Report the result and suggest clearing the context before `/implement NNN`.
