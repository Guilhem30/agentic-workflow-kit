---
id: "011"
title: Workflow content (process docs, templates, roles, skills)
status: frozen
depends: ["005", "009"]
---

# 011 Workflow content

## Context

The neutral content that every adapter wires in:
- `workflow/WORKFLOW.md` (the process);
- `workflow/TOKEN-EFFICIENCY.md` (Part B playbook);
- `workflow/templates/`;
- `workflow/roles/` (7 model-neutral role prompts, each with a tier);
- `skills/` (8 Agent Skills: kickoff, feature, spec, write-tests, freeze, implement, handoff,
  autopilot).

Much of this content is prose, so many requirements here are `[manual]`. The structural ones are
tested.

## Requirements (EARS)

### Process documents
- **R011-01** `WORKFLOW.md` shall describe the phases and gates (005), each phase's steps, the
  freeze and unfreeze protocol (002), the enforcement layers and their limits, roles and tiers,
  session handoff, the spike and bootstrap exceptions, and chaos mode with `/autopilot` (R020-35,
  R021-21, R021-25). [manual]
- **R011-02** `TOKEN-EFFICIENCY.md` shall contain the 8 sections of plan Part B and a budget
  table matching the defaults of 006, 007 and 009. [manual]

### Templates
- **R011-03** `workflow/templates/` shall contain `AGENTS.md.tmpl`, `agentkit.toml.tmpl`,
  `spec.md`, `plan.md`, `tasks.md`, `progress.md`, `adr.md`, `specs-README.md` and
  `unfreeze-log.md`.
- **R011-04** `spec.md` shall have front matter (`id`, `title`, `status: draft`) and these
  sections: Context, Requirements (EARS) with an explanation of the patterns and of the manual
  marker, Public API contract, Examples and edge cases, Out of scope, Open questions.
- **R011-05** `AGENTS.md.tmpl` shall contain project sections outside the agentkit block, and
  inside the block:
  - the session-start instruction;
  - the hard rules (frozen files, protected files, the owner's gates, no test gaming, IDs in
    test names). The protected-files rule also forbids editing the chaos log and
    `<paths.specs>/*/reviews/` and running `chaos clear`; the gates rule says that where chaos
    mode applies, gates go through `agentkit chaos approve` (020). Both stay within R011-06;
  - a command table whose agentkit commands run through `{{python}} .agentkit/bin/agentkit`
    (the launcher of R010-07);
  - token-discipline rules.
- **R011-06** The agentkit block of the rendered AGENTS.md, counted from its begin marker line to
  its end marker line inclusive, shall be at most 45 lines, so that projects keep at least 100
  lines of the 150-line budget for themselves.
- **R011-07** Templates shall use only known placeholder keys, each written `{{key}}`:
  - the spec-folder templates (`spec.md`, `plan.md`, `tasks.md`, `progress.md`) only the
    `new-spec` keys `id`, `slug` and `title` (005);
  - the other templates only the install context keys `python`, `version`, `profile`,
    `adapters`, `ci_providers`, `ci_os`, `models`, `specs`, `lock`, `unfreeze_log`, `codemap`,
    `skills`, `roles` and `chaos_log`, which install (010) supplies.

  Rendering a template with its keys shall leave no `{{…}}` placeholder.
- **R011-08** An AGENTS.md produced from the template, together with a CLAUDE.md that imports it
  (`@AGENTS.md`) and the kit skills installed in `<paths.skills>`, shall pass
  `lint-instructions` (009). The full CLAUDE.md block is checked by 012 (R012-08).

### Roles
- **R011-09** `workflow/roles/` shall contain `spec-writer`, `spec-reviewer`, `test-writer`,
  `test-auditor`, `implementer`, `impl-reviewer` and `summarizer`. Each has front matter `name`
  (equal to the file name), `description`, `tier` (`strong`/`standard`/`fast`), `effort`
  (`low`/`medium`/`high`) and `tools` (a subset of `read`, `edit`, `shell`).
- **R011-10** The tiers shall be: strong for spec-writer, spec-reviewer, test-writer and
  test-auditor; standard for implementer and impl-reviewer (owner's decision, 2026-10-03,
  `docs/priorities.md`); fast for summarizer.
