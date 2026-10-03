---
id: "021"
title: Chaos autopilot skill
status: draft
depends: ["002", "005", "011", "020"]
---

# 021 Chaos autopilot skill

## Context

A `/autopilot NNN` skill and its role wiring, for repositories with chaos mode (020) on. It chains
spec → tests → freeze → implement → done in one run, with no stop for the owner. At each gate it
hands the work to the matching reviewer role, and the reviewer's verdict is the approval that
020 records. It stops when 020 raises an escalation or when anything else goes wrong that it is
not allowed to fix (R021-16), and then tells the owner what is blocked and why. With chaos mode
off, it refuses and points to the normal per-phase skills.

The skill is instructions; an agent follows them. To keep the agent from deciding the order of
gates on its own, the next step comes from one read-only command, `agentkit autopilot NNN`, which
derives it from the spec's phase and the chaos log. The skill runs that command, does the step
it names, and runs it again. Because the step, the findings to fix and the last outcome all come
from files, a run interrupted at any point resumes with `/autopilot NNN` in a new session.

To keep the main context small, each phase's work goes to a subagent with the writer role
(spec-writer, test-writer, implementer, 011), and each review to a subagent with the reviewer
role. The main session sees each review report once, to save it, and then keeps only step
names, verdicts and paths.

## Requirements (EARS)

### Conventions
- "Chaos applies", "paused", "base commit", "agent environment" and the exit codes are as in 020.
- `autopilot` functions raise `AutopilotError` for refusals that exit 1 and
  `AutopilotUsageError` (an `AutopilotError`) for those that exit 2. Each carries `message`
  (one line, also its `str()`), `lines` (list of detail lines, possibly empty) and `hint` (a
  string, possibly empty). A malformed `[chaos]` table raises `ConfigError` (exit 2).
- The **work directory** is `<root>/.autopilot/`. It is gitignored (R010-11, amended) and
  matches no deny rule of the guard (R003-09) or of an adapter (R012-03), so the main session
  can write review files there. `chaos approve` copies each review into the spec folder
  (R020-14).
- The **review path** of a gate and role is `.autopilot/<NNN>-<gate>-<role>.md`
  (repo-relative, `/` separators).
- The spec's **records** are the chaos log records whose `spec` is NNN, in log order.

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
  `approve` is `agentkit chaos approve NNN <gate>` followed by ` --review <review>` when
  `review` is set; it is `None` for `done`.
- **R021-02** For `write-tests`, `set_phase` shall be `tests-draft`: the phase the skill sets
  with `agentkit spec-status` once the tests are written, before the review. For every other
  step it is `None`.
- **R021-22** `last` shall be `#<seq> <kind>` of the spec's newest record, or `None` when it
  has none.
- **R021-23** `findings` shall be the stored review paths (`reviews[*].review`, R020-09) of the
  spec's newest record when that record is a `reject` whose gate is the step's gate, or an
  `unfreeze` while the phase is `tests-draft`; otherwise `[]`. With an `unfreeze`, `reason` is
  that record's `reason`; otherwise `reason` is `None`.
- **R021-24** `unfreezes` shall count the spec's `unfreeze` records newer than the newest
  `clear` record in the log (all of them when there is none).
- **R021-03** `next_step` shall check, in this order, stopping at the first failure (messages
  exact, `NNN` the spec number):
  1. `ConfigError`: the `[chaos]` table is malformed (R020-02, R020-03);
  2. `AutopilotUsageError`: chaos mode is off: `chaos mode is off: the owner approves gates`,
     hint `use /spec, /write-tests, /implement`;
  3. `AutopilotUsageError`: the root is not a git repository: `not a git repository`;
  4. `AutopilotError`: the chaos log fails R020-37: the `ChaosError` message;
  5. `AutopilotUsageError`: there is no base commit: `no base commit`, hint
     `commit agentkit.toml`;
  6. `AutopilotError`: two spec folders share NNN (R005-19): `duplicate spec number NNN`, lines
     the two folders; spec NNN does not exist: `spec NNN does not exist`;
  7. `AutopilotError`: chaos does not apply to NNN (including `000`):
     `spec NNN is not under chaos mode`;
  8. `AutopilotError`: the phase is `dropped`: `spec NNN is dropped`; or not a phase of
     R005-03: `spec NNN has unknown phase <status>`;
  9. `AutopilotError`: chaos mode is paused: `chaos mode is paused: <k> open escalation(s)`,
     lines `chaos.format_log(<open escalations>, open_only=True)`, hint
     `owner: agentkit chaos log --open`;
  10. `AutopilotError`: the lock cannot be read (`LockError`): `lock unreadable: <error>`; or
      `lock.verify` reports violations: `lock violated: <k> file(s)`, lines `<kind> <path>`
      sorted by path, hint `restore with agentkit lock restore or ask the owner`;
  11. `AutopilotError`: the phase is `frozen` and a `depends` entry names a spec that is not
      `done` or does not exist: `blocked by NNN[, MMM]` (the entries in front-matter order).
