---
id: "015"
title: DeepSeek Harness adapter
status: approved
---

# 015 DeepSeek Harness adapter

## Context

DeepSeek Harness (dsh) reads AGENTS.md. Its `@deepseek-ai/dsh-hooks-codex` bridge replays an
existing Codex `hooks.json`.

Facts checked on 2026-10-03 in `packages/hooks/hooks-codex/README.md` of
`deepseek-ai/deepseek-harness`:
- The bridge supports the events SessionStart, UserPromptSubmit, PreToolUse, PostToolUse and Stop.
- PreToolUse can only deny.
- Payloads are Codex-shaped, but `tool_input` is only `{command}`, so file-edit tool arguments
  are not exposed.
- The config is process-wide: `configPath` is read once at startup and resolved from the launch
  directory. Per-project discovery is a TODO upstream.

## Requirements (EARS)

- **R015-01** Selecting this adapter shall also select the `codex` adapter (R010-05). No new
  hook code is needed.
- **R015-02** The kit shall ship `adapters/deepseek-harness/profile.yml`, a plugin block that
  enables `@deepseek-ai/dsh-hooks-codex` with `configPath: ./.codex/hooks.json`, with comments
  explaining that dsh must be launched from the repo root.
- **R015-03** install shall print a note telling the owner to add that block to their dsh profile.
- **R015-04** `adapters/README.md` shall state the limitation:
  - with dsh, the guard sees shell commands only;
  - edits to frozen files through edit tools are caught by the Stop verify, pre-commit and CI,
    not before they happen.
- **R015-05** Conformance fixtures (R004-21) for `dsh` shall include a `{command}`-only edit
  payload (expected: allow) and a shell write to a frozen file (expected: deny).

## Public API contract

`adapters/deepseek-harness/profile.yml`; `adapters.dsh_kit(...)` returns no files.

## Additions beyond plan.bkp

- The plan assumed "same guard, no new code" with full coverage. The bridge's `{command}`-only
  payload makes edit-tool guarding impossible through it. That limitation is documented
  (R015-04).

## Open questions

None. (Decided 2026-10-03: a native dsh plugin is deferred to a later spec.)
