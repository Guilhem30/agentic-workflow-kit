# agentic-workflow-kit

A language-neutral, agent-neutral kit for agentic programming. It packages one process:

**spec → tests → owner freeze → implement until the frozen tests pass.**

Tests never change without the owner's agreement, and token usage stays low by default. The kit
targets Claude Code, Codex CLI, OpenCode, DeepSeek Harness and Pi, plus a tool-neutral baseline
(AGENTS.md, git hooks, CI) for any other agent. It is Python 3.11+ with the standard library only.

## Status

Under construction, built with its own process. `python3 -m agentkit status` always shows the
live state; on 2026-10-04 it was:

| State | Specs |
|---|---|
| `done` | 001–009 (config, lock, guard, hook dialects, trace, status/handoff, test runner, codemap, lint-instructions), 011 (workflow content) |
| `frozen`, being implemented | 010 (install, update, sync), 020 (chaos mode; its code is in, it closes now that 011 is done) |
| `tests-draft`, waiting for owner review | 000 (vision and constitution) |
| `approved`, tests not written | 012–016 (adapters), 017 (profiles), 018 (git hooks and CI), 019 (self-hosting and docs), 021 (`/autopilot`) |
| `draft` | 022 (owner decisions), 023 (`/fix` path) |

There is **no install command yet**: `install`, `update`, `sync` (010) and `autopilot` (021)
are still stubs. Until they land, this repository uses a hand-written bootstrap instance
([ADR 0001](docs/adr/0001-bootstrap-instance.md)): `scripts/bootstrap_sync.py` copies
`.agents/skills/` and `roles/` into `.claude/`, and `scripts/session_start.py` prints
`agentkit status` at session start. Spec 019 adds the two-command install and the adapter
capability matrix.

## Commands

Run them with `python3 -m agentkit <command>` (`python` on Windows). These work today:

| Command | What it does |
|---|---|
| `status` | Short session summary: profile, lock state, chaos state, active specs and the next step for each |
| `test [scope]` | Runs the tests and prints a compact summary; the full log goes to `.agentkit/state/last-test.log` |
| `lock freeze --spec NNN` / `verify` / `status` / `audit` / `restore` | The test lock in `tests.lock.json`. `lock unfreeze` is for the owner only, in their own terminal |
| `new-spec`, `spec-status NNN <phase>` | Creates a draft spec from the templates; sets a non-gate phase |
| `trace --spec NNN` | Requirement coverage: which `RNNN-MM` IDs have tests |
| `handoff NNN --next "…"` | Writes the resume snapshot into the spec's `progress.md` |
| `codemap` | Writes `docs/CODEMAP.md`, the map of where code lives |
| `lint-instructions` | Checks the token budgets of AGENTS.md, skills and progress files |
| `models` | Shows which model and effort each tier routes to |
| `guard`, `verify` | Hook entry points: judge one tool call before it runs; verify the lock at end of turn |
| `chaos approve` / `log` / `audit` / `clear` | Chaos mode (below). `clear` is owner-only |
| `version` | Prints the version |

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
| `tests-approved` | you, `/freeze NNN` | `agentkit lock freeze` hashes the tests into `tests.lock.json`. From now on, no tool may change them. | → `frozen` |
| `frozen` | agent, `/implement NNN` | Implements task by task until the frozen tests pass. A reviewer subagent looks for test gaming. | green and reviewed → `done` |

A spec that is abandoned is set to `dropped`. `agentkit status` prints the next step for every
active spec, so you rarely need to remember where you were.

Between phases, run `/handoff NNN` and then clear the context (`/clear` in Claude Code). The
skill runs `agentkit handoff`, which writes a snapshot (phase, tasks, last test summary, next
step) into `specs/NNN-*/progress.md`. The next session resumes from that file, not from chat
history.

**If a frozen test turns out to be wrong,** the agent must stop and tell you. Only you can
unfreeze it, by running `agentkit lock unfreeze` in your own terminal. Every unfreeze is logged
in `tests.unfreeze-log.md`.

