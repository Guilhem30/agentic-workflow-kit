---
id: "005"
title: Spec folders, phases, requirement IDs and traceability
status: approved
depends: ["001"]
---

# 005 Spec folders, phases, requirement IDs and traceability

## Context

Spec Kit / Kiro style: one folder per feature, EARS requirements with stable IDs, and a status
that drives the gates. `trace` proves that every approved requirement has at least one test.
Test names start with their requirement ID.

## Requirements (EARS)

### Folders and phases
- **R005-01** A spec shall live in `<specs>/NNN-slug/`, where NNN is three digits and slug matches
  `[a-z0-9][a-z0-9-]*`. Other directories under `<specs>` are ignored.
- **R005-02** `spec.md` shall begin with front matter holding `id`, `title` and `status`.
  A missing status means `draft`.
- **R005-03** The phases shall be, in order: `draft`, `approved`, `tests-draft`,
  `tests-approved`, `frozen`, `done`.
- **R005-18** `dropped` shall be a terminal phase outside the order of R005-03, for an idea the
  owner abandoned. `spec-status NNN dropped` is accepted only from `draft`, `approved` and
  `tests-draft`; from a later phase it exits 1, saying the owner must unfreeze first. A dropped
  spec keeps its folder and number. `trace` (without `--spec`) and `status` skip it.
- **R005-19** If two folders under `<specs>` share a number, then `trace`, `new-spec` and
  `spec-status` shall exit 1, naming both folders.
- **R005-20** The front matter may hold `depends`, a list of spec numbers (absent means none).
  `trace` shall exit 1 when an entry names no existing spec, names the spec itself, or forms a
  cycle, naming the spec and the entry.
- **R005-04** `agentkit new-spec NNN slug [--title T]` shall create `spec.md`, `plan.md`,
  `tasks.md` and `progress.md` from the kit templates, replacing `{{id}}`, `{{slug}}` and
  `{{title}}` (default title: the slug with hyphens as spaces, capitalised).
- **R005-17** When `new-spec` is given only a slug, it shall use the next free number: one more
  than the highest existing spec number, or `000` when there is none. Spec folders are never
  deleted, so numbers are never reused. It prints the chosen number.
- **R005-05** If spec NNN already exists, or the slug is invalid, then `new-spec` shall create
  nothing and exit 1.
- **R005-06** `agentkit spec-status NNN STATUS` shall set the status, keep the rest of the file
  unchanged, and exit 0. Exception: while chaos mode applies to NNN, the CLI refuses
  `approved`, `tests-approved` and `done` in an agent environment (R020-31); `set_status()` does
  not check this.
- **R005-07** If STATUS is `frozen`, then `spec-status` shall refuse and exit 1, saying that
  `frozen` is set only by `lock freeze --spec` (002).
- **R005-08** If STATUS is not a known phase, or the spec does not exist, then `spec-status`
  shall exit 1.

### Requirement IDs
- **R005-09** Requirement IDs shall be found with the profile's `req_id_regex` and normalised to
  `R<group1>-<group2>`, so that `R004_07` becomes `R004-07`.
- **R005-10** In a spec, only IDs whose spec number equals the spec's own number shall count as
  that spec's requirements. References to other specs are ignored.
- **R005-11** A requirement whose list item contains `[manual]` or `[removed]` (case-insensitive)
  shall be excluded from traceability. The list item is the line that declares the ID plus the
  indented continuation lines that follow it.

### trace
- **R005-12** `agentkit trace` shall check every spec in phase `tests-draft` or later.
  `trace --spec NNN` shall check that spec whatever its phase.
- **R005-13** A requirement is traced when its ID appears (in any accepted form) in at least one
  file that matches the profile's `test_globs` and not `build_output_globs`.
- **R005-14** For each spec, trace shall print `spec NNN: <traced>/<required> requirements traced [OK|MISSING]`,
  then one line per untraced ID.
- **R005-15** trace shall warn about IDs of the spec that appear in tests but are not declared in
  it (or are excluded by R005-11), naming one file. Warnings do not fail.
- **R005-16** trace shall exit 1 when any checked spec has an untraced requirement, and exit 1
  for an unknown `--spec`. When no spec is in a traced phase, it prints a message and exits 0.

## Public API contract

```text
agentkit/specs.py:
  PHASES: list[str]                 # the order of R005-03
  DROPPED = "dropped"               # R005-18
  @dataclass Spec: id, slug, dir, status, title, depends: list[str]; spec_md: Path; next_action() -> str
  list_specs(cfg) -> list[Spec]; find_spec(cfg, spec_id) -> Spec | None
  set_status(spec, status) -> None
  spec_requirements(cfg, spec) -> (testable_ids: list[str], excluded_ids: set[str])
  new_spec(cfg, spec_id, slug, title="") -> Path   # spec_id None: next free number (R005-17)
agentkit/trace.py:
  @dataclass TraceResult: spec, required, covered: dict[id, files], unknown: dict[id, files]; missing; ok
  trace_specs(cfg, spec_id=None) -> list[TraceResult]
  format_results(results) -> list[str]
```

## Examples and edge cases

- spec 004 declares R004-01..R004-03, and R004-03 is `[manual]`. A test `` `R004-01 …` `` and a
  test `test_R004_02_x` give `2/2 [OK]`.
- spec 004 references R001-05: not counted as a requirement of 004.
- A test mentions R004-09, which is not declared: warning only.

## Additions beyond plan.md

- Chaos mode (020 amendment, ADR 0002, approved by the owner on 2026-10-03): the agent refusal in
  R005-06 (R020-31).
- The `tests-draft` phase (the plan had approved → tests approved). It marks "tests written,
  waiting for review", so that `status` can tell the owner it is their turn.
- `new-spec` and `spec-status` commands.
- The `[removed]` marker.
- Automatic numbering (R005-17), so an agent can number specs from scratch (owner's request, 2026-10-03).
- The `dropped` phase, the duplicate-number check and `depends` (R005-18 to R005-20), so ideas
  can be reserved as numbered drafts at any time and built later (owner's request, 2026-10-03).

## Open questions

None. (Decided 2026-10-03: agents may set `approved` and `tests-approved` through `spec-status`,
but only when the owner said so in the conversation. This rule is in AGENTS.md (011).
`frozen` stays reserved to `lock freeze`. Exception, approved by the owner on 2026-10-03: where
chaos mode applies (020), agents pass gates only through `chaos approve`, with a reviewer's
passing verdict and no owner involvement.)
