# 011 workflow-content: plan

## Approach

Content first, one small module. Move the bootstrap sources into the kit layout: `skills/` (from
`.agents/skills/`, commands rewritten to `{{python}} .agentkit/bin/agentkit`, plus `autopilot`)
and `workflow/roles/` (from `roles/`, plus spec-writer, test-writer and implementer). Write the
missing templates and the AGENTS.md template from the kit's own AGENTS.md workflow block, with
configurable paths as install keys. `agentkit/roles.py` merges kit and project roles.

## Files

- `workflow/WORKFLOW.md`, `workflow/TOKEN-EFFICIENCY.md` (manual: R011-01, R011-02)
- `workflow/templates/`: `AGENTS.md.tmpl`, `agentkit.toml.tmpl`, `adr.md`, `specs-README.md`,
  `unfreeze-log.md` (spec-folder templates exist)
- `workflow/roles/*.md`, `skills/*/SKILL.md`, `agentkit/roles.py`

## Test strategy

Tests read the kit files directly (`tests/content_fixtures.py`: a front-matter reader for the
YAML subset used, and `render()` with sample install contexts). One context uses non-default
values so that hard-coded paths fail. R011-08 lints a fixture repo holding the rendered
AGENTS.md, a `@AGENTS.md` CLAUDE.md and the rendered kit skills. `roles(cfg)` is tested on
fixture repos against the real kit roles.

## Notes

- The bootstrap copies (`.agents/skills/`, `roles/`) keep working until 019; the kit's own
  `paths.roles = "roles"` overrides kit roles through `roles(cfg)`.
- Expect an escalation: AGENTS.md and roles are protected for agents in chaos mode.
