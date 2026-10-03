---
id: "021"
title: Chaos autopilot skill
status: draft
depends: ["011", "020"]
---

# 021 Chaos autopilot skill

## Context

A `/autopilot NNN` skill and its role wiring, for repositories with chaos mode (020) on. It chains
spec → tests → freeze → implement → done in one run, with no stop for the owner. At each gate it
hands the work to the matching reviewer role, and the reviewer's verdict is the approval that
020 records. It stops only when 020 raises an escalation, and then tells the owner what is
blocked and why. With chaos mode off, the skill refuses and points to the normal per-phase skills.

The skill is instructions; an agent follows them. To keep the agent from deciding the order of
gates on its own, the next step comes from one read-only command, `agentkit autopilot NNN`, which
derives it from the spec's phase and the chaos state. The skill runs that command, does the step
it names, and runs it again. Because the step depends only on files, a run interrupted at any
point resumes with `/autopilot NNN` in a new session.

To keep the main context small, each phase's work goes to a subagent with the writer role
(spec-writer, test-writer, implementer, 011), and each review to a subagent with the reviewer
role. The main session keeps only step names, verdicts and paths.

## Requirements (EARS)

### Conventions
- "Chaos applies", "paused", "agent environment" and the exit codes are as in 020.
- `autopilot` functions raise `AutopilotError` for refusals that exit 1 and
  `AutopilotUsageError` (an `AutopilotError`) for those that exit 2. A malformed `[chaos]`
  table raises `ConfigError` (exit 2).
- The **review path** of a step is `.agentkit/state/autopilot/<NNN>-<gate>-<role>.md` under the
  root (repo-relative, `/` separators). The state directory is gitignored (R010-11) and writable
  by agents (R003-08); `chaos approve` copies the file into the spec folder (R020-14).

### The next step
- **R021-01** `autopilot.next_step(cfg, spec_id)` shall return the `Step` for the spec's phase:

  | Phase | `name` | `writer` | `reviewer` | `gate` |
  |---|---|---|---|---|
  | `draft` | `spec` | `spec-writer` | `spec-reviewer` | `approved` |
  | `approved` | `write-tests` | `test-writer` | `test-auditor` | `tests-approved` |
  | `tests-draft` | `review-tests` | `test-writer` | `test-auditor` | `tests-approved` |
  | `tests-approved` | `freeze` | `None` | `None` | `frozen` |
  | `frozen` | `implement` | `implementer` | `impl-reviewer` | `done` |
  | `done` | `done` | `None` | `None` | `None` |

  `review` is the review path of `<gate>` and `<reviewer>` when both are set, else `None`.
  `approve` is the command `agentkit chaos approve NNN <gate>` followed by ` --review <review>`
  when `review` is set, else `None`.
- **R021-02** For `write-tests`, the Step shall also set `set_phase` to `tests-draft`: the
  phase the skill sets with `agentkit spec-status` once the tests are written, before the
  review. For every other step `set_phase` is `None`.
- **R021-03** `next_step` shall check, in this order, stopping at the first failure:
  1. `ConfigError`: the `[chaos]` table is malformed (R020-02, R020-03);
  2. `AutopilotUsageError`: chaos mode is off, with the message
     `chaos mode is off: the owner approves gates; use /spec, /write-tests, /implement`;
  3. `AutopilotError`: spec NNN does not exist;
  4. `AutopilotError`: chaos does not apply to NNN (including `000`), saying that the spec is
     not under chaos mode;
  5. `AutopilotError`: the spec is `dropped`;
  6. `AutopilotError`: the chaos log fails R020-37 (the message names the line);
  7. `AutopilotError`: chaos mode is paused, listing each open escalation as
     `chaos.format_log` does, with the hint `owner: agentkit chaos log --open`;
  8. `AutopilotError`: the lock is violated (`lock.verify`), listing `<kind> <path>` per
     violation, with the hint `restore with agentkit lock restore or ask the owner`;
  9. `AutopilotError`: the phase is `frozen` and a `depends` entry names a spec that is not
     `done`, with the message `blocked by NNN[, MMM]` (as R006-13).
- **R021-04** `next_step` shall write nothing: no file under the root changes, and the chaos
  log is not appended to.
- **R021-05** `agentkit autopilot NNN` shall print the Step returned by `next_step`, one
  `key: value` line each, in this order: `step`, `gate`, `writer`, `reviewer`, `review`,
  `set-phase`, `then`, where `then` is `approve` and `None` prints `-`. It exits 0, also for
  `done`.
- **R021-06** When `next_step` raises `AutopilotError`, `agentkit autopilot NNN` shall print
  `blocked: <message>` and any listed lines, and exit 1 (2 for `AutopilotUsageError` and
  `ConfigError`).
