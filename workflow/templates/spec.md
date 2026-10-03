---
id: "{{id}}"
title: {{title}}
status: draft
depends: []
---

# {{id}} {{title}}

## Context

Why this feature exists and what it changes for the user.

## Requirements (EARS)

Each requirement has a stable ID `R{{id}}-MM` and one of these patterns:
ubiquitous ("The X shall ..."), event ("When E, the X shall ..."), state ("While S, ..."),
unwanted ("If U, then the X shall ...") or optional ("Where F, ..."). IDs are never reused.
Mark a requirement `[manual]` when a human checks it instead of a test, and `[removed]` when
it is withdrawn.

- **R{{id}}-01** ...

## Public API contract

```text
module/path:
  name(args) -> result
```

## Examples and edge cases

-

## Out of scope

-

## Open questions

None.