- **R021-04** `next_step` shall write nothing: no file under the root changes, and the chaos
  log is not appended to.
- **R021-05** `agentkit autopilot NNN` shall print to stdout the Step, one `key: value` line
  each, in this order: `step`, `gate`, `writer`, `reviewer`, `review`, `set-phase`, `then`
  (the `approve` command), `last`, `findings` (paths joined by `, `), `reason`,
  `unfreezes`. `None` and an empty list print `-`. It exits 0, also for `done`.
- **R021-06** When `next_step` raises, `agentkit autopilot NNN` shall print to stdout
  `blocked: <message>`, then each detail line indented by two spaces, then `hint: <hint>` when
  the hint is not empty; for `ConfigError` the message is the error text and there is no hint.
  It exits 1 for `AutopilotError`, 2 for `AutopilotUsageError` and `ConfigError`.
- **R021-07** `agentkit autopilot` with no spec number, more than one, or one that does not
  match `^\d{3}$`, shall print `usage: agentkit autopilot NNN` to stderr and exit 2.

### The skill
- **R021-08** The kit shall ship `skills/autopilot/SKILL.md` with `name: autopilot`, a
  `description` of at most 200 characters that starts with `OWNER ONLY.`, and `metadata`
  `agentkit-tier: "standard"`, `agentkit-effort: "medium"`, `agentkit-user-only: "true"` and
  `agentkit-args: "NNN"` (R011-14). Adapters that translate `agentkit-user-only` (012) keep
  agents from starting a run; elsewhere the description is the only guard.
- **R021-09** The skill shall contain `{{python}} .agentkit/bin/agentkit autopilot`,
  `chaos approve`, `chaos unfreeze`, `spec-status` and `.autopilot/`, and name each role of
  R021-01 (R011-18).
- **R021-10** The skill shall loop: run `agentkit autopilot NNN`; stop when it exits non-zero
  or prints `step: done`; otherwise do the step (R021-11 to R021-15) and run it again. It shall
  never choose a gate or a phase that the command did not print. [manual]
- **R021-11** For a step with a writer, the skill shall run the writer role as a subagent, and
  give it the path of the phase's SKILL.md (`spec`, `write-tests`, `implement`), the spec
  number, and the `findings` and `reason` printed, if any. The writer follows that skill but
  skips its review, owner hand-over, status-change and commit steps, and works from the
  findings when there are any. For `review-tests` the writer runs only when `findings` is not
  `-`. A spec-writer lists open questions without guessing answers; the spec-reviewer judges
  whether one needs the owner (R020-43). A test-writer that finds the approved spec wrong or
  incomplete reports it instead of writing around it, and the run stops (R021-16). The skill
  then sets `set-phase` when one is printed. [manual]
- **R021-12** The skill shall then run the reviewer role as a subagent, write the subagent's
  final report unchanged to the printed review path, and run the printed `then` command. It
  shall never write, edit or shorten a review's verdict line. When `then` exits 2 because the
  verdict line is invalid (R020-13), the skill shall ask the reviewer once for the same report
  ending with exactly one verdict line, and stop on a second failure. [manual]
- **R021-13** After running `then`, the skill shall decide by its exit code and by `last`
  from a new `agentkit autopilot NNN`:
  - exit 0: the gate passed (R021-15);
  - exit 1 and `last` names a `reject` newer than the `last` seen before `then`: the loop goes
    on, and the writer works from the new `findings` (R021-11). 020 bounds this:
    `max_rejections` rejects in a row escalate and pause (R020-21);
  - anything else: the run stops (R021-16). [manual]
- **R021-14** For `freeze`, the skill shall run the printed `then` command and nothing else. It
  shall not use the owner-only `freeze` skill. [manual]
