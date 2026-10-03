---
id: "000"
title: Kit vision and constitution
status: approved
depends: []
---

# 000 Kit vision and constitution

## Context

AI coding agents write code fast, but nothing stops them from editing the tests they are
supposed to satisfy, and their sessions burn tokens on exploration and verbose output. The
kit packages one process that works with any language, any LLM and any agent tool:

**spec → tests → (human) freeze → implement until the frozen tests pass.**

Tests never change without the human's agreement. Token usage stays low without hurting code
quality or speed much. The first real user is the kit itself (019).

## Personas

- **Owner**: the human. Approves every gate (spec approved, tests approved, freeze) and is the
  only one who unfreezes tests, except in chaos mode, which only the owner enables (020).
- **Agent session**: an LLM agent working in some tool (Claude Code, Codex CLI, OpenCode,
  DeepSeek Harness, Pi, or a tool with no adapter). Follows AGENTS.md. May be careless or try
  shortcuts.
- **CI**: a non-interactive runner that re-checks everything.

## Glossary

| Term | Meaning |
|---|---|
| Spec | `specs/NNN-slug/spec.md`: EARS requirements with stable IDs, plus an API contract |
| Phase | A spec's `status:` (see 005) |
| Gate | A phase transition that only the owner may approve, except in chaos mode, which only the owner enables (020) |
| Frozen file | A file recorded in the lock; it must not change |
| Lock | `tests.lock.json`: path → hash of each frozen file (002) |
| Unfreeze | The owner removes files from the lock; every unfreeze is logged |
| Profile | A TOML preset with a language's test command, globs and regexes (001, 017) |
| Adapter | Files that wire the neutral sources into one agent tool (012–016) |
| Dialect | How one tool's hook payloads and responses look (004) |
| Neutral action | WriteAction / ReadAction / ShellAction, which is what the guard judges (003) |
| Tier | A model class (`strong`, `standard`, `fast`), mapped to real models per tool (001) |
| Managed / derived file | A file installed from the kit, or one generated from the repo's neutral sources (010) |

## Principles (constitution: these do not change without an ADR)

1. **Enforcement lives in tool-neutral layers**: the lock, git hooks and CI. Agent hooks are an
   early warning on top, never the guarantee.
2. **One source of truth, thin adapters.** AGENTS.md, `.agents/skills/`, role prompts and the CLI
   are neutral. Adapters only wire them in. Generated copies are checked for drift.
3. **Zero dependencies, cross-platform.** Python standard library, 3.11 or later, on Windows,
   macOS and Linux. Language specifics live only in profiles.
4. **The kit uses its own process.** It is specified, tested and frozen like any user project,
   and it installs itself.
5. **The human owns the gates.** No kit command lets an agent approve a gate or unfreeze a test,
   except in chaos mode, which only the owner enables (020; ADR 0002).
6. **Token economy by default**: a small always-loaded context, compact tool output and model
   routing by tier (Part B of the plan, 011).

## Requirements (EARS)

- **R000-01** The kit's tooling shall run on CPython 3.11 or later using only the standard library.
- **R000-02** The kit's test suite shall pass on Windows, macOS and Linux. The kit's own CI
  runs on all three (019). Each project chooses its own CI environments at install time (010, 018).
- **R000-03** No agentkit command shall access the network.
- **R000-04** Every command shall be invocable both as `python .agentkit/bin/agentkit <command>`
  (installed) and as `python -m agentkit <command>` (from the kit repo).
- **R000-05** The core package (everything outside `payloads/` and the adapter generators) shall
  contain no behaviour specific to a programming language. Language specifics come from profiles. [manual]
- **R000-06** Tool-specific behaviour shall live only in the hook dialects (004) and adapter
  generators (012–016). [manual]
- **R000-07** Every text file written by agentkit shall be UTF-8 with LF line endings.
- **R000-08** Unless a command's spec states otherwise, commands shall exit 0 on success, 1 when a
  check fails, and 2 on a usage or configuration error.
- **R000-09** When a check fails, the command shall print the failing items and a one-line hint
  about how to proceed.
- **R000-10** No agentkit command shall offer a way for an agent to set a gate status
  (`approved`, `tests-approved`, `frozen`) or remove a file from the lock without the owner's
  involvement as specified in 002 and 005, except in chaos mode, which only the owner enables
  (020). [manual]

## Public API contract

The entry point is `agentkit/cli.py: main(argv: list[str] | None = None) -> int`.
Commands and their specs: `install`, `update`, `sync` (010); `lock …` (002); `guard`, `verify`
(003, 004); `status`, `handoff` (006); `trace`, `new-spec`, `spec-status` (005); `test` (007);
`codemap` (008); `lint-instructions` (009); `models` (001); `pre-commit`, `check-commit-msg` (018); `chaos …` (020); `autopilot` (021); `version`.

## Scope (v1)

All of the specs in `specs/README.md`. Adapters: Claude Code, Codex CLI, OpenCode, DeepSeek
Harness and Pi. Profiles: python-unittest (used by the kit itself), python-pytest, node-ts, go,
rust-cargo, dotnet, kotlin-gradle and generic (presets).

## Out of scope

- Making bypass impossible. An agent with shell access can always defeat local layers. The goal
  is that any bypass becomes visible and blocks the build.
- Adapters for Gemini CLI (retired June 2026), Aider (inactive), Goose, Cline, OpenHands and Crush.
  These are covered only by the neutral baseline (AGENTS.md, git hooks, CI).
- A GUI, a server, telemetry.

## Bootstrap

The lock cannot protect the kit's tests before the lock exists. So the order for the kit itself is:

1. The owner approves the specs.
2. Tests for 001 and 002 are written and the owner approves them.
3. The minimal lock (002) is implemented, together with the part of 005 that it needs: reading
   and setting a spec's status (`specs.PHASES`, `find_spec`, `set_status`).
4. Those tests and every later approved test are frozen by the owner with the kit's own `lock freeze`.
   Shared test helpers that contain no requirement ID (for example `tests/support.py`) belong to
   no spec, so the owner freezes them by path.

## Additions beyond plan.md

- Chaos autopilot (021 amendment, approved by the owner on 2026-10-03): the `autopilot` command.
- R000-08 (exit code convention), R000-09 and R000-10 make implicit plan intentions explicit.
- Chaos mode (020 amendment, ADR 0002, approved by the owner on 2026-10-03): the exception in
  principle 5, R000-10, the Owner persona, the Gate term, and the `chaos` command.
- The bootstrap order above: the kit's first tests are approved before any code is written, then
  frozen with the kit's own lock (plan.md, Execution order).
- Bootstrap steps 3 and 4 gained the 005 status functions and freezing shared helpers by path
  (owner's decision, 2026-10-03, after writing the 001/002 tests).

## Open questions

None. (Decided 2026-10-03: each project chooses its CI providers and operating systems when it
is installed, and may run several at once. See 010 and 018.)
