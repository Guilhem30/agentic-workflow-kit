---
id: "011"
title: Workflow content (process docs, templates, roles, skills)
status: approved
---

# 011 Workflow content

## Context

The neutral content that every adapter wires in:
- `workflow/WORKFLOW.md` (the process);
- `workflow/TOKEN-EFFICIENCY.md` (Part B playbook);
- `workflow/templates/`;
- `workflow/roles/` (7 model-neutral role prompts, each with a tier);
- `skills/` (5 Agent Skills: spec, write-tests, freeze, implement, handoff).

Much of this content is prose, so many requirements here are `[manual]`. The structural ones are
tested.

## Requirements (EARS)

### Process documents
- **R011-01** `WORKFLOW.md` shall describe the phases and gates (005), each phase's steps, the
  freeze and unfreeze protocol (002), the enforcement layers and their limits, roles and tiers,
  session handoff, and the spike and bootstrap exceptions. [manual]
- **R011-02** `TOKEN-EFFICIENCY.md` shall contain the 8 sections of plan Part B and a budget
  table matching the defaults of 006, 007 and 009. [manual]

### Templates
- **R011-03** `workflow/templates/` shall contain `AGENTS.md.tmpl`, `agentkit.toml.tmpl`,
  `spec.md`, `plan.md`, `tasks.md`, `progress.md`, `adr.md`, `specs-README.md` and
  `unfreeze-log.md`.
- **R011-04** `spec.md` shall have front matter (`id`, `title`, `status: draft`) and these
  sections: Context, Requirements (EARS) with an explanation of the patterns and of `[manual]`,
  Public API contract, Examples and edge cases, Out of scope, Open questions.
- **R011-05** `AGENTS.md.tmpl` shall contain project sections outside the agentkit block, and
  inside the block:
  - the session-start instruction;
  - the hard rules (frozen files, protected files, the owner's gates, no test gaming, IDs in
    test names);
  - a command table;
  - token-discipline rules.
- **R011-06** The agentkit block of the rendered AGENTS.md shall be at most 45 lines, so that
  projects keep at least 100 lines of the 150-line budget for themselves.
- **R011-07** Rendering any template with an install context shall leave no `{{…}}` placeholder
  of a known context key. Templates must not use unknown keys.
- **R011-08** An AGENTS.md produced from the template, together with the CLAUDE.md block (012),
  shall pass `lint-instructions` (009).

### Roles
- **R011-09** `workflow/roles/` shall contain `spec-writer`, `spec-reviewer`, `test-writer`,
  `test-auditor`, `implementer`, `impl-reviewer` and `summarizer`. Each has front matter `name`
  (equal to the file name), `description`, `tier` (`strong`/`standard`/`fast`), `effort`
  (`low`/`medium`/`high`) and `tools` (a subset of `read`, `edit`, `shell`).
- **R011-10** The tiers shall be: strong for spec-writer, spec-reviewer, test-writer,
  test-auditor and impl-reviewer; standard for implementer; fast for summarizer.
- **R011-11** spec-reviewer, test-auditor and impl-reviewer shall not have the `edit` tool.
- **R011-12** Each reviewer role shall end with an explicit verdict format. The test-auditor
  checks whether a plausible wrong implementation could pass, and the impl-reviewer looks for
  test gaming. [manual]
- **R011-13** Project roles in `<paths.roles>/` shall override kit roles that have the same name.

### Skills
- **R011-14** `skills/` shall contain `spec`, `write-tests`, `freeze`, `implement` and `handoff`.
  Each SKILL.md follows the Agent Skills standard: `name` equal to the directory, a `description`
  of at most 200 characters, and only standard keys at the top level. Agentkit extras go under
  `metadata` (`agentkit-tier`, `agentkit-effort`, `agentkit-user-only`, `agentkit-args`).
- **R011-15** The `freeze` skill shall set `agentkit-user-only: "true"` and shall stop when the
  spec is not `tests-approved`.
- **R011-16** The tiers shall be: spec and write-tests strong/high, implement standard/medium,
  freeze and handoff fast/low.
- **R011-17** Each skill shall name the role it delegates review to, and say what to do when the
  tool has no subagents (apply the role's checklist inline). [manual]
- **R011-18** Skills shall refer to agentkit commands through `{{python}} .agentkit/bin/agentkit`,
  rendered at install time.

## Public API contract

The files and front-matter fields listed above. There is no Python API.

## Examples and edge cases

- `metadata.agentkit-user-only: "true"` on `freeze` becomes `disable-model-invocation: true` in
  the Claude copy (012).

## Additions beyond plan.bkp

- Templates `agentkit.toml.tmpl`, `specs-README.md` and `unfreeze-log.md`.
- The block-size cap (R011-06), and the `metadata` convention for agentkit extras (R011-14).

## Open questions

None.
