---
name: spec
description: Write or revise a feature spec (EARS requirements, API contract) and get it reviewed. Use when starting a feature or when the human asks for spec changes.
metadata:
  agentkit-tier: strong
  agentkit-effort: high
  agentkit-args: "[NNN slug | NNN]"
---
# Spec phase

Run tools as `{{python}} .agentkit/bin/agentkit <command>`.

1. **Folder.** For a new feature, pick the next free number and run `new-spec NNN slug`.
   For an existing spec, open `specs/NNN-*/spec.md` (its status must be `draft`).
2. **Context.** Read AGENTS.md, docs/CODEMAP.md and the related specs or ADRs. Nothing more,
   unless a requirement needs it.
3. **Write** `spec.md` following the template's sections. EARS requirements with stable IDs
   `RNNN-MM`, one behaviour each, measurable. The public API contract has exact signatures and
   locations. Concrete examples and edge cases. Open questions listed, not guessed.
   Fill in `plan.md` (approach, files, test strategy) and the implementation part of `tasks.md`.
4. **Review.** Delegate to the `spec-reviewer` role (a subagent if your tool has one; otherwise
   apply its checklist from `.agentkit/workflow/roles/spec-reviewer.md` yourself). Fix the
   findings, or list them for the human.
5. **Hand over.** Leave `status: draft`. Give the human: the requirement count, open questions,
   reviewer verdict and notable trade-offs. Ask for approval.
6. When the human approves in this conversation, run `spec-status NNN approved` and commit
   `spec(NNN): <title>`. Then suggest clearing the context before `/write-tests NNN`.
