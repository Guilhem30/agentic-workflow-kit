# The agentkit workflow

Spec first, then tests, then a freeze, then implementation. The tests the human approved become
the oracle: the implementation iterates until they pass, and they never change without the
human's agreement. This file is the reference. AGENTS.md carries only the rules every session
needs. Read this file when a phase is unclear.

## Phases

`spec.md` carries a `status:` field. Every transition marked HUMAN is a gate.

| Status | Meaning | Who moves it on | Next status |
|---|---|---|---|
| `draft` | spec being written | HUMAN approves | `approved` |
| `approved` | requirements are agreed | agent, after writing tests | `tests-draft` |
| `tests-draft` | tests and API stubs exist and compile, `trace` passes | HUMAN approves | `tests-approved` |
| `tests-approved` | tests are agreed | HUMAN runs `/freeze` | `frozen` |
| `frozen` | tests are locked; implementation in progress | agent, when everything is green and reviewed | `done` |
| `done` | merged | | |

An agent sets `approved` or `tests-approved` only after the human said so in the current
conversation. `frozen` is only set by `agentkit lock freeze --spec NNN`.

## 1. Spec (`/spec`)

- Create the folder with `agentkit new-spec NNN slug`, then fill in `spec.md`.
- **Requirements use EARS** and have stable IDs `RNNN-MM`, for example `R004-07`. Never renumber
  them. Mark a removed one `[removed]` and keep its ID reserved.
- **The public API contract** names the signatures the tests will call and the file each one
  lives in. It tells the implementer where code goes, with no exploration needed.
- Examples and edge cases go in the spec as concrete values. Golden files are named here.
- Open questions are listed explicitly. A spec with open questions cannot be approved.
- The `spec-reviewer` role checks for ambiguity, untestable wording, missing edge cases and
  scope creep before the human sees the spec.

## 2. Tests (`/write-tests`)

- Write API stubs that compile and fail at runtime with the requirement ID, e.g.
  `TODO("R004-07")` or `raise NotImplementedError("R004-07")`.
- Write tests whose names start with the requirement ID they verify. Each test must fail for
  the right reason: the stub, not a compile error or a broken fixture.
- Keep fixtures and golden files small and readable (ASCII grids, short JSON).
- Run `agentkit trace --spec NNN`. Every testable requirement needs at least one test.
- The `test-auditor` role reviews the tests: does each one really check its requirement? Could
  a wrong implementation pass? Are there hidden couplings, sleeps, randomness without seeds,
  or dependencies on test order?
- Set the status to `tests-draft` and hand over to the human.

## 3. Freeze (`/freeze`, human only)

The human runs `/freeze NNN`, or `agentkit lock freeze --spec NNN` themselves. That:

1. adds every not-yet-frozen file matching the profile's frozen globs that belongs to the spec
   (it mentions one of the spec's IDs, or sits under a path segment `NNN` / `NNN-*`) to
   `tests.lock.json`, with a SHA-256 of its LF-normalised content;
2. sets the spec status to `frozen`;
3. is committed as `test(NNN): freeze tests`.

Explicit paths are also accepted: `agentkit lock freeze path/to/FooTest.kt fixtures/foo/`.

## 4. Implement (`/implement`)

- Loop: pick the next task, run the targeted test (`agentkit test <scope>`), change code, repeat.
- Run the full `agentkit test` before each commit (`feat(NNN): ...`).
- If a frozen test seems wrong, **stop and tell the human**. Do not work around it.
- Before marking `done`, the `impl-reviewer` role looks for test gaming: special cases that
  match test inputs, logic that only works for the fixtures, swallowed exceptions, disabled
  checks, and anything that changes test infrastructure.

## Unfreeze protocol

Only the human unfreezes, from their own terminal:

```
python .agentkit/bin/agentkit lock unfreeze path/to/FooTest.kt --reason "R004-07 example was wrong"
```

- The command refuses to run when it detects an agent environment (`AGENTKIT_AGENT`,
  `CLAUDECODE`, ...). It asks for confirmation on the real console, which a piped agent shell
  cannot answer.
- It removes the files from the lock and appends an entry to `tests.unfreeze-log.md`.
- After fixing the test, freeze it again. `agentkit lock audit` (run by pre-commit and CI)
  rejects any lock entry removed or re-hashed without a matching new log entry.

## Enforcement layers

| Layer | Covers | Role |
|---|---|---|
| `tests.lock.json` + `lock verify` | everything | source of truth |
| agent pre-tool guard (`agentkit guard`) | Claude Code, Codex, OpenCode, Pi, DeepSeek Harness (shell only) | early deny |
| agent end-of-turn verify (`agentkit verify`) | the same tools | the agent cannot finish with a broken lock |
| agent permission config | Claude Code, Codex, OpenCode | static denies, build output reads |
| git pre-commit (`agentkit pre-commit`) | anyone | staged lock verify, audit, instruction lint, sync check |
| CI | anyone | the same, plus `trace` and tests; CODEOWNERS on tests and the lock |

An agent with a shell can always try to bypass local layers. The stack makes any bypass a
visible event that fails the build. It does not make bypass impossible.

## Roles and model tiers

Roles live in `.agentkit/workflow/roles/` (project roles in `roles/`). `agentkit sync` turns them
into each tool's subagents. Tiers map to models in `agentkit.toml`.

| Role | Tier | Why |
|---|---|---|
| spec-writer, spec-reviewer | strong | requirements decide everything downstream |
| test-writer, test-auditor | strong | frozen tests are permanent |
| implementer | standard | the frozen tests are the oracle |
| impl-reviewer | strong | catching test gaming needs judgement |
| summarizer | fast | keeps logs and docs out of the main context |

## Sessions

- One spec phase per session. Before ending, run `agentkit handoff NNN --next "..."`, then
  clear the context. The next session starts from `status` and `progress.md`.
- The state lives in files: the spec status, `tasks.md` checkboxes and `progress.md`.
- When compacting, keep: the spec ID, the phase, the failing tests and the next task.

## Exceptions

- **Spikes**: throwaway exploration in `spikes/`, exempt from TDD. Nothing in `spikes/` ships;
  what is learned goes into a spec or an ADR.
- **Bootstrap**: a tool cannot protect its own tests before it exists. The kit's own first tests
  were written with the code, reviewed by the human, then frozen.
