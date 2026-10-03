# ADR 0001: Hand-written bootstrap instance

- Status: accepted (owner, 2026-10-03)
- Context specs: 000 (Bootstrap, principle 4), 010, 011, 012, 019

## Context

The kit must be built with its own practices (principle 4). Those practices include AGENTS.md
plus a CLAUDE.md that imports it, Agent Skills, review subagents, permission rules and spec
state in files. The tool that writes those files, `agentkit install` (010–012, 019), comes
near the end of the execution order. Waiting for it would mean building 18 specs without the
practices the kit sells.

Two things share these names:
- the kit **product**: templates, roles and skills that ship to every project. 011 and 012
  govern them. They are tested, frozen and implemented like any other code;
- this repo's **instance**: the files we use to build the kit.

## Decision

The repo keeps a hand-written instance now, shaped exactly like what `install --self` will
produce (same paths, same block markers):

| File | Mode once `install` exists (010) |
|---|---|
| `AGENTS.md` (project sections + agentkit block) | block |
| `CLAUDE.md` (`@AGENTS.md` + Claude-only notes) | block |
| `.gitignore` agentkit block | block |
| `agentkit.toml` (`[models] mode = "kit"`) | once |
| `.agents/skills/{spec,write-tests,freeze,implement,handoff}/SKILL.md` | managed |
| `roles/{spec-reviewer,test-auditor,impl-reviewer,summarizer}.md` | project roles (R011-13) |
| `.claude/skills/*`, `.claude/agents/*` | derived |
| `.claude/settings.json` (permissions only, no hooks) | managed |
| `specs/NNN-*/{plan,tasks,progress}.md` | created by `new-spec` |

Rules while the bootstrap lasts:
- **Commands that don't exist yet are replaced by their manual equivalent.** The AGENTS.md
  command table lists them.
- **Derived copies come from the sources.** `scripts/bootstrap_sync.py` regenerates
  `.claude/skills/` and `.claude/agents/` from `.agents/skills/` and `roles/` (R012-09/10,
  `kit` mode). `--check` reports drift.
- **The owner sees every test change.** Until the lock exists, `.claude/settings.json` asks the
  owner before any edit under `tests/`. The owner drops that rule after the bootstrap freeze.
- **001 and 002 are implemented at `tests-approved`.** They are then frozen by the owner with
  the kit's own `lock freeze` (spec 000, Bootstrap; plan.md, Execution order steps 1–2).
- **The early prototype spike is deleted from the tree.** It is in git history at commit
  `af0a18a` if a piece is ever worth consulting. Nothing from it is copied.

## Consequences

- Sessions start from AGENTS.md, the skills and `progress.md`, not from re-reading plan.md.
- At 019, `install --self --models kit --force` overwrites the instance. These files are not in
  the manifest, so without `--force` R010-12 would only write `.agentkit-new` files. Diffing the
  generated files against this hand-written set reviews the 011/012 templates against real use.
  After that, `scripts/bootstrap_sync.py` and this ADR's rules are removed, and `roles/` is kept
  only where it deliberately overrides a kit role.
- Until 003/004/018 exist, nothing enforces the hard rules except Claude permissions and owner
  review. That is the accepted risk of the bootstrap.
