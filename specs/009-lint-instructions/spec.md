---
id: "009"
title: Instruction linter (token budgets)
status: tests-draft
depends: ["001"]
---

# 009 Instruction linter

## Context

Part B §1: keep the always-loaded context small, around 3k tokens. `lint-instructions` enforces
line budgets and the `@AGENTS.md` import, forbids duplicated blocks, and reports the estimated
size of the always-loaded instructions. It runs in pre-commit and CI.

## Requirements (EARS)

### Inputs
- **R009-01** The linter shall check `AGENTS.md` and `CLAUDE.md` at the root,
  `.claude/rules/**/*.md`, and `<paths.skills>/*/SKILL.md`. Generated per-tool copies (for
  example `.claude/skills/`) are not checked.
- **R009-02** Budgets shall come from `[budgets]` with these defaults: `agents_md_lines = 150`,
  `claude_md_lines = 40`, `rule_md_lines = 80`, `skill_md_lines = 500`,
  `skill_description_chars = 200`, `duplicate_min_lines = 3`, `always_loaded_tokens = 3000`.

### Errors (exit 1)
- **R009-03** A file with more lines than its budget shall be an error naming the file, its line
  count and the budget.
- **R009-04** When both `AGENTS.md` and `CLAUDE.md` exist and `CLAUDE.md` does not contain
  `@AGENTS.md`, the linter shall report an error.
- **R009-05** A SKILL.md whose `name` is missing, differs from its directory name, does not match
  `^[a-z0-9]+(-[a-z0-9]+)*$`, or is longer than 64 characters shall be an error.
- **R009-06** A SKILL.md whose `description` is missing, or longer than
  `skill_description_chars`, shall be an error.
- **R009-07** The linter shall report an error when the same block of `duplicate_min_lines`
  consecutive normalised lines appears in two different checked files, naming both files and
  the block's first line. One error per pair of files.
- **R009-08** Normalisation for R009-07 shall skip front matter, blank lines, code-fence lines
  and lines shorter than 12 characters. It strips leading list, quote, heading and numbering
  markers, collapses whitespace and ignores case.

### Warnings and report
- **R009-09** A rule file without `paths:` front matter shall produce a warning that it is always
  loaded.
- **R009-10** The linter shall estimate the always-loaded tokens as (characters + 3) // 4,
  summed over: AGENTS.md, CLAUDE.md, rule files without `paths:`, and `name: description` of
  every skill.
- **R009-11** When the estimate exceeds `always_loaded_tokens`, the linter shall warn (not fail).
- **R009-12** The last line shall be `lint-instructions: <OK|FAILED> (always-loaded instructions ~<n> tokens)`.
  The exit code is 1 if any error was reported, else 0.

## Public API contract

```text
agentkit/lint_instructions.py:
  @dataclass LintReport(errors: list[str], warnings: list[str], always_loaded_tokens: int); ok
  estimate_tokens(text) -> int
  lint(cfg) -> LintReport
```

## Examples and edge cases

- CLAUDE.md with only `@AGENTS.md` plus 10 lines: OK.
- The same 3-line rule pasted in AGENTS.md and in a skill: error.
- An AGENTS.md produced by `install` from the template (011) passes with the default budgets.

## Additions beyond plan.md

- The rule file budget (80 lines), the `paths:` warning, the token estimate formula, and the
  name and description rules from the Agent Skills standard.

## Open questions

None.
