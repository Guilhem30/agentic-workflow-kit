---
name: spec
description: Write or revise a draft spec (EARS requirements with stable IDs, public API contract) and get it reviewed. Use for a reserved draft spec or when the owner asks for spec changes.
argument-hint: "NNN"
model: opus
effort: high
---
<!-- generated from .agents/skills/spec/SKILL.md by the bootstrap sync (ADR 0001); edit the source -->
# Spec phase

The spec must exist and be `draft`. Numbers are assigned elsewhere: `/kickoff` for a new
project, `/feature` for a new idea. Keep the `depends` front matter accurate.

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