- **R011-11** spec-reviewer, test-auditor and impl-reviewer shall not have the `edit` tool.
- **R011-12** Each reviewer role shall end with an explicit verdict format. The test-auditor
  checks whether a plausible wrong implementation could pass, and the impl-reviewer looks for
  test gaming. The verdict lines are those of R020-12: the test-auditor and the impl-reviewer
  also end an unfreeze review with `verdict: unfreeze justified` or `verdict: keep frozen`, and
  every reviewer role may end with `verdict: needs owner` for a question only the owner can
  answer (020). [manual]
- **R011-13** `roles(cfg)` shall return every role as `{name: path}`: the kit roles in
  `workflow/roles/` of the kit source, plus the project roles in `<paths.roles>/`, where a
  project role overrides the kit role that has the same name. A role's name is its file name
  without `.md`. Sync (010, 012) takes its roles from this function.

### Skills
- **R011-14** `skills/` shall contain `kickoff`, `feature`, `spec`, `write-tests`, `freeze`,
  `implement`, `handoff` and `autopilot` (021).
  Each SKILL.md follows the Agent Skills standard: `name` equal to the directory, a `description`
  of at most 200 characters, and only standard keys at the top level. Agentkit extras go under
  `metadata` (`agentkit-tier`, `agentkit-effort`, `agentkit-user-only`, `agentkit-args`).
- **R011-15** The `freeze` skill shall set `agentkit-user-only: "true"` and shall stop when the
  spec is not `tests-approved`. The `autopilot` skill also sets `agentkit-user-only: "true"`
  (R021-08).
- **R011-16** The tiers shall be: kickoff, feature, spec and write-tests strong/high, implement and
  autopilot standard/medium, freeze and handoff fast/low.
- **R011-17** Each skill shall name the role it delegates review to, and say what to do when the
  tool has no subagents (apply the role's checklist inline). [manual]
- **R011-19** The `kickoff` skill shall apply only when the project has no spec. It shall:
  - interview the owner in batches of at most eight questions;
  - have the owner accept a numbered breakdown before writing any spec, where `000` is the
    vision and constitution and features are numbered in dependency order, with `depends` in
    each front matter;
  - write spec 000 and `specs/README.md`, and create every other spec as a `draft` skeleton;
  - approve nothing without the owner. [manual]
- **R011-20** The `feature` skill shall apply when the project has specs. It shall:
  - read the spec index and open only related specs;
  - classify each part of the idea as a new spec or an amendment of an existing one, and
    leave amendments past `draft` to the owner;
  - number new specs one above the highest number on the default branch or locally, including
    dropped specs;
  - after the owner accepts, create `draft` skeletons with `depends`, add the index rows, and
    commit them at once to reserve the numbers. [manual]
- **R011-21** Only `kickoff` and `feature` shall assign spec numbers. `spec` works on an
  existing draft. [manual]
- **R011-18** Skills shall refer to agentkit commands through `{{python}} .agentkit/bin/agentkit`,
  rendered at install time with the install context keys of R011-07.

## Public API contract

The files and front-matter fields listed above, and:

```text
agentkit/roles.py:
  roles(cfg) -> dict[str, Path]     # R011-13
```

## Examples and edge cases

- `metadata.agentkit-user-only: "true"` on `freeze` becomes `disable-model-invocation: true` in
  the Claude copy (012).

## Additions beyond plan.md

- Chaos autopilot (021 amendment, approved by the owner on 2026-10-03): the `autopilot` skill
  (Context, R011-01, R011-14, R011-15, R011-16).
- Templates `agentkit.toml.tmpl`, `specs-README.md` and `unfreeze-log.md`.
- The block-size cap (R011-06), and the `metadata` convention for agentkit extras (R011-14).
- The `kickoff` and `feature` skills and the numbering rules (R011-19 to R011-21) (owner's request, 2026-10-03).
- The placeholder key lists (R011-07), `roles(cfg)` (R011-13) and linting AGENTS.md with the kit
  skills (R011-08) (owner's answers while writing the tests, 2026-10-04).
- Chaos mode in WORKFLOW.md, AGENTS.md and the reviewer verdicts (R011-01, R011-05, R011-12; 020
  amendment, approved by the owner on 2026-10-03).

## Open questions

None.
