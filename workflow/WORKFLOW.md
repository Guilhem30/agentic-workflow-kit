# Workflow

One process for every feature: **spec → tests → owner freeze → implement until the frozen tests
pass**. It works with any agent, any model and any language. The human owns the gates.

## Phases and gates

`status:` in `spec.md` records the phase. Each gate is a decision, not a step.

| Phase | Work | Gate to leave it |
|---|---|---|
| `draft` | Write the spec (EARS requirements, API contract), review it | owner sets `approved` |
| `approved` | Write stubs and failing tests, audit them | owner sets `tests-approved` |
| `tests-draft` | Fix audit findings | owner sets `tests-approved` |
| `tests-approved` | Nothing to write | owner runs `lock freeze`, giving `frozen` |
| `frozen` | Implement until the tests pass, review | `done` once green and reviewed |

`dropped` retires a spec; its number is never reused. A change to a non-gate phase
(`tests-draft`, `done`) is `agentkit spec-status NNN <phase>`; where chaos mode applies, `done`
goes through `agentkit chaos approve NNN done` instead.

## Steps of each phase

1. **Spec** (`/spec NNN`): requirements with stable IDs `RNNN-MM`, one behaviour each, plus the
   Public API contract. The spec-reviewer role checks it.
2. **Tests** (`/write-tests NNN`): stubs raise `NotImplementedError("<REQ-ID>")`; every test name
   starts with its requirement ID; `agentkit trace` checks coverage; the test-auditor asks
   whether a plausible wrong implementation could pass.
3. **Freeze** (`/freeze NNN`): `agentkit lock freeze --spec NNN` stores a SHA-256 per file in the
   lock. Commit `test(NNN): freeze tests`.
4. **Implement** (`/implement NNN`): targeted tests, then the full suite; the impl-reviewer looks
   for test gaming. Commit `feat(NNN)`.

New projects start with `/kickoff` (writes spec 000, the index and one draft per feature); new
ideas later with `/feature`. Only those two assign spec numbers.

## Freeze and unfreeze

Frozen files never change: no edit, move, delete or regeneration. If a frozen test looks wrong,
stop and tell the owner. Only the owner runs `agentkit lock unfreeze <path> --reason …`; the
lock then drops the file and the unfreeze log records who, when and why. The spec goes back to
`tests-draft`, and the tests are audited and frozen again.

## Enforcement layers and their limits

| Layer | What it does |
|---|---|
| Lock file and `lock verify` | The source of truth for frozen files |
| Agent guard and end-of-turn verify | Deny writes to frozen paths and the lock; re-check at turn end |
| Agent permission config | Deny direct edits to the lock and logs; ask before guard, hook and CI edits |
| git `pre-commit` | Lock verify and instruction lint, for any agent or human |
| CI | Lock verify, `sync --check`, tests |

No local layer can stop an agent that deliberately bypasses it with shell access. Stacking them
makes a bypass a visible event that blocks the build. Per-agent hooks are early warnings, never
the guarantee.

## Roles and tiers

| Role | Tier | Does |
|---|---|---|
| spec-writer | strong | Writes the spec |
| spec-reviewer | strong | Reviews it (read-only) |
| test-writer | strong | Writes stubs and tests |
| test-auditor | strong | Audits tests for gaps and weak assertions (read-only) |
| implementer | standard | Implements against the frozen tests |
| impl-reviewer | standard | Looks for test gaming and spec drift (read-only) |
| summarizer | fast | Condenses logs and wide searches |

Tiers map to models in `agentkit.toml` (`[models]`). Where a tool has no subagents, a skill
applies the role's checklist inline. Project roles in the configured roles folder override kit
roles of the same name.

## Session handoff

One phase of one spec per session. Before clearing the context, run `/handoff NNN`; it writes
the resume point into `progress.md`. The next session starts from `agentkit status` and that
file. See `TOKEN-EFFICIENCY.md`.

## Exceptions

- **Spike.** Throwaway exploration may run without a spec. Its code is deleted or specified
  before it ships, and it is never merged as it stands.
- **Bootstrap.** A project that builds the kit's own tools may implement the first specs before
  `lock` exists, using hand-written equivalents. An ADR records the exception and when it ends.

## Chaos mode

An opt-in exception to "the human owns the gates" (ADR 0002, spec 020).

- **Enabling.** Only the owner enables it, with `enabled = true` under `[chaos]` in
  `agentkit.toml`, a file agents cannot write. `[chaos] specs` limits it to chosen specs. It is
  off by default and never covers spec 000.
- **What agents may then do.** Pass a gate through `agentkit chaos approve NNN <gate>` with a
  review whose last line is the matching reviewer's passing verdict, and unfreeze a test
  through `chaos unfreeze` with both the test-auditor's and the impl-reviewer's `unfreeze
  justified` verdicts. Any reviewer may end with `verdict: needs owner`, which escalates.
- **Critical checks.** Repeated rejections (`max_rejections` in a row, default 2), a failing `lock verify` or `lock audit`, a change to
  a protected file (spec 000, AGENTS.md, CLAUDE.md, ADRs, `agentkit.toml`, role files), a
  rewritten base commit, or `verdict: needs owner` each raise an escalation and pause chaos mode.
- **The log.** Every pass, rejection, unfreeze and escalation goes into an append-only chaos
  log, with a hashed copy of each review in the spec's `reviews/` folder.
- **Clearing.** Only the owner clears an escalation (`agentkit chaos clear`), from a terminal an
  agent cannot use. `agentkit chaos log --open` lists what is open.
- **Limits.** The kit cannot prove a verdict came from an independent reviewer. The guarantee
  becomes visibility and mechanical checks, not prevention: an agent could skip submitting a
  rejection, or edit `status:` in `spec.md` by hand. Owners who need prevention leave chaos
  mode off.

### `/autopilot`

The owner starts `/autopilot NNN`. It first works each dependency of NNN that is not `done`,
then NNN. At each phase it runs the writer role as a subagent, then the reviewer role, saves
the review under `.autopilot/`, and passes the gate with `chaos approve`. It commits after each
gate. `freeze` is a single `chaos approve NNN frozen`. It stops, and reports what is blocked
and why, when an escalation is raised, a command fails other than by a rejection, a run repeats
itself, or a second agent unfreeze would be needed. It never clears escalations. To resume,
clear the cause (or fix it) and run `/autopilot NNN` again, in a new session if you like: the
next step comes from `agentkit autopilot NNN`, which reads the spec phases and the chaos log.