- **R021-15** After a gate passes, the skill shall update `progress.md` as the `handoff` skill
  says (without its commit step), stage every change (`git add -A`; the chaos log and the
  spec's `reviews/` included) and commit with the type of the gate: `approved` → `spec(NNN)`,
  `tests-approved` and `frozen` → `test(NNN)`, `done` → `feat(NNN)`; an agent unfreeze →
  `test(NNN): agent unfreeze`. After `done` it first runs the full test suite; when the suite
  fails, it commits nothing and stops (R021-16). It shall never commit with `--no-verify`.
  [manual]
- **R021-16** The skill shall stop the run, change nothing more, and report to the owner when:
  - `agentkit autopilot` exits non-zero (the report quotes its output);
  - a chaos command ends other than as R021-13 continues (the report quotes its output, and
    names the escalation when `last` is an `escalate`);
  - the same `step` and `last` come back after a full iteration of R021-10;
  - a writer or reviewer subagent returns no report, or a test-writer reports a spec gap;
  - a commit fails twice in a row, or the full suite fails after `done`;
  - a second agent unfreeze would be needed (R021-18).

  The report says what is blocked, why, and the command for the owner
  (`agentkit chaos log --open` for an escalation). [manual]
- **R021-17** The skill shall never run `chaos clear`, `lock unfreeze`, `lock freeze --force`,
  or `spec-status` with `approved`, `tests-approved` or `done`, and never edit the chaos log,
  `reviews/` or a frozen file. [manual]
- **R021-18** During `implement`, when the implementer reports a frozen test that it judges
  wrong, the skill shall stop the implementer. When `unfreezes` is 1 or more, the run stops
  (R021-16). Otherwise it runs the test-auditor and then the impl-reviewer on that test with
  the implementer's reason, writes their reports to `.autopilot/<NNN>-unfreeze-<role>.md`, and
  runs `agentkit chaos unfreeze` with them. On exit 0 it commits (R021-15), and the loop goes on
  at `review-tests`, where the test-writer fixes the test from the unfreeze `findings` and
  `reason` before the review. On exit 1 with a new `reject`, the implementer goes on without
  touching the test. Anything else stops the run. [manual]
- **R021-19** Where the tool has no subagents, the skill shall do the writer's and the
  reviewer's work inline, from the role files, and after each gate passes and is committed,
  stop and tell the owner to clear the context and run `/autopilot NNN` again. [manual]
- **R021-20** When the run ends with `step: done`, the skill shall report to the owner the
  gates passed in this run with their chaos log `seq`, the commits made, and any agent
  unfreeze. [manual]

### Documentation
- **R021-21** WORKFLOW.md's chaos-mode section (R020-35) shall describe `/autopilot`: who
  starts it, what it does at each phase, when it stops, and how to resume it. [manual]
- **R021-25** WORKFLOW.md shall contain the string `/autopilot`.

## Public API contract

```text
agentkit/autopilot.py:
  class AutopilotError(Exception)              # exit 1; .message, .lines, .hint
      def __init__(self, message: str, lines: list[str] | None = None, hint: str = "")
  class AutopilotUsageError(AutopilotError)    # exit 2
  WORK_DIR = ".autopilot"
  @dataclass class Step:
      name: str                 # "spec" | "write-tests" | "review-tests" | "freeze" | "implement" | "done"
      gate: str | None
      writer: str | None
      reviewer: str | None
      review: str | None        # repo-relative review path
      set_phase: str | None     # "tests-draft" for write-tests
      approve: str | None       # the chaos approve command
      last: str | None          # "#<seq> <kind>" (R021-22)
      findings: list[str]       # R021-23
      reason: str | None        # R021-23
      unfreezes: int            # R021-24
  def next_step(cfg, spec_id: str) -> Step
      # raises ConfigError, AutopilotUsageError, AutopilotError (R021-03)
  def format_step(step: Step) -> list[str]     # R021-05
CLI: agentkit autopilot NNN
Changed: agentkit/cli.py (the `autopilot` subcommand)
Files: skills/autopilot/SKILL.md (kit), rendered and synced like the other skills (010, 011)
```

The `approve` command is printed with the plain `agentkit` name; the skill runs it through
`{{python}} .agentkit/bin/agentkit` (R011-18).

## Examples and edge cases

`[chaos] enabled = true`, `specs = ["012"]`; 012 is `draft`, depends on `004` (done); the log
is empty.

```text
$ agentkit autopilot 012
step: spec
gate: approved
writer: spec-writer
reviewer: spec-reviewer
review: .autopilot/012-approved-spec-reviewer.md
set-phase: -
then: agentkit chaos approve 012 approved --review .autopilot/012-approved-spec-reviewer.md
last: -
findings: -
reason: -
unfreezes: 0
```

| Situation | `agentkit autopilot 012` |
|---|---|
| 012 `draft`, newest 012 record `#4 reject` of `approved` | `step: spec`, `last: #4 reject`, `findings: specs/012-…/reviews/4-approved-spec-reviewer.md` |
| 012 `approved` | `step: write-tests`, `set-phase: tests-draft`, reviewer `test-auditor` |
| 012 `tests-draft`, newest 012 record `#9 unfreeze` | `step: review-tests`, the two unfreeze reviews as `findings`, its `reason`, `unfreezes: 1` |
| 012 `tests-approved` | `step: freeze`, `review: -`, `then: agentkit chaos approve 012 frozen` |
| 012 `frozen`, 004 `frozen` | exit 1, `blocked: blocked by 004` |
| 012 `done` | `step: done`, `then: -`, exit 0 |
| chaos paused by escalation #3 | exit 1: `blocked: chaos mode is paused: 1 open escalation(s)`, the `#3` line and its detail indented, `hint: owner: agentkit chaos log --open` |
| `[chaos]` absent | exit 2: `blocked: chaos mode is off: the owner approves gates`, `hint: use /spec, /write-tests, /implement` |
| `agentkit autopilot 013` (not listed) | exit 1: `blocked: spec 013 is not under chaos mode` |
| `agentkit autopilot 12` | exit 2, usage on stderr |

A full run of `/autopilot 012` from `draft`: spec-writer drafts, spec-reviewer reviews, `chaos
approve 012 approved` (commit `spec(012)`); test-writer writes tests, `spec-status 012
tests-draft`, test-auditor reviews, `chaos approve 012 tests-approved` (commit `test(012)`);
`chaos approve 012 frozen` (commit `test(012)`); implementer implements, impl-reviewer reviews,
the full suite passes, `chaos approve 012 done` (commit `feat(012)`); report. Each commit
includes the updated `progress.md`. A rejection sends the findings back to the writer; the
second in a row escalates, and the run stops and reports the escalation.

- `chaos approve 012 tests-approved` exits 1 because `trace` fails (R020-17): no record is
  written, `last` is unchanged, so the run stops (R021-13) instead of looping.
- A run stopped by a crash or `/clear` resumes from files: `/autopilot 012` after a reject at
  `approved` gives `step: spec` with that reject's review as `findings`. A review file left in
  `.autopilot/` from an earlier attempt is overwritten.

## Out of scope

- Running a spec's dependencies first. A blocked spec stops the run (R021-03).
- Running several specs in one run, or in parallel.
- Any new gate, check or log record: those are 020's.
- Proving that the subagents were independent (020, Out of scope).

## Amendments needed in other specs (for the owner to approve)

- **000**: the command list gains `autopilot` (021).
- **010**: R010-11's `.gitignore` block gains `.autopilot/`.
- **011**: Context counts 8 Agent Skills; R011-14 lists `autopilot`; R011-16 gives it
  standard/medium; R011-15's user-only flag also applies to `autopilot` (R021-08); R011-01's
  WORKFLOW.md covers `/autopilot` (R021-21, R021-25).
- **012**: R012-07's skill list in the CLAUDE.md block gains `/autopilot` (owner only, chaos
  mode), within its 20-line cap.