**Tools without slash commands** (Codex, OpenCode, Pi, …) read the same files. Instead of
`/spec 003`, write "Follow `.agents/skills/spec/SKILL.md` for spec 003."

## Chaos mode (opt-in)

By default you own every gate. Chaos mode ([ADR 0002](docs/adr/0002-chaos-mode.md), spec 020)
lets agents pass gates themselves, and pulls you in only when something goes wrong. It is on in
this repository.

- **Only you enable it**, with `enabled = true` under `[chaos]` in `agentkit.toml`, a file agents
  cannot edit. `[chaos] specs` limits it to chosen specs. It never covers spec 000.
- **Agents pass a gate** with `agentkit chaos approve NNN <gate>` and a review whose last line is
  the matching reviewer's passing verdict (spec-reviewer, test-auditor or impl-reviewer). An
  agent unfreeze needs both the test-auditor and the impl-reviewer, and sends the spec back to
  `tests-draft`.
- **Critical problems escalate and pause chaos mode:** repeated rejections, a failing
  `lock verify` or `lock audit`, a change to a protected file (spec 000, AGENTS.md, CLAUDE.md,
  ADRs, `agentkit.toml`, role files), a rewritten base commit, or `verdict: needs owner`.
- **Everything is logged** in an append-only chaos log with a hashed copy of each review.
  `agentkit chaos log --open` lists open escalations; only you clear them, with
  `agentkit chaos clear`.
- **The limit:** the kit cannot prove a verdict came from an independent reviewer. Chaos mode
  trades prevention for visibility and mechanical checks. Leave it off if you need prevention.

**`/autopilot NNN`** (spec 021, not implemented yet) will chain the phases in chaos mode: writer
subagent, reviewer subagent, `chaos approve`, commit, for NNN and every unfinished dependency,
stopping on any escalation.

**Coming next:** `/fix` (spec 023, draft) routes a problem found after a spec is `done`: a fix
spec with new regression tests through the same gates, an amendment through `/feature`, a wrong
frozen test to you, or a direct `fix:` commit for wording only.

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
`agentkit models` shows the current routing.

**Ask for the short version of the state.** "Run `agentkit status`" beats "read the README and
progress.md": it prints the lock, chaos state and the next step per spec in about ten lines.
Likewise, `agentkit test` prints only the summary and failures.

## Where to look

The kit **product** (what ships to other projects) and this repo's **instance** (what we use to
build it) live side by side:

| Path | What |
|---|---|
| [`workflow/`](workflow/) | Product: [`WORKFLOW.md`](workflow/WORKFLOW.md) (the process in full), [`TOKEN-EFFICIENCY.md`](workflow/TOKEN-EFFICIENCY.md), spec and config templates, role definitions |
| [`skills/`](skills/) | Product: the 8 Agent Skills (`kickoff`, `feature`, `spec`, `write-tests`, `freeze`, `implement`, `handoff`, `autopilot`) |
| [`profiles/`](profiles/) | Product: language presets (only `generic` so far; 017 adds the rest) |
| [`agentkit/`](agentkit/) | Product: the CLI. [`docs/CODEMAP.md`](docs/CODEMAP.md) maps it |
| `.agents/skills/`, [`roles/`](roles/) | Instance: the skills and roles this repo runs on, copied into `.claude/` by `scripts/bootstrap_sync.py` |
| [`plan.md`](plan.md) | The plan and the decisions behind it |
| [`specs/README.md`](specs/README.md) | The specs, their dependencies and their order |
| [`AGENTS.md`](AGENTS.md) | Instructions for agents (and humans) working on the kit |
| [`docs/priorities.md`](docs/priorities.md) | The remaining work, ranked by token savings |
| [`docs/adr/`](docs/adr/) | Decisions: [0001 bootstrap instance](docs/adr/0001-bootstrap-instance.md), [0002 chaos mode](docs/adr/0002-chaos-mode.md) |
