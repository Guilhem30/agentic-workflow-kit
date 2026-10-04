# ADR 0002: Chaos mode, an owner opt-in to agent-approved gates

- Status: accepted (owner, 2026-10-03)
- Context specs: 000 (principle 5, R000-10), 020, 021

## Context

Principle 5 of the constitution says the human owns the gates: no kit command lets an agent
approve a gate or unfreeze a test. That is the right default, but it makes the owner the
bottleneck of every spec. Some owners want agents to run a spec from draft to done on their own,
and be pulled in only when something is wrong.

## Decision

Principle 5 gains one exception: **chaos mode**, specified in 020.

- Only the owner enables it, in `[chaos]` of `agentkit.toml`, which agents cannot write. It is
  off by default, never covers spec 000, and with it off every gate behaves as before.
- With it on, an agent passes a gate only through `agentkit chaos approve`, with a passing
  verdict from the matching reviewer role. An agent unfreeze needs both the test-auditor and the
  impl-reviewer, and sends the spec back to `tests-draft`.
- Every agent pass, rejection, unfreeze and escalation goes into an append-only log, with a
  hashed copy of each review.
- Critical problems escalate and pause chaos mode until the owner clears them: repeated
  rejections, a failing `lock verify` or `lock audit`, a change to spec 000, AGENTS.md,
  CLAUDE.md, ADRs, `agentkit.toml` or role files, a rewritten base commit, or a reviewer's
  `verdict: needs owner`.
- Clearing escalations stays owner-only (agent-environment check and console confirmation).

New wording of principle 5: **The human owns the gates.** No kit command lets an agent approve a
gate or unfreeze a test, except in chaos mode, which only the owner enables (020).

## Consequences

- The kit cannot prove that a verdict came from an independent reviewer. In chaos mode the
  guarantee becomes visibility and mechanical checks, not prevention. Owners who need the
  guarantee leave chaos mode off.
- Spec 000, and the specs listed in 020's amendments (001, 002, 003, 005, 006, 010, 011, 012,
  014, 018), change to match.
- 021 adds `/autopilot`, which chains the phases in chaos mode.

## Appendix: amendments applied to other specs

Moved here from the specs on 2026-10-03 to keep them short. Each target spec already carries the change.

### From 020

- **000**: principle 5 and R000-10 gain "except in chaos mode, which only the owner enables
  (020)"; the glossary's Owner and Gate say the same; the command list gains `chaos` (020). A
  principle changes only with an ADR: ADR 0002 (accepted 2026-10-03).
- **001**: R001-05 lists `[chaos]` (read by 020).
- **002**: R002-20 and R002-21 note that `chaos unfreeze` (R020-25) bypasses them by design;
  R002-24 notes the `chaos agent` entry; `lock audit` (R002-27, R002-28) also runs `chaos.audit`
  when a chaos log exists, so pre-commit and CI (018) check it; `lock freeze --spec` refuses
  agents where chaos applies (R020-31).
- **003**: R003-09 lists the chaos log and reviews (R020-29, R020-42); R003-13 lists
  `chaos clear` (R020-30); R003-21 (inline scripts) and R003-27 (degraded mode) also cover the
  chaos log and the reviews.
- **005**: R005-06 notes the agent refusal of R020-31; the Open questions decision gains the
  chaos exception.
- **006**: R006-02, R006-03 and R006-06 refer to R020-32 to R020-34.
- **010**: the CODEOWNERS block (R010-10) covers the chaos log and `specs/*/reviews/`.
- **011**: R011-12: the test-auditor and impl-reviewer roles also end an unfreeze review with
  `verdict: unfreeze justified` or `verdict: keep frozen`, and every reviewer role may end with
  `verdict: needs owner` for a question only the owner can answer; R011-05: AGENTS.md hard rule 2 (never
  edit the chaos log or reviews, never run `chaos clear`) and rule 3 (where chaos applies, gates
  go through `chaos approve`), within the R011-06 budget; R011-01: chaos mode in WORKFLOW.md
  (R020-35).