- **R021-07** `agentkit autopilot` with no spec number, or with one that does not match
  `^\d{3}$`, shall exit 2.

### The skill
- **R021-08** The kit shall ship `skills/autopilot/SKILL.md` with `name: autopilot`, a
  `description` of at most 200 characters, and `metadata` `agentkit-tier: "standard"`,
  `agentkit-effort: "medium"`, `agentkit-user-only: "true"` and `agentkit-args: "NNN"`
  (R011-14). Only the owner starts a run.
- **R021-09** The skill shall refer to `{{python}} .agentkit/bin/agentkit autopilot`,
  `chaos approve`, `chaos unfreeze` and `spec-status`, and name each role of R021-01 (R011-18).
- **R021-10** The skill shall loop: run `agentkit autopilot NNN`; stop when it exits non-zero
  or prints `step: done`; otherwise do the step and run it again. It shall never choose a gate
  or a phase that the command did not print. [manual]
- **R021-11** For a step with a writer, the skill shall run the writer role as a subagent on
  the phase's work, following that phase's skill (`spec`, `write-tests`, `implement`) except
  its owner hand-over and approval steps. For `review-tests` the writer runs only to fix
  findings of a rejected review. It shall then set `set-phase` when one is printed. [manual]
- **R021-12** The skill shall then run the reviewer role as a subagent, write the subagent's
  final report unchanged to the printed review path, and run the printed `then` command. It
  shall never write, edit or shorten a review's verdict line. [manual]
- **R021-13** When `chaos approve` exits 1 with a `reject` record, the skill shall pass the
  review's findings to the writer subagent, then review and approve again (R021-11, R021-12).
  020 bounds this loop: `max_rejections` rejects in a row escalate and pause (R020-21). [manual]
- **R021-14** For `freeze`, the skill shall run the printed `then` command and nothing else. It
  shall not use the owner-only `freeze` skill. [manual]
- **R021-15** After each gate passes (the `then` command exits 0), the skill shall run the
  repository's checks for that phase (the full test suite after `done`), commit the phase's
  files together with the chaos log and the spec's `reviews/` folder, with the message type of
  AGENTS.md (`spec(NNN)`, `test(NNN)`, `feat(NNN)`), and run `/handoff NNN`. It shall never
  commit with `--no-verify`. [manual]
