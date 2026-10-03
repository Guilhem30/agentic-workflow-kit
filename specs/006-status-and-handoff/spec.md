---
id: "006"
title: Status and handoff
status: frozen
depends: ["002", "005"]
---

# 006 Status and handoff

## Context

Short sessions that resume from files: one spec phase per session, then clear the context. The
session-start `status` is at most 10 lines. `handoff` writes the resume point into
`progress.md`, so that clearing the context costs almost nothing.

## Requirements (EARS)

### status
- **R006-01** `agentkit status` shall print at most 10 lines, each at most 200 characters.
- **R006-02** Line 1 shall be `agentkit: profile <name> | frozen files: <n> | lock: <OK | VIOLATED (<k> file(s): run `agentkit lock verify`)>`,
  followed by the chaos suffix of R020-32 when a `[chaos]` table exists.
- **R006-03** status shall print one line per spec not in phase `done` or `dropped`, in ID order:
  `spec NNN slug [phase] -> <next action>`, where the next action depends on the phase:
  - `draft`: run /spec NNN, then HUMAN approves;
  - `approved`: run /write-tests NNN;
  - `tests-draft`: HUMAN reviews the tests;
  - `tests-approved`: HUMAN runs /freeze NNN;
  - `frozen`: run /implement NNN.

  For a spec chaos mode applies to, R020-33 replaces these actions.
- **R006-13** For a spec in phase `frozen` with a `depends` entry (R005-20) whose spec is not
  `done`, the next action shall be `blocked by NNN[, MMM]` instead of `run /implement NNN`.
  Blocked specs are listed after the others.
- **R006-04** For a spec in phase `frozen`, the line shall end with `(progress: <text>)` when
  `progress.md` has a line `**Next:** <text>`.
- **R006-05** When there are more active specs than fit, status shall show as many as fit and a
  line `... <n> more active spec(s)`.
- **R006-06** When the lock is violated, the last line shall tell the agent to restore the frozen
  files or ask the owner to unfreeze, before anything else. Otherwise, while chaos mode is
  paused, the last line is the one of R020-34. Otherwise, when a spec is active, the
  last line is `next: <first active spec's next action>`.
- **R006-07** When there is no active spec, status shall print a line suggesting `/spec`
  (`agentkit new-spec slug`). When no spec exists at all, the line suggests `/kickoff` instead.
- **R006-08** If the lock is unreadable, then status shall report `lock: BROKEN (<error>)`
  instead of failing, and exit 0.

### handoff
- **R006-09** `agentkit handoff NNN [--note TEXT] [--next TEXT]` shall write a snapshot block
  between `<!-- agentkit:snapshot:begin -->` and `<!-- agentkit:snapshot:end -->` in
  `specs/NNN-*/progress.md`. It replaces an existing block and leaves the rest of the file
  unchanged; otherwise it appends the block.
- **R006-10** The snapshot shall contain:
  - the UTC timestamp and the phase;
  - `Tasks: <done>/<total> done`, with the first open task (from `- [ ]` / `- [x]` lines in `tasks.md`);
  - the first lines (at most 9) of the last `agentkit test` summary, when one exists;
  - the git branch and the number of uncommitted changes, when in a git repository;
  - the note, when given;
  - a final line `**Next:** <text>`.
- **R006-11** The `**Next:**` text shall be `--next` when given, else the first open task, else
  the phase's next action.
- **R006-12** If spec NNN does not exist, then handoff shall exit 1 and write nothing.

## Public API contract

```text
agentkit/status.py: status_lines(cfg) -> list[str]
agentkit/handoff.py: snapshot(cfg, spec_id, note="", next_step="", now=None) -> str
```

## Examples and edge cases

- 9 active specs: lines 1, 2..8 (7 specs), `... 2 more active spec(s)`, `next: …` = 10 lines.
- Running handoff twice changes only the snapshot block.

## Additions beyond plan.md

- Chaos mode (020 amendment, ADR 0002, approved by the owner on 2026-10-03): the chaos suffix,
  chaos next actions and the paused last line (R006-02, R006-03, R006-06).
- The exact status format, the progress `**Next:**` line, and the snapshot markers.
- Suggesting `/kickoff` in a project with no spec (R006-07) (owner's request, 2026-10-03).
- `/spec NNN` as the draft action, skipping `dropped`, and `blocked by` (R006-03, R006-13), so
  reserved specs show when they can start (owner's request, 2026-10-03).

## Open questions

None.