- **012** (R012-03) and **014** (R014-03, R014-07): deny edits of the chaos log and reviews and
  Bash `*chaos clear*`.
- **018**: R018-04's failure text also mentions `chaos clear`.

### From 021

- **000**: the command list gains `autopilot` (021).
- **010**: R010-11's `.gitignore` block gains `.autopilot/`.
- **011**: Context counts 8 Agent Skills; R011-14 lists `autopilot`; R011-16 gives it
  standard/medium; R011-15's user-only flag also applies to `autopilot` (R021-08); R011-01's
  WORKFLOW.md covers `/autopilot` (R021-21, R021-25).
- **012**: R012-07's skill list in the CLAUDE.md block gains `/autopilot` (owner only, chaos
  mode), within its 20-line cap.

## Appendix: design choices and owner decisions

Moved here from the specs on 2026-10-04 so that implement sessions load only requirements,
contract and examples. The requirements already encode every choice below.

### 020: additions beyond plan.md

The whole spec is the owner's idea of 2026-10-03, not in plan.md. Design choices to approve:
- One JSON Lines log for approvals, rejections, unfreezes, escalations and clears, rather than a
  log plus separate escalation files, so "open" and "in a row" are computed from one file.
- Reviews copied into `specs/NNN-*/reviews/` with their hash in the log.
- `frozen` takes no review of its own: the test-auditor's `ready to freeze` verdict on
  `tests-approved` is the freeze verdict (R020-09 `based_on`).
- `tests-approved` requires a clean `trace` (R020-17).
- Spec 000 is simply outside chaos mode (R020-05); changes to it escalate through
  `escalate_globs`.
- An agent unfreeze needs both the test-auditor and the impl-reviewer (owner's decision).
- A reviewer escalates with `verdict: needs owner` (R020-43): an agent approves a spec with open
  questions unless the reviewer finds one only the owner can answer (owner's decision).
- An agent unfreeze is limited to one spec's tests, from `frozen` or `done`, and sends that spec
  back to `tests-draft`, so the changed tests are audited and frozen again.
- The pause is global, not per spec.
- The base commit for the `protected` and `audit` checks is the newest log record's commit; a
  vanished base escalates (`base`).
- `spec-status` and `lock freeze --spec` refuse gate moves by agents where chaos applies (R020-31).
- Requires git for the mutating commands (R020-06).

### 020: open questions (settled)

None. Decided by the owner on 2026-10-03:
1. An agent unfreeze needs both the test-auditor and the impl-reviewer (R020-12, R020-23).
2. An agent approves a spec with open questions unless the reviewer judges one critical; the
   reviewer then escalates with `verdict: needs owner` (R020-43).
3. Any edit of `AGENTS.md` or `CLAUDE.md` escalates (R020-01 default `escalate_globs`).
4. `done` needs no mechanical check beyond the critical checks; the impl-reviewer runs the tests.
5. ADR 0002 records the principle 5 change (`docs/adr/0002-chaos-mode.md`).

### 021: additions beyond plan.md

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
- Dependencies first: the chain order and the working spec (owner's decision, 2026-10-03). The
  phases along the chain are read before chaos is checked on the working spec, since the phase
  picks it (R021-03 items 7 and 8, unlike R020-38).
- At most one agent unfreeze per run (owner's decision, 2026-10-03; R021-18).
- The full suite runs after the impl-reviewer passes and before `chaos approve WWW done`.
- One retry of a reviewer whose verdict line is invalid (R021-12).
- A dependency outside chaos mode stops the run; the owner finishes it or lists it.
- Without subagents, one gate per session (R021-19).
- Tier standard/medium for the orchestrator: the strong-tier work is in the subagents.

### 021: open questions (settled)

None. Decided by the owner on 2026-10-03:
1. One agent unfreeze per run (R021-18). An unfreeze lets the test be modified, audited and
   frozen again.
2. Dependencies under chaos mode are run first (the chain, R021-01, R021-03).
3. One commit after each gate (R021-15).
