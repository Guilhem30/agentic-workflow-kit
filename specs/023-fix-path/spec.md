---
id: "023"
title: Fix path for finished work
status: draft
depends: ["005", "011"]
---

# 023 Fix path for finished work

## Context

The process covers new work only: spec, tests, owner freeze, implement. Once a spec is `done`
there is no defined way to fix it. When the code breaks a requirement and no frozen test catches
it, the only route today is to invent a new spec by hand (as 022 did). Doc and wording fixes, and
review follow-ups found after a spec closes, have no defined path either.

This spec adds a `/fix` skill that sorts a problem report into one of four kinds and routes it:

- the code breaks an existing requirement and the tests missed it: a **fix spec** whose
  requirements restore that behaviour and hold the regression tests. It goes through the
  **same gates as new work** (owner's decision, 2026-10-04);
- the requirement itself is wrong or missing: hand over to `/feature` (amendment);
- a frozen test is wrong: stop and tell the owner, who alone unfreezes;
- wording or docs only, no behaviour change: a direct `fix:` commit that keeps the content
  tests, `lint-instructions` and `sync --check` green.

Principle: **a frozen contract can grow, never shrink.** A fix adds owner-approved tests; it never
edits a frozen file. `/fix` assigns spec numbers with the same rules as `/feature` (owner's
decision, 2026-10-04). It adds a fix-spec template (or a Fix section in `spec.md`) and a
Maintenance section in `WORKFLOW.md`. No CLI or lock changes.

Like 020 and 022, this spec amends a `done` spec (011: R011-01, R011-03/04, R011-05, R011-14,
R011-16, R011-21) and holds the new tests itself; the frozen tests of 011 do not change.

## Requirements (EARS)

## Public API contract

## Examples and edge cases

## Out of scope

## Open questions
