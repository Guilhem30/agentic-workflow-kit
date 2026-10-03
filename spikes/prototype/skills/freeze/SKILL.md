---
name: freeze
description: HUMAN-INVOKED ONLY. Freeze the approved tests of a spec into tests.lock.json and commit them.
metadata:
  agentkit-tier: fast
  agentkit-effort: low
  agentkit-user-only: "true"
  agentkit-args: "NNN"
---
# Freeze

Only run this when the human invoked it explicitly for spec NNN. Run tools as
`{{python}} .agentkit/bin/agentkit <command>`.

1. Check that `specs/NNN-*/spec.md` has `status: tests-approved`. If not, stop and say why.
2. Run `lock status` and `trace --spec NNN`. Both must be clean.
3. Run `lock freeze --spec NNN`. Show the human the list of frozen files. If a file is missing
   (for example a fixture outside the spec's paths), freeze it explicitly:
   `lock freeze --spec NNN <path>`.
4. Commit the tests, the stubs, the lock and the spec status:
   `git add -A` then `git commit -m "test(NNN): freeze tests"`. The pre-commit hook must pass.
5. Report the result and suggest clearing the context before `/implement NNN`.
