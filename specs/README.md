# Specs for agentic-workflow-kit

The kit is built with its own process: spec, then tests, then freeze, then implement. Every spec
below was derived from [`plan.md`](../plan.md) (Part A, Part B and the Verification section) on 2026-10-03.
All of them were **approved by the owner on 2026-10-03**. Decisions taken during the review are recorded in each spec's Additions and Open questions sections.

Each spec has a section **Additions beyond plan.md**. It lists the design choices the plan did
not make. Approve or reject them explicitly.

| ID | Spec | Depends on | Plan source |
|---|---|---|---|
| 000 | [kit-vision](000-kit-vision/spec.md): constitution, scope, glossary, roadmap | none | Context, Part A principles |
| 001 | [config-and-profiles](001-config-and-profiles/spec.md): `agentkit.toml`, profile loading, globs, model tiers | 000 | Part A Profiles, model tiers |
| 002 | [test-lock](002-test-lock/spec.md): freeze, verify, status, unfreeze, log | 001, 005 (spec status only) | `lock` commands |
| 003 | [guard](003-guard/spec.md): neutral actions and allow/ask/deny decisions | 001, 002 | `guard`, enforcement layers |
| 004 | [hook-dialects](004-hook-dialects/spec.md): per-tool payload parsing and responses, end-of-turn verify | 003, 006 | `payloads/`, conformance tests |
| 005 | [specs-and-trace](005-specs-and-trace/spec.md): spec folders, phases, requirement IDs, `trace` | 001 | `trace`, per-feature cycle |
| 006 | [status-and-handoff](006-status-and-handoff/spec.md) | 002, 005 | `status`, `handoff` |
| 007 | [test-runner](007-test-runner/spec.md): `agentkit test` compact summary | 001 | `test`, Part B §3 |
| 008 | [codemap](008-codemap/spec.md) | 001 | `codemap`, Part B §2 |
| 009 | [lint-instructions](009-lint-instructions/spec.md): token budgets | 001 | `lint-instructions`, Part B §1 |
| 010 | [install-update-sync](010-install-update-sync/spec.md) | 001 | `install`, `update`/`sync` |
| 011 | [workflow-content](011-workflow-content/spec.md): WORKFLOW.md, playbook, templates, roles, skills | 005, 009 | Layout: `workflow/`, `skills/` |
| 012 | [adapter-claude-code](012-adapter-claude-code/spec.md) | 004, 010, 011 | Adapters table |
| 013 | [adapter-codex](013-adapter-codex/spec.md) | 004, 010, 011 | Adapters table |
| 014 | [adapter-opencode](014-adapter-opencode/spec.md) | 004, 010, 011 | Adapters table |
| 015 | [adapter-deepseek-harness](015-adapter-deepseek-harness/spec.md) | 013 | Adapters table |
| 016 | [adapter-pi](016-adapter-pi/spec.md) | 004, 010 | Adapters table |
| 017 | [profiles](017-profiles/spec.md): language presets | 001 | Profiles |
| 018 | [githooks-and-ci](018-githooks-and-ci/spec.md) | 002, 009, 010 | Enforcement layers |
| 019 | [self-hosting-and-docs](019-self-hosting-and-docs/spec.md): README, adapter matrix, the kit installs itself | all | Principle 4, Verification |
| 020 | [chaos-mode](020-chaos-mode/spec.md): opt-in agent-approved gates, escalation on critical problems | 001, 002, 003, 005, 006 | Owner's idea, 2026-10-03 (not in plan.md) |
| 021 | [chaos-autopilot](021-chaos-autopilot/spec.md): `/autopilot NNN` runs a spec to done in chaos mode | 001, 002, 005, 006, 007, 011, 020 | Owner's idea, 2026-10-03 (not in plan.md) |

Suggested order: 000 and 001 first, then 002, 003 and 005 (the core), then 004, 006, 007, 008
and 009, then 010 and 011, then the adapters, 017, 018 and finally 019.
020 (chaos mode, approved 2026-10-03, ADR 0002; amendments applied) and 021 (`/autopilot`, approved 2026-10-03;
amendments applied) come after the specs they depend on.

Requirement IDs are `RNNN-MM`. Requirements marked `[manual]` are checked by a human, not by a
test.
