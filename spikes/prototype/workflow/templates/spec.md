---
id: "{{id}}"
title: {{title}}
status: draft
---

# {{id}} {{title}}

## Context

Why this feature exists, in a few sentences. Link to the product vision and to ADRs.

## Requirements (EARS)

One requirement per line. IDs are stable: never renumber, mark removed ones `[removed]`.
Patterns: Ubiquitous "The <system> shall ...", Event "When <trigger>, the <system> shall ...",
State "While <state>, ...", Unwanted "If <condition>, then ...", Optional "Where <feature>, ...".
Append `[manual]` to a requirement that cannot be tested automatically (it is excluded from `trace`).

- **R{{id}}-01** The system shall ...
- **R{{id}}-02** When ..., the system shall ...

## Public API contract

Signatures that the tests will call, and where they live (module/package/file). Tests compile
against exactly this; implementation may add private code only.

```text
module/path/File: fun example(input: Type): Result
```

## Examples and edge cases

Concrete inputs and outputs, including the awkward ones. Golden files are named here.

## Out of scope

## Open questions

Questions for the human. The spec cannot be approved while one is open.
