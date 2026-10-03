# Priorities: remaining plan.md work and token savings (2026-10-03)

## Where we are

- **Done:** 001 config, 002 lock, 003 guard, 005 specs/trace (all through `chaos approve`).
- **In flight:** 004 hook-dialects. The spec was amended, `/write-tests` has started, and the work
  is not committed yet (`agentkit/payloads/`, `tests/hook_fixtures.py`).
- **Frozen:** 020 chaos mode. Its last 16 errors wait on the 006 status stub.
- **Approved, not started:** 006–019, 021.
- **Measured cost of one spec:** about 8–10 commits, 2–3 impl-reviewer passes and 1–2 test-auditor
  passes. All reviewers run on opus at high effort. Fix commits make up 11 of the 81 commits so far.

## Priority order

The order is ranked by what pays back on every later spec, then by plan.md dependencies.

| # | Spec | Why now | Savings |
|---|---|---|---|
| 1 | **004** hook-dialects | Already in flight. Unblocks 012–016. | Reuse `hook_fixtures.py` for every adapter's conformance tests |
| 1b | **022** owner decisions | Small (4 requirements). Turns the owner's answers C, D, F and G into tests and code. | None |
| 2 | **006** status/handoff | Closes 020 (`chaos approve 020 done`). A ≤ 10-line `status` replaces reading the README, progress.md and the chaos log at session start. | High: every session |
| 3 | **007** test runner | `agentkit test` prints the summary and failures only (60-line cap). Every implement loop and review pass runs the suite. | High: every test run |
| 4 | **009** lint-instructions | Enforces the ~3k-token startup budget. Catches growth in AGENTS.md, skills and progress.md. | Medium, ongoing |
| 5 | **008** codemap | `docs/CODEMAP.md` removes exploration reads during implement and reviews. | Medium |
| 6 | **010** install/update/sync | Replaces `scripts/bootstrap_sync.py`. Needed by 011 and the adapters. | None (needed for distribution) |
| 7 | **011** workflow content | WORKFLOW.md, TOKEN-EFFICIENCY.md, templates, roles. Expect an escalation (AGENTS.md, roles/). | Indirect |
| 8 | **012** Claude Code adapter | The adapter we use ourselves: guard, Stop verify, SessionStart `status`. | High: hooks replace manual checks |
| 9 | **018** githooks + CI | The tool-neutral guarantee layer (pre-commit lock verify). | Fewer manual `lock verify` runs |
| 10 | **017** profiles | Presets with smoke tests only. Mechanical work. | None |
| 11 | **013** Codex → **015** DeepSeek Harness | 015 reuses Codex's `hooks.json` and is the smallest spec (51 lines). | None |
| 12 | **014** OpenCode, **016** Pi | Independent adapters. | None |
| 13 | **019** self-hosting | Last, because it depends on everything. Replaces the bootstrap instance (ADR 0001). | Drops hand-written duplicates |
| — | **021** autopilot | Optional. It saves owner turns, not model tokens. Do it after 012 or defer it. | Low |

Changes from plan.md's order: 006 and 007 move ahead of 008 and 009 because they cut the cost of
every later cycle. 018 moves ahead of 017 and the non-Claude adapters because it is the guarantee
layer the chaos gates lean on.

## Token savings beyond plan.md Part B

### Process (apply now, no code)

1. **One full review, then a diff-scoped re-check.** After the first test-auditor or impl-reviewer
   pass, the second pass gets only the fix diff and the findings list, not the whole spec. Stop at 2
   passes. A third pass needs a new blocking finding. This cuts most of today's 2–3 full opus passes.
2. **Reviewer tiers by risk.** The test-auditor stays on opus/high, because frozen tests are
   permanent. The impl-reviewer moves to sonnet/high: the frozen tests are the oracle, and it hunts
   for gaming, not design flaws. Use opus only for 002/003/020-class security code.
3. **Scope the reviewer prompt.** Give the reviewer the requirement IDs, the contract section and the
   list of changed files. Today it re-reads the spec cold.
4. **Combine phases for small specs under chaos:** 008, 015, 016, 017, 019 (≤ 72 lines each).
   Run write-tests, audit, freeze and implement in one session with one handoff, which saves a
   cold-start re-read per phase.
5. **Prune progress.md at handoff.** Keep the snapshot block and the open owner questions. Move the
   history to git (the commits already hold it). 003 and 005 are at 39–49 lines and growing.
6. **Batch owner questions.** Answer open questions in one sitting; each one otherwise costs a
   stop, a resume and a re-read. (Done 2026-10-03: A–H settled, the behaviour changes are in 022.)
7. **Quiet test output until 007 lands.** Run
   `python3 -m unittest discover -s tests 2>&1 | tail -3`, and with failures,
   `grep -E '^(ERROR|FAIL):'`. Never read the full traceback dump into the main context. Hand
   failure digging to `summarizer` (haiku).

### Kit features (fold into existing specs, no new spec)

8. **SessionStart hook → `agentkit status`** (012, needs 006). It replaces the "read the README +
   progress.md" ritual in AGENTS.md.
9. **PostToolUse output filter** (012/007). Truncate Bash output from test commands to the summary.
   This is plan.md Part A's "hooks that filter command output".
10. **`trace --spec NNN` as the coverage check** (exists, 005). Drop the manual grep row from
    AGENTS.md's command table, which saves both lines and runs.
11. **Shrink AGENTS.md** (4.2 KB). The "Bootstrap state" and "Commands (bootstrap equivalents)"
    sections go away as 006, 007 and 018 land. Re-check with 009.
12. **Split the chaos specs.** 020 (401 lines) and 021 (357 lines) are 2–3× any other spec. Move
    their rationale and examples into ADR 0002 so implement sessions load only the requirements
    and contract.
13. **Allowlist read-only commands** (`/fewer-permission-prompts`). This saves round-trips more
    than tokens, but stops sessions stalling on `tests/**` asks during the chaos cycle.

## Applied directly (2026-10-03)

- Items 1–5 and 7: skills and roles (cheaper, shorter review loop; leaner handoff); progress.md
  files of 001, 002, 003, 005 and 020 cut to their snapshots.
- Item 10 and part of 11: AGENTS.md uses the real `agentkit` commands (`trace --spec`, quiet
  test runs) instead of the bootstrap equivalents.
- Part of 8: a bootstrap SessionStart hook (`scripts/session_start.py`) prints the resume point
  until 006 and 012 wire `agentkit status`.
- Part of 12: the applied amendments of 020 and 021 moved to ADR 0002's appendix.
- Item 13: read-only commands are allowed in `.claude/settings.json`, which also denies
  editing `.git/config` (decision C) until 022 lands.
- Still waiting on specs: item 9 (output filter, 007/012), the rest of 8 and 11 (006, 012, 018).

## Suggested next steps

1. Finish 004 in its own session (the uncommitted work belongs to it).
2. Done 2026-10-03: owner approved process items 1–5 and 7 (now in `.agents/skills/` and `roles/`) and
   the recommended answers A–H.
3. Run 022, then 006, then 007, applying the reduced review loop.
