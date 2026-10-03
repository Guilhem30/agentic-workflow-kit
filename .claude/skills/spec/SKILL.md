---
name: spec
description: Write or revise a feature spec (EARS requirements with stable IDs, public API contract) and get it reviewed. Use when starting a feature or when the owner asks for spec changes.
argument-hint: "NNN [slug]"
model: opus
effort: high
---
<!-- generated from .agents/skills/spec/SKILL.md by the bootstrap sync (ADR 0001); edit the source -->
# Spec phase

The spec must be `draft`. For a new feature, take the next free number, create
`specs/NNN-slug/` with `spec.md`, `plan.md`, `tasks.md` and `progress.md`, and add a row to
`specs/README.md`.

1. **Context.** Read the `plan.md` sections the spec derives from, the specs it depends on, and
   the relevant ADRs. Nothing else unless a requirement needs it.
2. **Write `spec.md`.** Front matter `id`, `title`, `status: draft`. Sections: Context,
   Requirements (EARS), Public API contract, Examples and edge cases, Additions beyond plan.md,
   Open questions.
   - One behaviour per requirement, measurable, ID `RNNN-MM`. Never reuse or renumber an ID;
     retire one by marking it `[removed]`.
   - Mark requirements a human checks with `[manual]`.
   - The API contract gives exact module paths and signatures. Tests will target it only.
   - List open questions; don't guess the answers.
3. **Plan the work.** `plan.md`: approach, files touched, test strategy. `tasks.md`: one
   `- [ ]` line per implementation step.
4. **Review.** Run the `spec-reviewer` role as a subagent (or apply `roles/spec-reviewer.md`
   inline if your tool has no subagents). Fix its findings or list them for the owner.
5. **Hand over.** Give the owner the requirement count, open questions, the reviewer's verdict
   and the main trade-offs, then ask for approval.
6. **On approval in this conversation:** set `status: approved` and commit `spec(NNN): <title>`.
   Suggest clearing the context before `/write-tests NNN`.
