# agentic-workflow-kit

<!-- Project sections live outside the agentkit block. Budget: 150 lines for the whole file
     (`lint-instructions`, spec 009). Link to docs instead of pasting them here. -->

## Product

A language-neutral, agent-neutral kit that packages one process:
spec → tests → owner freeze → implement until the frozen tests pass. It ships a stdlib-only
Python CLI (`agentkit`), process docs, Agent Skills and adapters for Claude Code, Codex CLI,
OpenCode, DeepSeek Harness and Pi. The kit is built with its own process and installs itself.

## Layout

| Path | What |
|---|---|
| `plan.md` | The working plan. Specs cite its sections. Read a section only when a spec points to it. |
| `specs/NNN-slug/` | `spec.md` (EARS requirements, API contract), `plan.md`, `tasks.md`, `progress.md` |
| `specs/README.md` | Spec index, dependencies and order |
| `agentkit/` | The CLI package. Modules follow each spec's *Public API contract* |
| `tests/` | `unittest` suite. `tests/support.py` holds shared fixtures |
| `docs/adr/` | Decisions. ADR 0001 explains why these instruction files are hand-written for now |
| `.agents/skills/`, `roles/` | Neutral skill and role sources. `scripts/bootstrap_sync.py` copies them into `.claude/` |

## Conventions

- Python 3.11+, standard library only, no network (R000-01, R000-03). Windows, macOS and Linux.
- Text files are UTF-8 with LF endings (R000-07). Exit codes: 0 ok, 1 check failed, 2 usage or
  config error (R000-08).
- Code goes exactly where the spec's API contract says. Nothing outside the contract is public.
- A stub body is `raise NotImplementedError("<REQ-ID>")`.
- Test names start with requirement IDs (`test_R002_07_...`). IDs of other specs are built with
  `support.rid()` so that a file belongs to exactly one spec.

## Bootstrap state

`agentkit` itself is not implemented yet, so its commands do not run. The block below uses their
manual equivalents. Claude Code hooks, git hooks, CI and `tests.lock.json` arrive with specs
002–004 and 018. Until then, `.claude/settings.json` asks the owner before any edit under
`tests/`. See `docs/adr/0001-bootstrap-instance.md`.

<!-- agentkit:begin (managed by agentkit; edit outside this block) -->
## Workflow (agentkit)

Every feature goes spec → tests → freeze → implement. Phases (`status:` in `spec.md`):
`draft` → `approved` → `tests-draft` → `tests-approved` → `frozen` → `done`.

**Session start:** find the active spec in `specs/README.md` and read its `progress.md`, which
has the resume point. Work on one phase of one spec per session.

### Hard rules
1. Frozen files never change: no edit, move, delete or regeneration, by any tool or shell
   command. If a frozen test looks wrong, stop and tell the owner. Only the owner unfreezes.
2. Never edit `tests.lock.json`, `tests.unfreeze-log.md`, `agentkit.toml` or `.agentkit/`. Never
   commit with `--no-verify`, change `core.hooksPath`, or run `lock unfreeze`.
3. The owner owns the gates. Set `approved` or `tests-approved` only when the owner said so in
   this conversation. `frozen` is set only by `lock freeze`.
4. Make tests pass honestly: no special-casing of test inputs, no skipped or weakened checks.
5. Every test name starts with the requirement ID it covers.

### Commands (bootstrap equivalents)
| Need | Command |
|---|---|
| Full suite | `python3 -m unittest discover -s tests` (`python` on Windows) |
| One module or test | `python3 -m unittest tests.test_002_freeze` |
| Change a non-gate phase | edit `status:` in `spec.md` (`tests-draft`, `done`) |
| Requirement coverage | `grep -rhoE 'R002[-_][0-9]{2}' tests \| sort -u` against the spec |

### Token discipline
- Read the spec's API contract and `tasks.md` first. Open only the files they point to.
- Run targeted tests while working. Run the full suite before each commit.
- Hand verbose work (wide searches, log digging) to a fast-tier subagent. Do trivial steps yourself.
- Commits: `spec(NNN): …`, `test(NNN): …`, `feat(NNN): …`, `fix: …`, `docs: …`, `chore: …`.
<!-- agentkit:end -->
