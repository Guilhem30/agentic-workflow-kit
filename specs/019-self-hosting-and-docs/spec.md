---
id: "019"
title: Self-hosting, README and adapter documentation
status: approved
---

# 019 Self-hosting, README and adapter documentation

## Context

Principle 4: the kit uses its own process. The kit repo installs itself with its own AGENTS.md,
Claude adapter and lock. Users need a two-command quickstart and an honest matrix of what each
adapter can and cannot enforce.

## Requirements (EARS)

### Self-hosting
- **R019-01** The kit repo shall be installed with
  `python -m agentkit install --target . --self --profile python-unittest --adapters claude-code --ci github --ci-os linux,windows,macos`.
  With `--self`, the package is used from the repo root and not copied into `.agentkit/` (R010-06).
- **R019-02** The kit repo shall contain its own `AGENTS.md` (project sections plus the agentkit
  block), `CLAUDE.md`, `tests.lock.json` and `tests.unfreeze-log.md`.
- **R019-03** Every kit test approved by the owner shall be frozen in the kit's own lock
  (see 000 Bootstrap).
- **R019-04** The kit repo's pre-commit hook shall pass on a clean checkout, and so shall its CI
  workflow (on GitHub, once a remote exists).

### Documentation
- **R019-05** `README.md` shall contain:
  - a quickstart that installs the kit into a repository in 2 commands;
  - the list of commands;
  - the capability matrix (R019-06);
  - the unfreeze protocol in short;
  - the CODEOWNERS recommendation. [manual]
- **R019-06** `adapters/README.md` shall have one row per adapter with these columns:
  instructions, skills, pre-tool guard (edit and shell), end-of-turn verify, roles to subagents,
  model tiers, permissions, and known limitations. For each tool it records the date and URL of
  the documentation the adapter was checked against. [manual]
- **R019-07** The capability matrix shall state that Goose, Cline, OpenHands and Crush are covered
  by the neutral baseline only (AGENTS.md, git hooks, CI). [manual]

### Plan verification (acceptance)
- **R019-08** `python -m unittest discover -s tests` shall pass in the kit repo.
- **R019-09** install, update and `sync --check` shall be tested against temporary fixture
  repositories for at least two profiles and all five adapters.
- **R019-10** The guard demo of R012-12 shall be run once in a throwaway fixture repository
  installed with the `claude-code` adapter, which is then deleted. [manual]

## Public API contract

None beyond the earlier specs.

## Additions beyond plan.md

- The `--self` install flag and the `python-unittest` profile for the kit.
- R019-10 runs the guard demo in a throwaway fixture repository (owner's decision, 2026-10-03:
  the kit has no other user project).

## Open questions

None.
