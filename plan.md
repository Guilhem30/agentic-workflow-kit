# Plan: Agentic Workflow Kit

The working plan (2026-10-03). The approved specs cite its sections.

## Context

You want a generic, reusable agentic-programming workflow kit. It must not be tied to any
language or to Claude: it should work in any language and with any LLM or agent tool. It ships
full adapters for Claude Code and the most popular open-source agent CLIs as of September 2026.

The process it packages, and that the kit is itself built with:

**spec → tests → (owner) freeze → implement until the frozen tests pass.**

Tests never change without your agreement. Token usage stays low without hurting code quality or
speed much.

## Decisions you made

| Topic | Decision |
|---|---|
| Kit location | This repo, `agentic-workflow-kit`, standalone. The kit installs itself, so it is its own first user. |
| Adapters | **Full** adapters for Claude Code, Codex CLI, OpenCode, DeepSeek Harness and Pi |
| Gates | **You approve every gate** (spec approved → tests approved → freeze) |
| Frozen tests | Edits are **hard-blocked**. Only you unfreeze, by running a command yourself, and every unfreeze is logged. |
| CI | Each project picks its CI providers and OSes at install time; the kit's own CI runs on Linux, Windows and macOS |

## Where we are

- **Specs 000–019 are approved** (`specs/README.md`). Each spec's *Additions beyond plan.md*
  and *Open questions* sections record the decisions made during review.
- **Tests for 001 and 002 are written** (`tests/test_001_*.py`, `tests/test_002_*.py`,
  `tests/support.py`) and the specs were clarified to match. They are **awaiting your
  approval**.
- **Stubs** in `agentkit/` (`config.py`, `lock.py`, `cli.py`, `util.py`) raise
  `NotImplementedError("<REQ-ID>")`. The suite runs 151 tests, and all of them currently error
  on those stubs. That is the expected red state.
- **Bootstrap instance** (`docs/adr/0001-bootstrap-instance.md`): the repo has hand-written
  `AGENTS.md`, `CLAUDE.md`, skills, review roles, Claude settings and `agentkit.toml`, so the kit
  is built with its own practices before `install` exists. The state of each active spec lives
  in its `progress.md`. Specs 001 and 002 are in phase `tests-draft`.
- The early prototype spike was deleted. It is still in git history (commit `af0a18a`).

## Research findings (condensed)

**Instruction and skill standards:**
- **AGENTS.md** is the cross-tool instruction file standard (Linux Foundation AAIF). Claude Code
  reads it only when there is no CLAUDE.md, or when a CLAUDE.md imports it with `@AGENTS.md`.
  **Using the import avoids paying for the same tokens twice.**
- **Agent Skills** (`SKILL.md`, agentskills.io) is an open standard supported by 30+ tools.
  Skills load progressively: about 30–50 tokens per skill at startup, and the full body only
  when the skill is used.

**Top open-source agent CLIs (Aug–Sep 2026, by stars):**

| Agent | Stars | License | What it supports |
|---|---|---|---|
| DeepSeek Harness | ~203k | MIT | Everything is a plugin. Reads AGENTS.md, falling back to CLAUDE.md. Its hook-bridge plugins run existing Claude Code / Codex `hooks.json`. |
| OpenCode | ~202k | MIT | `.opencode/plugins/` with a `tool.execute.before` hook (throwing an error blocks the call) and a `session.idle` event. Provider-agnostic, including local models. |
| Codex CLI | ~119k | Apache-2.0 | `.codex/hooks.json` with a **schema almost identical to Claude Code's**: PreToolUse/Stop, exit code 2 or `permissionDecision: deny`. File edits go through `apply_patch`. Project hooks need a trust step. Skills live in `.agents/skills`. |
| Pi | ~98k | MIT | A minimal harness with a system prompt under 1k tokens, lazily loaded skills, and extensions |

- Gemini CLI was **retired on 18 June 2026**. Its successor, Antigravity CLI, is closed source,
  and its open-source fork lives on as Qwen Code. Aider has been inactive since May 2026.
- Goose, Cline, OpenHands and Crush are covered by the tool-neutral baseline only.

**Claude Code practice:** CLAUDE.md under 200 lines; path-scoped `.claude/rules/`; skills for
workflows; hooks for deterministic gates; subagents to isolate verbose work; prompt-cache
hygiene; model and effort routing; hooks that filter command output before the agent reads it.

