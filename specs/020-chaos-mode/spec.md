---
id: "020"
title: Chaos mode: agent-approved gates
status: draft
depends: ["001", "002", "003", "005", "006"]
---

# 020 Chaos mode: agent-approved gates

## Context

An opt-in mode in which agents pass the gates themselves, without the owner, unless a critical
problem arises. Only the owner turns it on, in `[chaos]` of `agentkit.toml` (a file agents cannot
write, R003-09), for the whole repository or for chosen specs. With chaos mode on, an agent may
set `approved`, `tests-approved` and `done` and run `lock freeze`, each only with a passing
verdict from the matching reviewer role (spec-reviewer, test-auditor, impl-reviewer). An agent may
unfreeze a test when a reviewer agrees; the unfreeze log marks it as an agent unfreeze for later
audit. Every agent approval is appended to an append-only approval log. A critical problem stops
the run and writes an escalation record: the same gate rejected twice in a row (N configurable),
a failing `lock verify` or `lock audit`, or a change that touches spec 000 or a hard rule.
`status` shows open escalations, and chaos mode stays paused until the owner clears them. Off by
default; with it off, every existing owner gate behaves exactly as before.

Amendments this spec needs in approved specs (owner's decision, pending): 000 principle 5 and
R000-10, glossary Owner and Gate; 002 R002-20, R002-21, R002-24 and audit; 003 R003-13; 005
`spec-status` gate statuses; 006 status line 1; 011 AGENTS.md hard rules 2 and 3.

## Requirements (EARS)

## Public API contract

## Examples and edge cases

## Out of scope

## Additions beyond plan.md

## Open questions
