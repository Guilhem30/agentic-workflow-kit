---
id: "022"
title: Owner decisions on open spec questions
status: draft
depends: ["002", "003", "005", "020"]
---

# 022 Owner decisions on open spec questions

## Context

While specs 002, 003 and 005 were implemented, the agents logged open questions for the owner.
On 2026-10-03 the owner took the recommended answer to each (`docs/priorities.md`, questions
A–H). The answers that only reword a spec (A, B, E, H) were applied to 003, 005 and 020
directly. The four that change behaviour (C, D, F, G) are here, because the specs that own the
behaviour are `done` and their tests are frozen. Like 020, this spec amends earlier specs and
holds the new tests itself; the frozen tests of 002, 003 and 005 do not change.

## Requirements (EARS)

- **R022-01** (amends R003-09; question C) A write to `.git/config` shall be denied (compared
  case-insensitively, R003-06), whatever `[guard] allow_globs` says, because that file can set
  `core.hooksPath`. Reads of it stay allowed (R003-12).
- **R022-02** (amends R005-11; question D) A `[manual]` or `[removed]` marker shall count only
  outside inline code: text between a pair of backticks on the same line is ignored when
  R005-11 looks for markers. An unpaired backtick does not start inline code.
- **R022-03** (amends R002-31 and R005-18; question F) If `lock freeze --spec NNN --force` (or
  `freeze(cfg, spec=NNN, force=True)`) targets a spec in phase `dropped`, then it shall exit 1
  and write nothing, saying the spec is dropped, before any console confirmation is asked.
- **R022-04** (amends R002-33; question G) `audit()` shall also run `chaos.audit(cfg,
  base=REF, staged=staged)` when the chaos log is absent from the worktree (or the index, with
  `--staged`) but exists at REF, so deleting the log fails `lock audit`, pre-commit and CI.
  With no chaos log at REF either, `audit()` is unchanged.

## Public API contract

No new public names. The changes live behind existing functions:

```text
agentkit/guard.py:  evaluate(...)                     # R022-01, through the existing deny rules
agentkit/specs.py:  spec_requirements(cfg, spec)       # R022-02
agentkit/lock.py:   freeze(cfg, ..., spec=..., force=True), audit(cfg, base, staged)  # R022-03, R022-04
agentkit/cli.py:    lock freeze --spec NNN --force    # R022-03 exit code
```

Tests use only those entry points and `tests/support.py` / `tests/chaos_fixtures.py` fixtures.

## Examples and edge cases

- Edit `.git/config` → deny. Edit `.GIT/Config` on a case-insensitive comparison → deny.
  Read `.git/config` → allow. `[guard] allow_globs = [".git/**"]` → still deny.
- `- **R005-11** A requirement containing `[manual]` …` (marker in backticks) → traced.
  `- **R009-03** … [manual]` → excluded. ``- **R009-04** a ` lone backtick … [manual]`` →
  excluded.
- Spec 017 is `dropped`; the owner runs `lock freeze --spec 017 --force` → exit 1, no prompt,
  lock and unfreeze log unchanged.
- The chaos log exists at `origin/main` and is deleted in the worktree → `lock audit --base
  origin/main` exits 1 with `chaos.audit`'s deletion problem. No log at REF or in the worktree
  → no chaos problems.

## Out of scope

- `.git/hooks/**` and other files under `.git/` (only `.git/config` was decided).
- Narrowing R003-13 (question A: the owner kept the literal rule).

## Open questions

None. Every requirement records an owner decision of 2026-10-03.
