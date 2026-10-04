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
   For where code lives, read `docs/CODEMAP.md` (`python3 -m agentkit codemap`) before searching.
   Open the full spec only for the requirement you are working on.
2. Loop over the open tasks:
   - run the targeted tests: `python3 -m agentkit test tests.test_NNN_<area>` (compact
     summary; the full log is in `.agentkit/state/last-test.log`);
   - change the code;
   - re-run until it passes, reading only the last lines and the `ERROR:`/`FAIL:` names of
     the output (hand long tracebacks to `summarizer`);
   - tick the task in `tasks.md`.
3. If a test looks wrong, stop and explain it to the owner. Never touch it. If a frozen file
   changed by accident, restore it with `git checkout -- <path>`.
4. When the targeted tests pass, run the full suite with `python3 -m agentkit test`. Earlier
   specs must stay green.
5. **Review.** Run the `impl-reviewer` role as a subagent (or apply `roles/impl-reviewer.md`
   inline). Fix its findings.
   At most two passes: the first is a full review; the second gets only the saved first
   review (a file path) and the fix commit, not a pasted copy. A third pass needs a new
   blocking finding in the second.
6. Commit `feat(NNN): <summary>`. When everything is green and reviewed, set `status: done`.
7. If you stop before the end, run `/handoff NNN` first.

Small specs (spec.md up to about 80 lines) in chaos mode may run tests, freeze and implement in
one session with one handoff at the end.