**Spec-driven development:** Spec Kit / Kiro style. One folder per feature
(`spec.md`/`plan.md`/`tasks.md`), **EARS** requirements with stable IDs, and a constitution of
rules that do not change without an ADR.

---

## Part A: the kit

### Design principles (spec 000 constitution)

1. **Enforcement lives in tool-neutral layers.** These are the lock file, git hooks and CI, which
   work with any agent, any LLM and any human. Each agent's own hooks are an early warning on
   top, never the guarantee.
2. **One source of truth, thin adapters.** AGENTS.md, `.agents/skills/`, role prompts and the CLI
   are neutral. Adapters only wire them into each tool, and generated copies are checked for drift.
3. **Zero dependencies, cross-platform.** Python stdlib only (3.11+, for `tomllib`), on Windows,
   macOS and Linux. Language specifics live only in **profiles** (TOML).
4. **The kit uses its own process.** It is specified, tested and frozen like any user project, and
   it installs itself.
5. **The human owns the gates.** No kit command lets an agent approve a gate or unfreeze a test.
6. **Token economy by default** (Part B).

### Layout

```
agentic-workflow-kit/
  README.md                 quickstart (2 commands), command list, capability matrix
  AGENTS.md, CLAUDE.md      the kit's own instructions (self-hosted, 019)
  plan.md                   this plan
  specs/                    000–019, one folder per spec
  workflow/
    WORKFLOW.md             spec → tests → freeze → implement, gates, roles, unfreeze protocol
    TOKEN-EFFICIENCY.md     tool-neutral token playbook (Part B)
    templates/              AGENTS.md.tmpl, spec.md, plan.md, tasks.md, progress.md, adr.md
    roles/                  spec-writer, spec-reviewer, test-writer, test-auditor, implementer,
                            impl-reviewer, summarizer (model-neutral, each tagged with a tier)
  skills/                   Agent Skills: kickoff/, feature/, spec/, write-tests/,
                            freeze/, implement/, handoff/
  agentkit/                 Python package (`python -m agentkit …` or `.agentkit/bin/agentkit`)
    config.py lock.py guard.py specs.py trace.py status.py handoff.py runtests.py
    codemap.py lint_instructions.py install.py sync.py
    payloads/               claude, codex, opencode, dsh, pi → neutral actions
  profiles/                 python-unittest, python-pytest, node-ts, go, rust-cargo, dotnet,
                            kotlin-gradle, generic (.toml)
  adapters/                 claude-code/, codex/, opencode/, deepseek-harness/, pi/, README.md
  githooks/                 pre-commit (lock verify + instruction lint), commit-msg
  ci/                       github-actions.yml, gitlab-ci.yml
  tests/                    unittest suite, payload fixtures, per-profile fixture repos
  tests.lock.json           the kit's own frozen tests
  tests.unfreeze-log.md
```

### `agentkit` CLI (the tool-neutral core)

| Command | Spec | Purpose |
|---|---|---|
| `install`, `update`, `sync [--check]` | 010 | Install the core, templates, skills, githooks, CI and chosen adapters; update without overwriting your customisations (3-way via manifest); regenerate derived copies, `--check` fails on drift |
| `lock freeze / verify / status / unfreeze / restore / audit` | 002 | SHA-256 per frozen file after CRLF→LF normalisation; owner-only unfreeze, logged to `tests.unfreeze-log.md` |
| `guard`, `verify` | 003, 004 | Read a tool's hook payload, turn it into Write/Read/Shell actions, answer allow/ask/deny in that tool's format; end-of-turn lock check |
| `new-spec`, `spec-status`, `trace` | 005 | Spec folders and phases (incl. `dropped`), automatic numbering, `depends`; every requirement ID of an approved spec appears in a test |
| `status`, `handoff NNN` | 006 | ≤ 10-line session summary; `progress.md` so sessions can be cleared cheaply |
| `test [scope]` | 007 | Run the profile's tests quietly, parse JUnit XML, print summary + failures (60-line cap) |
| `codemap [--check]` | 008 | Compact `docs/CODEMAP.md` of modules, files and public symbols |
| `lint-instructions` | 009 | Token budgets: AGENTS.md ≤ 150 lines, CLAUDE.md ≤ 40, SKILL.md ≤ 500, descriptions ≤ 200 chars, no duplicated blocks |
| `models` | 001 | Show tier → model mapping per adapter |
| `pre-commit`, `check-commit-msg` | 018 | Git hook entry points |
| `version` | 000 | |

### Enforcement layers (identical for every agent)

