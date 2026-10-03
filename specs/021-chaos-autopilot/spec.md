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

## Requirements (EARS)

## Public API contract

## Examples and edge cases

## Out of scope

## Additions beyond plan.md

## Open questions