- **R021-16** The skill shall stop the run, change nothing more, and report to the owner when:
  - `agentkit autopilot` or a chaos command exits 2, or exits 1 with an `escalate` record
    (the report quotes the command's output);
  - a commit or its pre-commit hook fails twice in a row;
  - a reviewer subagent fails to return a report.
  The report says what is blocked, why, and the command for the owner
  (`agentkit chaos log --open` for an escalation). [manual]
- **R021-17** The skill shall never run `chaos clear`, `lock unfreeze`, `lock freeze --force`,
  or `spec-status` with `approved`, `tests-approved` or `done`, and never edit the chaos log,
  `reviews/` or a frozen file. [manual]
- **R021-18** During `implement`, when the implementer reports a frozen test that it judges
  wrong, the skill shall stop the implementer, run the test-auditor and then the impl-reviewer
  on that test with the reason, write both reports to
  `.agentkit/state/autopilot/<NNN>-unfreeze-<role>.md`, and run `agentkit chaos unfreeze`
  with them. When it exits 0, the spec is back in `tests-draft` and the loop goes on
  (R021-10); when it exits 1 with a `reject`, the implementer goes on without touching the
  test. At most one agent unfreeze per run; a second need stops the run (R021-16). [manual]
- **R021-19** Where the tool has no subagents, the skill shall do the writer's and the
  reviewer's work inline, from the role files, and after each gate passes run `/handoff NNN`,
  stop, and tell the owner to clear the context and run `/autopilot NNN` again. [manual]
- **R021-20** When the run ends with `step: done`, the skill shall report to the owner the
  gates passed in this run with their chaos log `seq`, the commits made, and any agent
  unfreeze. [manual]

### Documentation
- **R021-21** WORKFLOW.md's chaos-mode section (R020-35) shall describe `/autopilot`: who
  starts it, what it does at each phase, when it stops, and how to resume it. [manual]

## Public API contract

```text
agentkit/autopilot.py:
  class AutopilotError(Exception)              # exit 1
  class AutopilotUsageError(AutopilotError)    # exit 2
  STATE_DIR = ".agentkit/state/autopilot"
  @dataclass class Step:
      name: str                 # "spec" | "write-tests" | "review-tests" | "freeze" | "implement" | "done"
      gate: str | None
      writer: str | None
      reviewer: str | None
      review: str | None        # repo-relative review path
      set_phase: str | None     # "tests-draft" for write-tests
      approve: str | None       # the chaos approve command
  def next_step(cfg, spec_id: str) -> Step
      # raises ConfigError, AutopilotUsageError, AutopilotError (R021-03)
  def format_step(step: Step) -> list[str]     # R021-05
CLI: agentkit autopilot NNN
Files: skills/autopilot/SKILL.md (kit), rendered and synced like the other skills (010, 011)
```

The `approve` command is printed with the plain `agentkit` name; the skill runs it through
`{{python}} .agentkit/bin/agentkit` (R011-18).

## Examples and edge cases

`[chaos] enabled = true`, `specs = ["012"]`; 012 is `draft`, depends on `004` (done).

```text
$ agentkit autopilot 012
step: spec
gate: approved
writer: spec-writer
reviewer: spec-reviewer
review: .agentkit/state/autopilot/012-approved-spec-reviewer.md
set-phase: -
then: agentkit chaos approve 012 approved --review .agentkit/state/autopilot/012-approved-spec-reviewer.md
```

| Situation | `agentkit autopilot 012` |
|---|---|
| 012 `approved` | `step: write-tests`, `set-phase: tests-draft`, reviewer `test-auditor` |
| 012 `tests-approved` | `step: freeze`, `review: -`, `then: agentkit chaos approve 012 frozen` |
| 012 `frozen`, 004 `frozen` | exit 1, `blocked: blocked by 004` |
| 012 `done` | `step: done`, every other value `-`, exit 0 |
| chaos paused by escalation #3 | exit 1, `blocked: chaos mode is paused`, the `#3` line, the hint |
| `[chaos]` absent | exit 2, `blocked: chaos mode is off: …` |
| `agentkit autopilot 013` (not listed) | exit 1: 013 not under chaos mode |
| `agentkit autopilot 12` | exit 2 |

A full run of `/autopilot 012` from `draft`: spec-writer drafts, spec-reviewer reviews, `chaos
approve 012 approved` (commit `spec(012)`); test-writer writes tests, `spec-status 012
tests-draft`, test-auditor reviews, `chaos approve 012 tests-approved` (commit `test(012)`);
`chaos approve 012 frozen` (commit `test(012)`); implementer implements, impl-reviewer reviews,
`chaos approve 012 done` (commit `feat(012)`); report. A `/handoff 012` follows each commit. A rejection at any review sends the findings back to the writer;
the second in a row escalates and the run stops with the escalation.

- A run stopped by a crash or `/clear` resumes from the phase: `/autopilot 012` after `approved`
  starts at `write-tests`. A review file left from an earlier attempt is overwritten.
- An agent unfreeze sends 012 to `tests-draft`; the next step is `review-tests`, and the
  test-auditor reviews the changed tests before they are frozen again.

## Out of scope

- Running a spec's dependencies first. A blocked spec stops the run (R021-03).
- Running several specs in one run, or in parallel.
- Any new gate, check or log record: those are 020's.
- Proving that the subagents were independent (020, Out of scope).

## Amendments needed in other specs (for the owner to approve)

- **000**: the command list gains `autopilot` (021).
- **011**: R011-14 lists `autopilot`; R011-16 gives it standard/medium; R011-15's user-only
  flag also applies to `autopilot` (R021-08).
- **012**: R012-07's skill list in the CLAUDE.md block gains `/autopilot` (owner only, chaos
  mode), within its 20-line cap.

## Additions beyond plan.md

The whole spec is the owner's idea of 2026-10-03, not in plan.md. Design choices to approve:
- A read-only `agentkit autopilot NNN` command decides the next step, so the order of gates is
  code, not the agent's judgement, and a run resumes from files.
- Writers and reviewers run as subagents; the main session keeps only verdicts and paths.
- Review files live in `.agentkit/state/autopilot/` before `chaos approve` copies them.
- `/autopilot` is owner-only (`agentkit-user-only`), like `/freeze`: an agent never starts a
  run on its own.
- One commit and one `/handoff` per gate.
- At most one agent unfreeze per run (R021-18).
- A blocked dependency stops the run instead of running the dependency.
- Tier standard/medium for the orchestrator: the strong-tier work is in the subagents.

## Open questions

1. Agent unfreeze during a run (R021-18): allow one per run (as drafted), none (stop and ask the
   owner), or any number (020 bounds it through rejections)?
2. Should `/autopilot` with a blocked dependency that is itself under chaos mode run that
   dependency first (drafted: no, out of scope)?
3. Commit per gate (drafted), or one commit at the end of the run?
