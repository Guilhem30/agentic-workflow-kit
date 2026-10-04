---
id: "021"
title: Chaos autopilot skill
status: approved
depends: ["001", "002", "005", "006", "007", "011", "020"]
---

# 021 Chaos autopilot skill

## Context

A `/autopilot NNN` skill and its role wiring, for repositories with chaos mode (020) on. It chains
spec → tests → freeze → implement → done in one run, with no stop for the owner, after doing the
same for each dependency that is not `done` yet (owner's decision, 2026-10-03). At each gate it
hands the work to the matching reviewer role, and the reviewer's verdict is the approval that
020 records. It stops when 020 raises an escalation or when anything else goes wrong that it is
not allowed to fix (R021-16), and then tells the owner what is blocked and why. With chaos mode
off, it refuses and points to the normal per-phase skills.

The skill is instructions; an agent follows them. To keep the agent from deciding the order of
gates on its own, the next step comes from one read-only command, `agentkit autopilot NNN`, which
derives it from the phases of the spec and its dependencies and from the chaos log. The skill
runs that command, does the step
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
- The **walk** starts at the target NNN. At each spec it checks the spec (R021-03 item 6),
  then visits its `depends` entries (R005-20) in front-matter order, skipping specs already
  finished; an entry that is on the current path is a cycle. A spec is finished when all its
  entries are. The **chain** is the specs in the order they finish (depth-first post-order),
  so NNN is last. For `012` depending on `004` and `010`, where `004` depends on `003`: `003`,
  `004`, `010`, `012`.
- The **working spec** is the first spec of the chain whose phase is not `done`, or NNN when
  every spec of the chain is `done`. The step is for the working spec; below, "the spec" and
  `WWW` mean the working spec.
- The spec's **records** are the chaos log records whose `spec` is the working spec, in log
  order.
- The **full suite** is `{{python}} .agentkit/bin/agentkit test` (R007-01) in the skill, and
  passes when it exits 0.

### The next step
- **R021-01** `autopilot.next_step(cfg, spec_id)` shall return the `Step` for the working
  spec of `spec_id`'s chain (`spec` = the working spec's number) and its phase:

  | Phase | `name` | `writer` | `reviewer` | `gate` |
  |---|---|---|---|---|
  | `draft` | `spec` | `spec-writer` | `spec-reviewer` | `approved` |
  | `approved` | `write-tests` | `test-writer` | `test-auditor` | `tests-approved` |
  | `tests-draft` | `review-tests` | `test-writer` | `test-auditor` | `tests-approved` |
  | `tests-approved` | `freeze` | `None` | `None` | `frozen` |
  | `frozen` | `implement` | `implementer` | `impl-reviewer` | `done` |
  | `done` | `done` | `None` | `None` | `None` |

  `review` is the review path of `<gate>` and `<reviewer>` when both are set, else `None`.
  The review path uses WWW. `approve` is `agentkit chaos approve WWW <gate>` followed by
  ` --review <review>` when
  `review` is set; it is `None` for `done`.
- **R021-02** For `write-tests`, `set_phase` shall be `tests-draft`: the phase the skill sets
  with `agentkit spec-status` once the tests are written, before the review. For every other
  step it is `None`.
- **R021-22** `last` shall be `#<seq> <kind>` of the spec's newest record, or `None` when it
  has none.
- **R021-23** Let R be the spec's newest record that is not an `escalate`. `findings` shall be
  the stored review paths (`reviews[*].review`, R020-09) of R when R is a `reject` whose gate is
  the step's gate, or an `unfreeze` while the phase is `tests-draft`; otherwise `[]`. With an
  `unfreeze`, `reason` is R's `reason`; otherwise `reason` is `None`. (An escalation after a
  reject, and the owner's `clear`, which has no `spec`, keep the findings.)
