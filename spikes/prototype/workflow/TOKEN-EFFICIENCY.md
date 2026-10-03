# Token efficiency playbook

Tool-neutral defaults, enforced where possible. The goal is fewer tokens with no loss of
quality, because quality is protected by the frozen tests and by spending strong-model tokens
where they matter.

## Budgets

| Item | Budget | Enforced by |
|---|---|---|
| Always-loaded instructions (AGENTS.md + CLAUDE.md + skill descriptions + unscoped rules) | ~3k tokens | `lint-instructions` (warning) |
| AGENTS.md | 150 lines | `lint-instructions` |
| CLAUDE.md | 40 lines, `@AGENTS.md` import plus tool-only notes | `lint-instructions` |
| Path-scoped rule file | 80 lines | `lint-instructions` |
| SKILL.md | 500 lines; description 200 chars | `lint-instructions` |
| Duplicated block across instruction files | none (3+ identical lines) | `lint-instructions` |
| Session-start status | 10 lines | `status` |
| Test output shown to the agent | 60 lines | `test` |

## 1. Small always-loaded context

- One source: AGENTS.md. CLAUDE.md imports it with `@AGENTS.md`, so it is never duplicated.
- Path-scoped rules (`.claude/rules/*.md` with `paths:`) load only for matching files.
- Skills load progressively: the description at startup, the body only when used.
- Link documents instead of pasting them.

## 2. No exploration tax

- `docs/CODEMAP.md` (`agentkit codemap`) lists modules, files and public symbols.
- Each spec's public API contract says where code goes.
- Use code intelligence (LSP, go to definition) where the tool has it, rather than grep then read.

## 3. Compressed tool output

- `agentkit test` runs the profile's quiet test command, parses JUnit XML and prints the summary
  plus failures only. The raw log stays in `.agentkit/state/last-test.log`.
- The guard denies reads of build outputs (`build_output_globs`).
- Golden files are compact text (ASCII grids), not images.

## 4. Short sessions that resume from files

- One phase per session, then `handoff` and clear the context.
- `status` at session start (a hook where the tool supports it) is 10 lines.
- The state is in the spec status, `tasks.md` and `progress.md`, not in the conversation.

## 5. Model and effort routing

- Strong tier, high effort: specs, tests, audits, implementation review.
- Standard tier, medium effort: implementation against frozen tests.
- Fast tier: summarising logs, docs and broad searches in a subagent, so the verbose output
  stays out of the main context.
- Never delegate trivial shell or git steps: a subagent's startup costs more than it saves.

## 6. Prompt-cache hygiene

- Keep instruction files stable. Do not edit instructions, settings or MCP servers mid-session.
- No MCP servers by default: CLIs (git, build tools, adb) cost nothing until used.
- Avoid idle gaps longer than the cache lifetime during active work.

## 7. Fast loops

- Targeted tests (`agentkit test <scope>`) while implementing, the full suite before committing.
- Enable the build tool's caches and daemons (speed, not tokens).

## 8. Measure

- Claude Code: the status line shows context %; `/context` and `/usage` give breakdowns.
- `lint-instructions` prints the estimated always-loaded size on every run.
