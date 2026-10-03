---
name: kickoff
description: Turn a new project idea into numbered specs - interview the owner, write spec 000 (vision, constitution, roadmap) and the spec index, and create one draft spec per feature. Use when specs/ is empty.
argument-hint: "[idea in a few sentences]"
model: opus
effort: high
---
<!-- generated from .agents/skills/kickoff/SKILL.md by the bootstrap sync (ADR 0001); edit the source -->
# Project kickoff

Use this once, when `specs/` holds no spec yet. For an existing project, use `/spec`.
Nothing here is approved until the owner says so.

1. **Interview.** Ask the owner, in one batch of at most eight questions, what you cannot infer
   from the idea:
   - the goal and the users;
   - what is in and out of scope for the first version;
   - language, runtime and platforms;
   - hard constraints (dependencies, performance, security, compliance);
   - how they will judge it done.

   Ask a second batch only if answers conflict. Never guess an answer; list it as an open
   question.
2. **Break it down.** Split the project into features, each one a coherent, testable unit
   (roughly 5–30 requirements). Number them:
   - `000` is always the vision and constitution;
   - features get `001`, `002`, … in dependency order, so a spec depends only on lower
     numbers;
   - slugs are short kebab-case nouns (`user-accounts`, not `implement-the-users`).

   Show the owner the breakdown as a table (ID, slug, one-line scope, depends on) **before
   writing any spec**. Revise it until they accept it.
3. **Spec 000.** Write `specs/000-vision/spec.md`:
   - Context, personas and a glossary;
   - principles that change only through an ADR;
   - project-wide EARS requirements (`R000-MM`): platforms, dependencies, error and output
     conventions;
   - scope, out of scope, and the roadmap (the accepted table).
4. **Index.** Write `specs/README.md`: one row per spec with ID, linked slug, one-line scope and
   dependencies, then the suggested order and the ID format `RNNN-MM`.
5. **Skeletons.** For every other spec, create `specs/NNN-slug/` with `plan.md`, `tasks.md` and
   `progress.md`, plus a `spec.md` holding:
   - front matter `id`, `title`, `status: draft`, `depends: ["MMM", …]`;
   - a Context paragraph with the agreed scope and dependencies;
   - empty sections for the rest.

   `/spec NNN` fills one spec per session later. If the owner wants full drafts now, write them
   one spec at a time, each in a subagent where your tool has them, so this context stays small.
6. **Review.** Run the `spec-reviewer` role on spec 000 and the index, as a subagent or inline
   from `roles/spec-reviewer.md`. Fix what it finds.
7. **Hand over.** Give the owner the spec list, the open questions and the reviewer's verdict,
   and ask them to approve spec 000. On approval, set its status to `approved` and commit
   `spec(000): vision and roadmap`. Suggest `/clear`, then `/spec 001`.
