---
name: feature
description: Turn a feature idea for an existing project into numbered draft specs, or into an amendment of existing specs, and reserve the numbers. Use when the owner has a new idea.
argument-hint: "[idea in a few sentences]"
model: opus
effort: high
---
<!-- generated from .agents/skills/feature/SKILL.md by the bootstrap sync (ADR 0001); edit the source -->
# Feature intake

This skill only captures and numbers the idea. `/spec NNN` writes each spec later, at any
time. With no spec in `specs/` yet, use `/kickoff` instead.

1. **Context.** Read `specs/README.md` (the index). Open a spec only when its row looks
   related to the idea. Ask the owner at most five questions, and only what the idea leaves
   open: who it is for, what is out of scope, hard constraints.
2. **New spec or amendment?** For each part of the idea, decide:
   - **amendment**, when it changes behaviour an existing spec already owns. Name the spec and
     the requirements affected. A spec in `draft` is edited through `/spec NNN`. For a later
     phase, the owner decides; frozen tests change only through the owner's unfreeze;
   - **new spec**, when it is a coherent, testable unit of its own (roughly 5–30
     requirements). Split a large idea into several.
3. **Number.** Fetch the default branch first (`git fetch origin <default>`). Take one more
   than the highest number found in `specs/` there or locally, including `dropped` specs.
   Never reuse a number. A spec depends only on lower numbers. If the idea must come before an
   existing spec, say so instead of renumbering.
4. **Propose.** Show a table: number, slug, one-line scope, `depends`, and whether it is ready
   to spec now. List the amendments separately. Revise until the owner accepts it.
5. **Reserve.** For each accepted new spec, create `specs/NNN-slug/` with `plan.md`,
   `tasks.md`, `progress.md` and a skeleton `spec.md`:
   - front matter `id`, `title`, `status: draft` and `depends: ["MMM", …]`;
   - a Context paragraph with the agreed scope;
   - empty sections for the rest.

   Add the rows to `specs/README.md` and commit `spec(NNN): reserve <slug>` right away. Ask
   the owner to merge it to the default branch soon, because two branches can otherwise take
   the same number (CI catches it through `trace`).
6. **Hand over.** List what was reserved, the amendments awaiting the owner, and which specs
   can start now (every `depends` is `done`). Suggest `/spec NNN` for the first one.

If the owner later abandons a reserved spec, set it to `dropped` only when they say so. Its
folder and number stay.
