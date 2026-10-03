---
name: write-tests
description: Turn an approved spec into compiling API stubs and failing, requirement-tagged tests, then audit them. Use after the human approved a spec.
metadata:
  agentkit-tier: strong
  agentkit-effort: high
  agentkit-args: "NNN"
---
# Tests phase

Run tools as `{{python}} .agentkit/bin/agentkit <command>`. The spec's status must be `approved`.

1. Read `specs/NNN-*/spec.md` and `plan.md`. The API contract is the boundary for the tests.
2. **Stubs.** Create exactly the contract's public API, with bodies that fail with the
   requirement ID (`TODO("RNNN-MM")`, `raise NotImplementedError("RNNN-MM")`).
3. **Tests.** Follow `.agentkit/workflow/roles/test-writer.md`. Each test name starts with its
   requirement ID. The tests are deterministic, go through the public contract only, and use
   small text fixtures and golden files.
4. **Fail for the right reason.** Run `test <scope>` for the new tests: everything compiles and
   each test fails because of a stub.
5. **Trace.** `trace --spec NNN` must pass. Requirements marked `[manual]` are exempt.
6. **Audit.** Delegate to the `test-auditor` role (or apply its checklist yourself) and fix what
   it finds.
7. Run `spec-status NNN tests-draft`, then hand over to the human: tests per requirement, the
   audit verdict, and any spec issues found. Ask them to review and approve.
8. When the human approves, run `spec-status NNN tests-approved` and tell them to run
   `/freeze NNN`. Do not freeze yourself.
