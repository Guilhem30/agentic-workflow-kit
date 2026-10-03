# agentic-workflow-kit

A language-neutral, agent-neutral kit for agentic programming. It packages one process:

**spec → tests → owner freeze → implement until the frozen tests pass.**

Tests never change without the owner's agreement, and token usage stays low by default. The kit
targets Claude Code, Codex CLI, OpenCode, DeepSeek Harness and Pi, plus a tool-neutral baseline
(AGENTS.md, git hooks, CI) for any other agent. It is Python 3.11+ with the standard library only.

## Status

Under construction, built with its own process.
- Specs 000–019 are approved.
- The tests for 001 (config) and 002 (test lock) are written and awaiting owner approval.
- The `agentkit` CLI is still stubs, so there is no quickstart yet. Spec 019 adds the two-command
  install, the command list and the adapter capability matrix.

## Where to look

- [`plan.md`](plan.md): the plan and the decisions behind it
- [`specs/README.md`](specs/README.md): the specs, their dependencies and their order
- [`AGENTS.md`](AGENTS.md): instructions for agents (and humans) working on the kit
- [`docs/adr/`](docs/adr/): decisions, starting with the
  [bootstrap instance](docs/adr/0001-bootstrap-instance.md)