| Layer | Works with | What |
|---|---|---|
| `tests.lock.json` + `lock verify` | everything | Source of truth for frozen files |
| Agent pre-tool guard | Claude Code, Codex, OpenCode, DeepSeek Harness, Pi | **Denies** writes, moves and deletes of frozen paths, edits to lock and guard files, and `lock unfreeze` |
| Agent end-of-turn verify | same five | Blocks or re-prompts the agent if the lock fails to verify |
| Agent permission config | Claude Code `permissions`, Codex sandbox and approvals, OpenCode `permission` | Deny direct edits to the lock and unfreeze log; ask before edits to the guard, hooks and CI; deny reads of build outputs |
| git `pre-commit` | any agent or human | Lock verify + instruction lint. `--no-verify` is forbidden by instructions and caught by CI. |
| CI | any | Lock verify + `sync --check` + tests. CODEOWNERS on tests and lock where the host supports it. |

No local layer can stop an agent that deliberately bypasses it with shell access. Stacking the
layers turns any bypass into **a visible event that blocks the build**.

### Adapters

"Full" means instructions + skills + guard + end-of-turn verify + roles/subagents + model
routing + permissions, wherever the tool supports each.

| Tool | Spec | Instructions | Skills | Guard / verify | Roles → subagents | Model tiers |
|---|---|---|---|---|---|---|
| Claude Code | 012 | `CLAUDE.md` = `@AGENTS.md` + ~20 Claude-only lines | `.claude/skills/` (synced) | `.claude/settings.json` PreToolUse, Stop, SessionStart (`status`) | `.claude/agents/*.md` | `strong=opus`, `standard=sonnet`, `fast=haiku`, effort per skill |
| Codex CLI | 013 | AGENTS.md (native) | `.agents/skills/` (native) | `.codex/hooks.json` (PreToolUse incl. `apply_patch`, Stop); one-time `/hooks` trust step by you | Codex subagents | `config.toml` profiles |
| OpenCode | 014 | AGENTS.md (native) | per current docs | `.opencode/plugins/agentkit.ts`: `tool.execute.before` → guard, `session.idle` → verify | `.opencode/agent/*.md` | from `agentkit.toml` |
| DeepSeek Harness | 015 | AGENTS.md (native) | native skills plugin | `hooks-codex` bridge reuses `.codex/hooks.json` | `subagent-*` plugins | dsh config |
| Pi | 016 | AGENTS.md via its loader | lazy skills | Pi extension calling `guard` / `verify` | none (Pi stays minimal) | Pi model config |

Each adapter is built against the tool's **official docs fetched at implementation time**, and
`adapters/README.md` records the URL and date. Each one gets **conformance tests**: recorded hook
payloads fed to `guard`, with the expected decision checked. Missing capabilities are documented
and covered by the neutral layers. Tiers live in `agentkit.toml` under
`[models] strong/standard/fast`, so any provider works, local models included.

### Profiles (017)

Each profile sets `test_cmd` / `test_one_cmd`, `junit_report_glob` (or `output_filter_regex`),
`frozen_globs`, `source_globs`, `build_output_globs`, `req_id_regex`, codemap symbol regexes,
format/lint commands and `ci_setup`.

- `python-unittest` is the profile the kit uses for itself.
- `python-pytest`, `node-ts` (Vitest), `go`, `rust-cargo`, `dotnet`, `kotlin-gradle` and
  `generic` are presets. Each one is covered by a smoke test on a tiny fixture repo that checks
  globs, `trace`, `codemap` and build-output matching without running the language toolchain.

---

## Part B: Token-efficiency strategy (kit default)

**1. Small always-loaded context.** Target: about 3k tokens at session start. AGENTS.md
≤ 150 lines; CLAUDE.md is the `@AGENTS.md` import plus tool-only notes; path-scoped rules and
on-demand skills; docs linked, not imported. `lint-instructions` enforces it.

**2. No exploration tax.** `docs/CODEMAP.md` and `docs/architecture.md` map the code up front.
Each spec's **public API contract** says where code goes. Use LSP / code-intelligence plugins
where the tool supports them.

**3. Compressed tool output.** `agentkit test` prints only the summary and failures. Test
commands run in quiet mode. Reads of build outputs are denied. Golden files are compact text.

**4. Short sessions that resume from files.** One spec phase per session, `/clear` between
phases. State lives in files: spec `status:`, `tasks.md` checkboxes, `progress.md` from
`handoff`. Session-start `status` ≤ 10 lines. Compaction keeps spec ID, phase and failing tests.

