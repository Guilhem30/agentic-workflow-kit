---
name: implement
description: Implement a spec whose tests are frozen, task by task, until all tests pass; then review for test gaming. Use for specs with status frozen.
metadata:
  agentkit-tier: standard
  agentkit-effort: medium
  agentkit-args: "NNN"
---
# Implementation phase

Run tools as `{{python}} .agentkit/bin/agentkit <command>`. The spec's status must be `frozen`.

1. Read `specs/NNN-*/progress.md` (resume point), `tasks.md`, the spec's API contract and
   docs/CODEMAP.md. Do not re-read the whole spec unless you need to.
2. Loop over the open tasks: run `test <scope>` for the relevant tests, change code, re-run,
   then tick the task in `tasks.md`.
3. Hard rules: never touch frozen files, never special-case test inputs, never weaken or skip
   tests. If a frozen test looks wrong, stop and explain it to the human. If something was
   changed by accident, run `lock restore`.
4. When targeted tests pass: run the full `test`, then `codemap` if public symbols changed.
5. **Review.** Delegate to the `impl-reviewer` role (or apply its checklist yourself) and fix
   the findings.
6. Commit `feat(NNN): <summary>`. When everything is green and reviewed, run
   `spec-status NNN done`.
7. If you stop before the end, run `handoff NNN --next "<next concrete step>"` first.
