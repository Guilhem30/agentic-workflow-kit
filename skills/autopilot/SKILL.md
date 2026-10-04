---
name: autopilot
description: OWNER ONLY. In chaos mode, run a spec and its unfinished dependencies from draft to done through writer and reviewer subagents. Stops on any escalation.
metadata:
  agentkit-tier: standard
  agentkit-effort: medium
  agentkit-user-only: "true"
  agentkit-args: "NNN"
---
# Autopilot

Run this only when the owner invoked it for spec NNN, and only where chaos mode is on. With
chaos mode off, refuse and point to the per-phase skills (`/spec`, `/write-tests`, `/freeze`,
`/implement`). Dependencies that are not `done` are worked first. A run interrupted at any
point resumes with `/autopilot NNN`: the state is in files.

**Loop.** Run `{{python}} .agentkit/bin/agentkit autopilot NNN`. Stop when it exits non-zero or
prints `step: done`. Otherwise do the step it printed, then run it again. Never choose a spec,
gate or phase it did not print. `WWW` below is the printed `spec`, which may be a dependency.

1. **Writer.** For a step with a `writer` role, run that role (`spec-writer`, `test-writer` or
   `implementer`) as a subagent. Give it the phase skill's path (`spec`, `write-tests` or
   `implement`), WWW, and the printed `findings` and `reason`. It skips that skill's review,
   hand-over, status and commit steps. For `review-tests` it runs only when `findings` is not
   `-`. A spec-writer lists open questions without guessing. A test-writer that finds the spec
   wrong reports it and the run stops. Then run the
   printed `set-phase` with `{{python}} .agentkit/bin/agentkit spec-status`, if one is printed.
2. **Reviewer.** Run the `reviewer` role (`spec-reviewer`, `test-auditor` or `impl-reviewer`)
   as a subagent and write its final report, unchanged, to the printed review path under
   `.autopilot/`. For `implement`, when the verdict passes, run the full suite
   (`{{python}} .agentkit/bin/agentkit test`) and stop if it fails. Never write, edit or shorten
   a verdict line. If `then` exits 2 on an invalid verdict line, ask the reviewer once for the same
   report ending with exactly one verdict line; stop on a second failure.
3. **Gate.** Run the printed `then` command (`chaos approve`), then the autopilot command again
   to read `last`. Exit 0: the gate passed. Exit 1 with a new `reject` in `last`: go on, and the writer works from the new `findings`. Anything
   else stops the run. For `freeze`, run `then` and nothing else; never use the `freeze` skill.
4. **Record.** After a gate passes, update `progress.md` as the `handoff` skill says (without
   its commit step), `git add -A`, and commit with the gate's type: `approved` → `spec(WWW)`,
   `tests-approved` and `frozen` → `test(WWW)`, `done` → `feat(WWW)`. Never use `--no-verify`.

**Frozen test judged wrong.** The implementer stops and names the test files and its reason.
If a file does not belong to WWW in the lock, or this run already made one agent unfreeze,
stop. Otherwise run the `test-auditor` and then the `impl-reviewer` on those tests, save their
reports to `.autopilot/WWW-unfreeze-<role>.md`, and run
`{{python}} .agentkit/bin/agentkit chaos unfreeze <paths> --reason "<reason>"
--auditor-review .autopilot/WWW-unfreeze-test-auditor.md
--impl-review .autopilot/WWW-unfreeze-impl-reviewer.md`. On exit 0 commit
(`test(WWW): agent unfreeze`) and the loop goes on at `review-tests`. On exit 1 with a new
`reject`, the implementer goes on without touching the tests, given the stored reviews.

**Stop and report** to the owner, changing nothing more, when: the command exits non-zero; a
chaos command ends other than as above; the same `spec`, `step` and `last` return after a full
iteration; a subagent returns no report; a commit fails twice or the full suite fails before
`done`; or a second agent unfreeze would be needed. Say what is blocked and why, quoting the
command output and the `blocked:` lines, and give the owner's command (`chaos log --open` for an escalation).

**Never** run `chaos clear`, `lock unfreeze`, `lock freeze --force`, or `spec-status` with
`approved`, `tests-approved`, `done` or `dropped`. Never edit the chaos log, `reviews/` or a
frozen file.

**No subagents.** Do the writer's and reviewer's work inline from the role files in
`{{roles}}/`. After each gate passes and is committed, stop and tell the owner to clear the
context and run `/autopilot NNN` again.

**Done.** On `step: done`, report per spec of the chain: the gates passed with their chaos log
`seq`, the commits made and any agent unfreeze.