**5. Model and effort routing without losing quality.**
- **Specs, tests and audits: strong model, high effort.** Frozen tests are permanent.
- **Implementation: standard model, medium effort.** The frozen tests are the oracle.
- **Summarising and exploration: fast model** in subagents, keeping verbose output out of the
  main context. Trivial shell or git steps never go to a subagent.

**6. Prompt-cache hygiene.** Stable instruction files; no edits to instructions, settings or MCP
servers mid-session; CLIs over MCP servers by default; no idle gaps longer than the cache
lifetime during active work.

**7. Fast loops.** Targeted tests (`test_one_cmd`) while implementing; the full check only
before a commit; the toolchain's own caches enabled.

**8. Measure.** Status line shows context % (Claude); `/usage` per skill and subagent;
`TOKEN-EFFICIENCY.md` holds the budgets.

---

## Execution order

Each step follows the per-feature cycle below. Order follows `specs/README.md`.

1. **Gate: approve the 001/002 tests** (now). Then implement 001 and 002, plus the 005 status
   functions they need (`specs.PHASES`, `find_spec`, `set_status`), until those tests pass.
2. **Bootstrap freeze:** you run the kit's own `lock freeze` on the 001/002 tests and on
   `tests/support.py` (by path). From here the kit protects its own tests.
3. **Spec lifecycle first:** 005 specs-and-trace, then 006 status/handoff. They carry automatic
   numbering, `dropped`, `depends` and the `blocked by` status, which back the `/kickoff` and
   `/feature` skills already in use (owner's request, 2026-10-03). Then 003 guard.
4. **Core services:** 004 hook dialects, 007 test runner, 008 codemap, 009 lint-instructions.
5. **Distribution and content:** 010 install/update/sync, 011 workflow content (WORKFLOW.md,
   TOKEN-EFFICIENCY.md, templates, roles, skills).
6. **Adapters:** 012 Claude Code first, then 013 Codex, 014 OpenCode, 015 DeepSeek Harness,
   016 Pi. Each against current official docs, each with conformance tests.
7. **017 profiles, 018 githooks and CI.**
8. **019 self-hosting:** the kit installs itself (`--self --profile python-unittest
   --adapters claude-code --ci github --ci-os linux,windows,macos --models kit`), README and
   adapter matrix. It replaces the hand-written bootstrap instance (ADR 0001).

Commits follow the pattern so far: `spec(NNN)`, `test(NNN)`, `feat(NNN)`, `chore:`. I commit
only what you have agreed to at each gate.

### Per-feature cycle

1. Spec: written, reviewed by the spec-reviewer role, **you approve** (done for 000–019).
2. Tests: stubs raising `NotImplementedError("<REQ-ID>")` + tests that fail →
   `agentkit trace` (once 005 exists) → test-auditor review → **you approve**.
3. Freeze: **you** run `lock freeze --spec NNN`; commit `test(NNN)` with the lock.
4. Implement: targeted tests → full suite → impl-reviewer looks for test-gaming → `feat(NNN)`.

If writing tests exposes a gap in a spec, the spec is clarified first and the change is shown
to you (as was done for 001/002).

## Verification

- **Suite:** `python -m unittest discover -s tests` is green on Linux, Windows and macOS. It covers
  lock, guard (every payload format, including Codex `apply_patch` parsing), trace, status,
  handoff, test-output summariser, codemap, lint-instructions, install/update/`sync --check`
  against temporary fixture repos for 2+ profiles, and per-profile smoke tests.
- **Self-hosting:** the kit's own `lock verify`, `lint-instructions`, `sync --check` and
  pre-commit pass on a clean checkout. Every approved kit test is in `tests.lock.json`.
- **Guard demo** (in a throwaway fixture repo, Claude Code): freeze a dummy test, then
  - edit it with the Edit tool → denied;
  - change it from the shell → the Stop hook blocks;
  - `git commit` → pre-commit rejects it;
  - `lock unfreeze` run by you in your own terminal → allowed and logged.

  Then delete the fixture repo.
- **Other adapters:** conformance tests prove the guard's decisions on recorded payloads. A live
  check is optional if you have the CLI installed (Codex needs the hook trust step first).
- **Token budget:** `lint-instructions` passes; the always-loaded instruction size is reported
  against the ~3k-token target.
- **In your own Claude Code session:** `/context` shows CLAUDE.md + AGENTS.md loaded once, not
  twice.
