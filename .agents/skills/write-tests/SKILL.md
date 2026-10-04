---
name: write-tests
description: Turn an approved spec into API stubs and failing, requirement-tagged tests, then audit them. Use after the owner approved a spec.
metadata:
  agentkit-tier: strong
  agentkit-effort: high
  agentkit-args: "NNN"
---
# Tests phase

The spec must be `approved`. Tests written here become frozen, so they are the oracle for the
implementation: precise and complete, but not over-specified.

1. Read `specs/NNN-*/spec.md` and its `plan.md`. The Public API contract is the only surface
   the tests may use.
2. **Stubs.** Create the contract's modules, classes and functions with the exact signatures.
   Each body raises `NotImplementedError("<REQ-ID>")`.
3. **Tests.** Put them in `tests/test_NNN_<area>.py`, with each name starting
   `test_RNNN_MM_`. Cover every requirement not marked `[manual]`, the spec's examples, its
   boundaries and its error paths. Keep tests deterministic: temp dirs from `tests/support.py`,
   no network, no wall clock, no ordering assumptions.
4. **Red for the right reason.** Run the new modules. Every test must import cleanly and fail on
   a stub, not on a typo or a fixture bug.
5. **Coverage.** `python3 -m agentkit trace --spec NNN` passes: every non-manual ID of spec NNN
   appears in a test name.
6. **Audit.** Run the `test-auditor` role as a subagent (or apply `roles/test-auditor.md`
   inline). Fix its findings. If a test exposes a gap in the spec, propose the spec change to
   the owner first.
   Audit at most twice: a full audit, then a re-check given only the saved first audit (its
   path) and the fix commit. A third audit needs a new blocking finding in the re-check.
7. Set `status: tests-draft`, update `progress.md`, and hand over: tests per requirement, the
   audit verdict and any spec changes. Ask the owner to review.
8. **On approval in this conversation:** set `status: tests-approved` and commit
   `test(NNN): <summary>`. Tell the owner to run `/freeze NNN`. Never freeze yourself.
