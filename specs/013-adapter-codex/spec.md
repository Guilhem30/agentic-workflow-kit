---
id: "013"
title: Codex CLI adapter
status: approved
---

# 013 Codex CLI adapter

## Context

Codex reads AGENTS.md and `.agents/skills/` natively. Its hooks live in `.codex/hooks.json`,
with a schema close to Claude Code's.

Facts checked on 2026-10-03 at [hooks](https://learn.chatgpt.com/docs/hooks) and the Codex
subagents documentation:
- hooks.json has the shape `{"hooks": {"<Event>": [{"matcher"?, "hooks": [{"type": "command",
  "command", "commandWindows"?, "timeout" (seconds), "statusMessage"?}]}]}}`.
- Hooks run with the session cwd as their working directory.
- `apply_patch` sends the patch text in `tool_input.command`. Only deny works (`ask` is
  unsupported).
- Project hooks run only after the user trusts them with `/hooks`.
- Custom agents are `.codex/agents/*.toml` with `name`, `description` and
  `developer_instructions`, and optionally `model`, `model_reasoning_effort` and `sandbox_mode`.

## Requirements (EARS)

### `.codex/hooks.json` (managed)
- **R013-01** hooks.json shall register:
  - `SessionStart`, running `status --format codex`;
  - `PreToolUse`, with a matcher covering `Bash`, `apply_patch`, `Edit`, `Write` and
    `exec_command`, running `guard --format codex`;
  - `Stop`, running `verify --format codex`.
- **R013-02** Each hook's `command` shall locate the launcher from the git top-level directory,
  so that it works from any session cwd: `python3 "$(git rev-parse --show-toplevel)/.agentkit/bin/agentkit" …`
  (with the configured python). `commandWindows` shall use the configured python with a path
  relative to the repo root.
- **R013-03** Each hook shall set a `timeout` of at most 30 seconds and a short `statusMessage`.

### `.codex/config.toml` (managed)
- **R013-04** config.toml shall set `shell_environment_policy.set.AGENTKIT_AGENT = "1"`,
  `sandbox_mode = "workspace-write"` and `approval_policy = "on-request"`.

### Derived agents (sync)
- **R013-05** For each role, sync shall write `.codex/agents/<name with - replaced by _>.toml`
  with:
  - `name`, `description`;
  - `developer_instructions` (the role body, as a TOML multi-line literal string when possible);
  - `model` (in `kit` mode only, R001-17);
  - `model_reasoning_effort` (`low`/`medium`/`high`; `xhigh` and `max` map to `high`);
  - `sandbox_mode`: `read-only` when the role has neither `edit` nor `shell`, else
    `workspace-write`.
- **R013-06** Every generated TOML file shall parse with `tomllib`.

### Notes
- **R013-07** install shall print the post-install note that the owner must run `/hooks` once in
  Codex and trust the project hooks.

## Public API contract

The kit files are `adapters/codex/hooks.json.tmpl` and `adapters/codex/config.toml.tmpl`.
The generator functions are `adapters.codex_kit` and `adapters.codex_derived`.

## Additions beyond plan.md

- R013-02 (git top-level lookup), because hooks run in the session cwd.
- R013-04 values (the plan said "sandbox and approvals" without values).

## Open questions

None. (Decided 2026-10-03: keep `approval_policy = "on-request"`, so Codex asks before risky
actions.)