- **R021-24** [removed] (the unfreeze limit is per run, R021-18, which only the skill knows)
- **R021-03** `next_step` shall check, in this order, stopping at the first failure (messages
  exact, `NNN` the target, `WWW` the working spec):
  1. `ConfigError`: the `[chaos]` table is malformed (R020-02, R020-03);
  2. `AutopilotUsageError`: chaos mode is off: `chaos mode is off: the owner approves gates`,
     hint `use /spec, /write-tests, /implement`;
  3. `AutopilotUsageError`: the root is not a git repository: `not a git repository`;
  4. `AutopilotError`: the chaos log fails R020-37: the `ChaosError` message;
  5. `AutopilotUsageError`: there is no base commit: `no base commit`, hint
     `commit agentkit.toml`;
  6. `AutopilotError`, during the walk, at the first spec MMM (reached from spec PPP, for a
     dependency) where: two or more spec folders share its number (R005-19):
     `duplicate spec number MMM`, lines each folder's repo-relative path with `/` separators,
     sorted; it does not exist: `spec MMM does not exist`, with ` (needed by PPP)` for a
     dependency; an entry is on the current path: `dependency cycle: AAA -> … -> AAA`, the
     path from that entry back to it (a self-dependency is `dependency cycle: AAA -> AAA`);
  7. `AutopilotError`: chaos does not apply to NNN (including `000`):
     `spec NNN is not under chaos mode`;
  8. `AutopilotError`: the first spec of the chain that is `dropped`: `spec MMM is dropped`,
     with ` (needed by PPP)` for a dependency, PPP the spec that first listed it; the working
     spec's phase is not a phase of R005-03: `spec WWW has unknown phase <status>`; chaos does
     not apply to the working spec: `spec WWW is not under chaos mode`, the line
     `needed by PPP` and the hint `the owner finishes WWW, or lists it in [chaos] specs`;
  9. `AutopilotError`: chaos mode is paused: `chaos mode is paused: <k> open escalation(s)`,
     lines `chaos.format_log(<open escalations>, open_only=True)`, hint
     `owner: agentkit chaos log --open`;
  10. `AutopilotError`: the lock cannot be read (`LockError`): `lock unreadable: <error>`; or
      `lock.verify` reports violations: `lock violated: <k> file(s)`, lines `<kind> <path>`
      sorted by path, hint `restore with agentkit lock restore or ask the owner`;
  11. [removed] (by the chain order, the working spec's dependencies are all `done`.)
- **R021-04** `next_step` shall write nothing: no file under the root outside `.git/` changes,
  and the chaos log is not appended to.
- **R021-05** `agentkit autopilot NNN` shall print to stdout the Step, one `key: value` line
  each, in this order: `spec`, `step`, `gate`, `writer`, `reviewer`, `review`, `set-phase`,
  `then` (the `approve` command), `last`, `findings` (paths joined by `, `), `reason`. `None` and an empty list print `-`. It exits 0, also for `done`.
- **R021-06** When `next_step` raises, `agentkit autopilot NNN` shall print to stdout
  `blocked: <message>`, then each detail line with two more spaces in front (so an escalation
  line of `format_log` starts at 2 spaces and its detail lines at 4), then `hint: <hint>` when
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
  never choose a spec, a gate or a phase that the command did not print. Every step works on
  the printed `spec` (written `WWW` below), which may be a dependency of NNN. [manual]
- **R021-11** For a step with a writer, the skill shall run the writer role as a subagent, and
  give it the path of the phase's SKILL.md (`spec`, `write-tests`, `implement`), WWW, and the `findings` and `reason` printed, if any. The writer follows that skill but
  skips its review, owner hand-over, status-change and commit steps, and works from the
  findings when there are any. For `review-tests` the writer runs only when `findings` is not
  `-`. A spec-writer lists open questions without guessing answers; the spec-reviewer judges
  whether one needs the owner (R020-43). A test-writer that finds the approved spec wrong or
  incomplete reports it instead of writing around it, and the run stops (R021-16). The skill
  then sets `set-phase` when one is printed. [manual]
- **R021-12** The skill shall then run the reviewer role as a subagent and write the
  subagent's final report unchanged to the printed review path. For `implement`, when the
  verdict passes, it then runs the full suite and stops the run when the suite fails
  (R021-16). Then it runs the printed `then` command. It
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
  spec's `reviews/` included) and commit with the type of the gate: `approved` → `spec(WWW)`,
  `tests-approved` and `frozen` → `test(WWW)`, `done` → `feat(WWW)`; an agent unfreeze →
  `test(WWW): agent unfreeze` (this commit also holds the implementer's work in progress). It
  shall never commit with `--no-verify`. [manual]
- **R021-16** The skill shall stop the run, change nothing more, and report to the owner when:
  - `agentkit autopilot` exits non-zero (the report quotes its output);
  - a chaos command ends other than as R021-13 continues (the report quotes its output and the
    `blocked:` lines of a new `agentkit autopilot NNN`);
  - the same `spec`, `step` and `last` come back after a full iteration of R021-10;
  - a writer or reviewer subagent returns no report, or a test-writer reports a spec gap;
  - a commit fails twice in a row, or the full suite fails before `done` (R021-12);
  - a second agent unfreeze would be needed (R021-18).

  The report says what is blocked, why, and the command for the owner
  (`agentkit chaos log --open` for an escalation; `agentkit lock unfreeze <path> --reason …`
  for a second unfreeze). [manual]
- **R021-17** The skill shall never run `chaos clear`, `lock unfreeze`, `lock freeze --force`,
  or `spec-status` with `approved`, `tests-approved`, `done` or `dropped`, and never edit the
  chaos log, `reviews/` or a frozen file. [manual]
- **R021-18** During `implement`, the implementer stops and reports when it judges a frozen
  test wrong, naming the test files and its reason. When a file does not belong to WWW in the
  lock (another spec's test, or no spec), the run stops (R021-16). An agent unfreeze lets the test be
  modified: it leaves the lock, the test-writer fixes it, and it is audited and frozen again.
  When this run already made one agent unfreeze (for any spec of the chain), the run stops
  (R021-16): one agent unfreeze per run (owner's decision, 2026-10-03); a new `/autopilot` run
  may make another.
  Otherwise the skill runs the test-auditor and then the impl-reviewer on those tests with the
  reason, writes their reports to `.autopilot/<WWW>-unfreeze-<role>.md`, and runs
  `agentkit chaos unfreeze <paths> --reason "<reason>" --auditor-review
  .autopilot/<WWW>-unfreeze-test-auditor.md --impl-review
  .autopilot/<WWW>-unfreeze-impl-reviewer.md`. On exit 0 it commits (R021-15), and the loop goes
  on at `review-tests`, where the test-writer fixes the tests from the unfreeze `findings` and
  `reason` before the review. On exit 1 with a new `reject` (`last`), the implementer goes on
  without touching the tests and is given that reject's stored reviews
  (`<WWW spec dir>/reviews/<seq>-unfreeze-<role>.md`, R020-14). Anything else stops the run.
  [manual]
- **R021-19** Where the tool has no subagents, the skill shall do the writer's and the
  reviewer's work inline, from the role files, and after each gate passes and is committed,
  stop and tell the owner to clear the context and run `/autopilot NNN` again. [manual]
- **R021-20** When the run ends with `step: done`, the skill shall report to the owner, per
  spec of the chain worked on in this run, the gates passed with their chaos log `seq`, the
  commits made, and any agent unfreeze. [manual]

### Documentation
- **R021-21** WORKFLOW.md's chaos-mode section (R020-35) shall describe `/autopilot`: who
  starts it, the dependencies first, what it does at each phase, when it stops, and how to
  resume it. [manual]
- **R021-25** WORKFLOW.md shall contain the string `/autopilot`.

## Public API contract

```text
agentkit/autopilot.py:
  class AutopilotError(Exception)              # exit 1; .message, .lines, .hint
      def __init__(self, message: str, lines: list[str] | None = None, hint: str = "")
  class AutopilotUsageError(AutopilotError)    # exit 2
  WORK_DIR = ".autopilot"
  @dataclass class Step:
      spec: str                 # the working spec (R021-01)
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

`[chaos] enabled = true`, `specs = ["004", "012"]`; 012 is `draft`, depends on `004` (done),
whose own dependencies are `done`; the log is empty.

```text
$ agentkit autopilot 012
spec: 012
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
```

| Situation | `agentkit autopilot 012` |
|---|---|
| 012 `draft`, newest 012 record `#4 reject` of `approved` | `step: spec`, `last: #4 reject`, `findings: specs/012-…/reviews/4-approved-spec-reviewer.md` |
| 012 `approved` | `step: write-tests`, `set-phase: tests-draft`, reviewer `test-auditor` |
| 012 `tests-draft`, newest 012 record `#9 unfreeze` | `step: review-tests`, the two unfreeze reviews as `findings`, its `reason` |
| 012 `tests-approved` | `step: freeze`, `review: -`, `then: agentkit chaos approve 012 frozen` |
| 004 `frozen` (listed in `[chaos] specs`), 012 `draft` | `spec: 004`, `step: implement`, `then: agentkit chaos approve 004 done --review .autopilot/004-done-impl-reviewer.md` |
| 004 `frozen`, not listed in `[chaos] specs` | exit 1: `blocked: spec 004 is not under chaos mode`, `  needed by 012`, `hint: the owner finishes 004, or lists it in [chaos] specs` |
| 012 `done`, 004 sent back to `tests-draft` by an unfreeze | `spec: 004`, `step: review-tests` |
| 004 `dropped` | exit 1: `blocked: spec 004 is dropped (needed by 012)` |
| 012 depends on 013, 013 depends on 012 | exit 1: `blocked: dependency cycle: 012 -> 013 -> 012` |
| 012 `done` | `step: done`, `then: -`, exit 0 |
| chaos paused by escalation #3 | exit 1, see below |
| 012 `draft`, records `#4 reject`, `#5 reject`, `#6 escalate` of `approved`, then the owner's `#7 clear` | `step: spec`, `last: #6 escalate`, `findings: specs/012-…/reviews/5-approved-spec-reviewer.md` |
| `[chaos]` absent | exit 2: `blocked: chaos mode is off: the owner approves gates`, `hint: use /spec, /write-tests, /implement` |
| `agentkit autopilot 013` (not listed), whatever its dependencies | exit 1: `blocked: spec 013 is not under chaos mode` |
| `agentkit autopilot 12` | exit 2, usage on stderr |

Paused by escalation #3 (`rejections` of 012 `approved`, after rejects #1 and #2):

```text
blocked: chaos mode is paused: 1 open escalation(s)
  #3 2026-10-03T10:00:00Z escalate 012 approved rejections (agent)
    #1
    #2
hint: owner: agentkit chaos log --open
```

A full run of `/autopilot 012` from `draft` (004 `done`): spec-writer drafts, spec-reviewer reviews, `chaos
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

- Running dependencies that are not under chaos mode: they stop the run (R021-03).
- Running independent specs in one run, or anything in parallel.
- Any new gate, check or log record: those are 020's.
- Proving that the subagents were independent (020, Out of scope).

## Amendments to other specs

Approved by the owner and applied on 2026-10-03; listed in ADR 0002's appendix.

## Additions and open questions

None open. The design choices and the owner's decisions of 2026-10-03 are in the appendix of
[ADR 0002](../../docs/adr/0002-chaos-mode.md).