## Additions beyond plan.md

The whole spec is the owner's idea of 2026-10-03, not in plan.md. Design choices to approve:
- A read-only `agentkit autopilot NNN` command decides the next step, the findings to fix and
  the last outcome, so the order of gates is code, not the agent's judgement, and a run resumes
  from files. Its `blocked:` output and check order (R021-03, R021-06).
- The `review-tests` step, where the test-writer runs only to fix findings.
- Writers and reviewers run as subagents; the main session keeps only verdicts and paths.
- Review files are written to a gitignored `.autopilot/` folder (Claude Code denies edits under
  `.agentkit/`) before `chaos approve` copies them.
- `/autopilot` is owner-only (`agentkit-user-only`), like `/freeze`.
- One commit per gate, with `progress.md` in it; stop on any outcome that is not a pass or a
  fresh reject (R021-13, R021-16).
- At most one agent unfreeze per spec until the owner's next `clear` (R021-18, R021-24).
- One retry of a reviewer whose verdict line is invalid (R021-12).
- A blocked dependency stops the run instead of running the dependency.
- Without subagents, one gate per session (R021-19).
- Tier standard/medium for the orchestrator: the strong-tier work is in the subagents.

## Open questions

1. Agent unfreeze during a run (R021-18): allow one per spec until the owner's next `clear` (as
   drafted), none (stop and ask the owner), or any number (020 bounds it through rejections)?
2. Should `/autopilot` with a blocked dependency that is itself under chaos mode run that
   dependency first (drafted: no, out of scope)?
3. Commit per gate (drafted), or one commit at the end of the run?
