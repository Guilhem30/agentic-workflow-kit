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
- The `agentkit` CLI is still stubs, so there is no install command yet. Spec 019 adds the
  two-command install, the full command list and the adapter capability matrix. Until then, the
  workflow below already works in this repository, using the manual stand-ins listed in
  [`AGENTS.md`](AGENTS.md).

## How the kit is used

Two people share the work:
- **You, the owner**, decide what gets built and approve every gate.
- **The agent** (Claude Code, Codex, OpenCode, …) does the writing.

**Starting a project.** Run `/kickoff` with your idea in a few sentences, for example:
`/kickoff A CLI that syncs my Markdown notes to a static site. Python, no network at runtime.`

The agent then:
1. asks you a short batch of questions about scope, stack and constraints;
2. proposes a numbered breakdown for you to accept or reshape: `000` is the vision and
   constitution, and features get `001`, `002`, … in dependency order;
3. writes spec 000 and the index `specs/README.md`, and creates a draft skeleton for every
   other spec.

**Adding a feature later.** Run `/feature` with the idea, at any time:
`/feature Users can export a note as PDF.`

The agent reads the spec index and tells you whether the idea is:
- a **new spec**, with a number, a slug and its dependencies; or
- an **amendment** to an existing spec. Amendments past `draft` are your call.

Once you accept, it reserves the numbers with draft skeletons and commits them. Merge that
commit soon, so that another branch can't take the same number. You can then spec, test and
build each reserved spec whenever you like, once the specs it depends on are `done`. If you
abandon an idea, mark it `dropped`: it keeps its number, because numbers are never reused.

Each feature is one spec, `specs/NNN-slug/`, and moves through these phases:

| Phase | Who acts | What happens | Ends when |
|---|---|---|---|
| `draft` | agent, `/spec NNN` | Writes EARS requirements with IDs (`RNNN-MM`) and an exact API contract. A reviewer subagent checks them. | **you approve** the spec |
| `approved` | agent, `/write-tests NNN` | Writes stubs and failing tests, one or more per requirement. An auditor subagent hunts for weak tests. | → `tests-draft` |
| `tests-draft` | you | You read the tests. They are the contract the code must meet. | **you approve** the tests |
| `tests-approved` | you, `/freeze NNN` | The tests are hashed into `tests.lock.json`. From now on, no tool may change them. | → `frozen` |
| `frozen` | agent, `/implement NNN` | Implements task by task until the frozen tests pass. A reviewer subagent looks for test gaming. | → `done` |

Between phases, run `/handoff NNN` and then clear the context (`/clear` in Claude Code). The
next session resumes from `specs/NNN-*/progress.md`, not from chat history.

**If a frozen test turns out to be wrong,** the agent must stop and tell you. Only you can
unfreeze it, by running `agentkit lock unfreeze` in your own terminal. Every unfreeze is logged
in `tests.unfreeze-log.md`.

**Tools without slash commands** (Codex, OpenCode, Pi, …) read the same files. Instead of
`/spec 003`, write "Follow `.agents/skills/spec/SKILL.md` for spec 003."

## Prompting tips

**At kickoff, give the goal and the constraints, not the design.** Say who it is for, what
"done" means, what is out of scope, and any must-use or must-avoid technology. Let the agent
propose the breakdown, then reshape it: merging, splitting or reordering is cheap before any
spec is written and expensive after.

**Capture ideas as soon as you have them.** `/feature <idea>` costs one short session and
nothing is built until you approve it. A reserved draft beats an idea lost in chat history.

**Name the phase and the spec, and nothing more.** The skill already holds the procedure:
`/implement 002` beats a paragraph that explains how to implement. Long prompts cost tokens
and compete with the instructions the agent already has.

**Approve gates in plain words, in the same conversation.** For example: "I approve spec 003",
or "Tests for 002 approved." Agents may set `approved` or `tests-approved` only after you say
so. Say "approved" only when you mean it.

**Put intent into the spec, not the chat.** A requirement you mention only in chat is lost at
the next `/clear`. Say instead: "Add a requirement to 003: the guard denies `git mv` of frozen
files." Then it gets an ID, a test, and a place in the trace.

**Point to files; don't paste them.** "Read R002-07 in `specs/002-test-lock/spec.md`" is
cheaper and more exact than pasting the text. The same goes for logs: ask for a summary
("have the summarizer digest the CI log"), not for the whole thing.

**Ask for the trade-offs, not just the result.** When reviewing a spec, ask: "What did you
decide that plan.md didn't? What are the open questions?" Every spec has sections for exactly
this. Answer the open questions yourself rather than letting the agent guess.

**Read the tests as an adversary before you approve them.** Ask the agent: "Which plausible
wrong implementation would still pass these tests?" Frozen tests are the only oracle during
implementation, so a gap here becomes a bug later.

**Keep sessions to one phase.** Mixing "write the spec and start coding" in one session skips
your gates and fills the context. If the agent proposes moving on, clear the context first.

**When the agent is stuck on a test, don't tell it to "just make it pass".** Ask why it fails
and whether the test or the code is wrong. If the test is wrong, that is your unfreeze
decision, not the agent's.

**Prefer precise requests over broad ones.** "Implement the next open task in `tasks.md`"
works better than "finish 002". "Fix the failing `test_R002_11_*` tests" works better than
"fix the tests".

**Let model routing do its job.** Specs, tests and audits run on the strong model at high
effort; implementation runs on the standard model; summaries run on the fast one. You don't
need to ask for "think hard" in a spec session: the `/spec` skill already sets it.

## Where to look

- [`plan.md`](plan.md): the plan and the decisions behind it
- [`specs/README.md`](specs/README.md): the specs, their dependencies and their order
- [`AGENTS.md`](AGENTS.md): instructions for agents (and humans) working on the kit
- [`docs/adr/`](docs/adr/): decisions, starting with the
  [bootstrap instance](docs/adr/0001-bootstrap-instance.md)
