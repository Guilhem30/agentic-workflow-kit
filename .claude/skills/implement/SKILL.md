---
name: implement
description: Implement a spec whose tests are frozen, task by task, until all its tests pass, then review for test gaming. Use for specs in phase frozen.
argument-hint: "NNN"
model: sonnet
effort: medium
---
<!-- generated from .agents/skills/implement/SKILL.md by the bootstrap sync (ADR 0001); edit the source -->
# Implementation phase

The spec must be `frozen` (during the bootstrap, 001 and 002 are implemented at
`tests-approved`; see ADR 0001). The frozen tests are the oracle.

1. Read `specs/NNN-*/progress.md` (resume point), `tasks.md` and the spec's API contract.
   Open the full spec only for the requirement you are working on.
2. Loop over the open tasks:
   - run the targeted test module;
   - change the code;
   - re-run until it passes;
   - tick the task in `tasks.md`.
3. If a test looks wrong, stop and explain it to the owner. Never touch it. If a frozen file
   changed by accident, restore it with `git checkout -- <path>`.
4. When the targeted tests pass, run the full suite. Earlier specs must stay green.
5. **Review.** Run the `impl-reviewer` role as a subagent (or apply `roles/impl-reviewer.md`
   inline). Fix its findings.
6. Commit `feat(NNN): <summary>`. When everything is green and reviewed, set `status: done`.
7. If you stop before the end, run `/handoff NNN` first.
