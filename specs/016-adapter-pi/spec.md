---
id: "016"
title: Pi adapter
status: approved
depends: ["004", "010"]
---

# 016 Pi adapter

## Context

Pi is a minimal harness. It reads AGENTS.md and the Agent Skills locations `.agents/skills/`
natively, and loads project extensions from `.pi/extensions/` once project trust is granted.

Facts checked on 2026-10-03 in `packages/coding-agent/docs/{extensions,configuration}.md` of
`badlogic/pi-mono`:
- An extension is a TS module with a default export `(pi: ExtensionAPI)`.
- `pi.on("tool_call", (event, ctx))` can return `{block: true, reason}`.
- `event.toolName` names the tool.
- `ctx.ui.confirm` asks the user.
- The `agent_end` event fires when a run finishes.
- `pi.sendUserMessage()` sends a message.
- A handler error blocks the tool (fail-safe).

## Requirements (EARS)

- **R016-01** The kit shall install `.pi/extensions/agentkit.ts` (managed).
- **R016-02** On `tool_call`, the extension shall run `guard --format pi` with
  `{tool: event.toolName, args: <event input>, cwd}`.
  - When the decision is `deny`, it returns `{block: true, reason}`.
  - When it is `ask` and a UI is available, it asks with `ctx.ui.confirm` and blocks if the user
    declines. Without a UI, ask blocks.
- **R016-03** If the guard process cannot run or returns invalid JSON, then the extension shall
  apply degraded mode itself, as in R014-03, with the degraded globs rendered at install time.
  It catches every other error, so that Pi's fail-safe (a handler error blocks the tool) does not
  block all tools.
- **R016-04** The extension shall set `process.env.AGENTKIT_AGENT = "1"` when it loads, so that
  shells spawned by Pi inherit it.
- **R016-05** On `agent_end`, the extension shall run `verify --format pi`. When `ok` is false,
  it shall send the message with `pi.sendUserMessage`, at most 2 times for the same violation set.
- **R016-06** The extension shall find the repo root by walking up from the cwd to the directory
  that contains `agentkit.toml`. It needs no npm dependency at runtime.
- **R016-07** No roles or subagents are generated for Pi. Model tiers are left to the user's Pi
  config, which `adapters/README.md` explains.
- **R016-08** install shall print a note that the owner must accept project trust in Pi.

## Public API contract

`adapters/pi/agentkit.ts.tmpl`; `adapters.pi_kit(...)`.

## Additions beyond plan.md

- Ask handled through `ctx.ui.confirm`; the in-extension degraded mode and the re-prompt limit.

## Open questions

1. The exact shape of the `tool_call` event's input field (`event.input`?) and the signature of
   `sendUserMessage` are not fully documented. They must be confirmed in the Pi source at
   implementation time.
