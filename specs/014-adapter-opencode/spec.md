---
id: "014"
title: OpenCode adapter
status: approved
---

# 014 OpenCode adapter

## Context

OpenCode reads AGENTS.md natively. It reads skills from `.opencode/skills/`, `.claude/skills/`
and `.agents/skills/`, so no copy is needed.

Facts checked on 2026-10-03 at [plugins](https://opencode.ai/docs/plugins/),
[agents](https://opencode.ai/docs/agents/) and [skills](https://opencode.ai/docs/skills/):
- Project plugins in `.opencode/plugins/` are loaded at startup.
- `tool.execute.before(input, output)` blocks when the handler throws.
- `shell.env(input, output)` sets environment variables for shells.
- A `session.idle` event exists.
- Agents are `.opencode/agents/<name>.md` with `description`, `mode` (`subagent`), `model`
  (`provider/model`) and `permission`.

## Requirements (EARS)

### Plugin `.opencode/plugins/agentkit.ts` (managed)
- **R014-01** The plugin shall run the configured python with `.agentkit/bin/agentkit guard --format opencode`
  for every tool call, sending `{tool, args, cwd}` on stdin (plugin protocol, R004-13).
- **R014-02** When the result's decision is not `allow`, the plugin shall throw an Error with the
  reason.
- **R014-03** If the guard process cannot run or returns invalid JSON, then the plugin shall apply
  degraded mode itself (consistent with R003-27). It throws for a write tool whose path matches
  the degraded globs, the lock, the unfreeze log, `agentkit.toml` or `.agentkit/**`, and
  otherwise allows the call and logs a warning. The degraded globs (R003-29) are rendered into
  the plugin at install time, so this works even when Python is missing.
- **R014-04** The plugin shall set `AGENTKIT_AGENT=1` through `shell.env`.
- **R014-05** On `session.idle`, the plugin shall run `verify --format opencode`. When `ok` is
  false, it shall send the message back to the session as a prompt, at most 2 times per session
  for the same violation set. After that it only logs.
- **R014-06** The plugin shall locate the repo root from the plugin context (`worktree`, else
  `directory`) and need no npm dependency at runtime.

### `opencode.json` (managed)
- **R014-07** opencode.json shall set `$schema` and bash permission denials for
  `*lock unfreeze*` and `git commit --no-verify*`.

### Derived agents (sync)
- **R014-08** For each role, sync shall write `.opencode/agents/<name>.md` with front matter:
  - `description`;
  - `mode: subagent`;
  - no `model` (OpenCode has no built-in map, R001-18);
  - `permission.edit` (`allow` if the role has `edit`, else `deny`);
  - `permission.bash` (`allow` if the role has `shell`, else `deny`).

  The body is a generated-file comment followed by the role body.

## Public API contract

The kit files are `adapters/opencode/agentkit.ts.tmpl` and `adapters/opencode/opencode.json.tmpl`.
The generator functions are `adapters.opencode_kit` and `adapters.opencode_derived`.

## Examples and edge cases

- An `edit` with `filePath` set to a frozen file: guard denies it and the plugin throws.
- Python missing on PATH: an `edit` of `core/src/test/FooTest.kt` is still refused (degraded globs
  rendered into the plugin). An `edit` of `core/src/main/Foo.kt` is allowed with a warning.

## Additions beyond plan.bkp

- The re-prompt limit (R014-05), the in-plugin degraded mode (R014-03), and the opencode.json bash denials.

## Open questions

1. The exact SDK call to re-prompt a session from `session.idle` is not in the plugin docs. This
   draft assumes `client.session.prompt`. It must be confirmed against the SDK at implementation
   time; if it is unavailable, fall back to `client.app.log` plus a toast.
