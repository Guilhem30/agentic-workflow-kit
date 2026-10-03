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
