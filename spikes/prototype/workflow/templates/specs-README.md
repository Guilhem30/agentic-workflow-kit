# Specs

One folder per feature: `NNN-slug/` with `spec.md` (what, with EARS requirement IDs), `plan.md`
(how), `tasks.md` (checklist) and `progress.md` (handoff notes). Create one with
`agentkit new-spec NNN slug`.

The `status:` field in `spec.md` is the phase:
`draft -> approved -> tests-draft -> tests-approved -> frozen -> done`.
The human approves the spec, approves the tests and runs the freeze. See
`.agentkit/workflow/WORKFLOW.md`.
