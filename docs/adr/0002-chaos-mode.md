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
