---
id: "012"
title: Claude Code adapter
status: approved
depends: ["004", "010", "011"]
---

# 012 Claude Code adapter

## Context

Claude Code reads CLAUDE.md, not AGENTS.md, unless CLAUDE.md imports it with `@AGENTS.md`.
It reads skills from `.claude/skills/` and subagents from `.claude/agents/`, and it runs hooks
from `.claude/settings.json`.

Facts checked on 2026-10-03 at [hooks](https://code.claude.com/docs/en/hooks),
[sub-agents](https://code.claude.com/docs/en/sub-agents), [skills](https://code.claude.com/docs/en/skills)
and [statusline](https://code.claude.com/docs/en/statusline):
- Hooks have an exec form (`command` + `args`, no shell). `${CLAUDE_PROJECT_DIR}` is substituted
  in args. On Windows, shell-form hooks run in Git Bash, or PowerShell if Git Bash is absent.
- Subagent front matter supports `name`, `description`, `tools`, `model`
  (`opus`/`sonnet`/`haiku`/full ID/`inherit`) and `effort`.
- Skill front matter supports `disable-model-invocation`, `argument-hint`, `model` and `effort`.
  Unknown keys are ignored.
- The status line receives JSON with `model.display_name` and `context_window.used_percentage`
  (which may be null).

## Requirements (EARS)

### Settings (`.claude/settings.json`, managed)
- **R012-01** settings shall set `env.AGENTKIT_AGENT = "1"`.
- **R012-02** settings shall register, all in exec form with
  `command = <[kit] python>` and `args[0] = "${CLAUDE_PROJECT_DIR}/.agentkit/bin/agentkit"`:
  - a `SessionStart` hook running `status --format claude`;
  - a `PreToolUse` hook with matcher `Bash|PowerShell|Edit|Write|MultiEdit|NotebookEdit|Read`
    running `guard --format claude`;
  - a `Stop` hook running `verify --format claude`.
- **R012-03** settings shall deny `Edit` of `**/tests.lock.json`, `**/tests.unfreeze-log.md`,
  `**/.agentkit/**`, `**/agentkit.toml`, the chaos log (`[chaos] log`, default
  `chaos-log.jsonl`) and `<paths.specs>/*/reviews/**` (020), Bash commands matching
  `*lock unfreeze*` and `*chaos clear*`, and `Read` of every profile `build_output_globs`
  pattern.
- **R012-04** settings shall ask before `Edit` of `.claude/settings.json`, `.githooks/**`,
  `.github/workflows/**` and `.gitlab-ci.yml`.
- **R012-05** settings shall configure `statusLine` to run
  `.agentkit/adapters/claude-code/statusline.py` with the configured python. The script prints
  one line: the model display name, `ctx <n>%` (or `ctx ?` when unknown), and the first active
  spec as `NNN:<phase>`. It must never fail: on any error it prints the model name only.
- **R012-06** `.gitignore` shall get a block that ignores `.claude/settings.local.json`.

### CLAUDE.md (block, top)
- **R012-07** The block shall start with the line `@AGENTS.md`, followed by at most 20 lines of
  Claude-only notes:
  - skills are invoked as `/kickoff`, `/feature`, `/spec`, `/write-tests`, `/freeze` (owner
    only), `/implement` and `/handoff`;
  - the review roles are subagents;
  - `/clear` goes between phases;
  - the compaction preferences (keep the spec ID, phase, failing tests and next task).
- **R012-08** The CLAUDE.md block shall not repeat any AGENTS.md content (it passes R009-07).

### Derived files (sync)
- **R012-09** For each skill in `<paths.skills>`, sync shall write `.claude/skills/<name>/` with
  every file copied byte for byte, except SKILL.md, whose front matter is translated:
  - `name`, `description`, `license`, `compatibility` and `allowed-tools` are kept;
  - `metadata.agentkit-user-only: "true"` becomes `disable-model-invocation: true`;
  - `agentkit-args` becomes `argument-hint`;
  - in `kit` mode, `agentkit-tier` becomes `model` and `agentkit-effort` becomes `effort`
    (R001-17); in `tool` mode both are omitted;
  - `metadata` is dropped;
  - a comment saying the file is generated, and from where, is inserted after the front matter.
- **R012-10** For each role, sync shall write `.claude/agents/<name>.md` with `name`,
  `description`, `tools` (`read` → `Read, Grep, Glob`; `edit` → `Edit, Write`;
  `shell` → `Bash, PowerShell`), `model` and `effort` (in `kit` mode only, R001-17),
  then a generated-file comment and the role body.

### Example rule
- **R012-13** The kit shall ship `adapters/claude-code/rules-example.md`. It is a path-scoped rule
  with `paths:` front matter, under 30 lines, showing the format. It is not installed; README
  explains how to copy it into `.claude/rules/`. It shall pass `lint-instructions` when copied.

### Checks
- **R012-11** In a session in a repository installed with this adapter, `/context` shall show
  AGENTS.md content loaded once, not twice. [manual]
- **R012-12** The guard demo shall work in a Claude Code session [manual]:
  - an Edit of a frozen test is denied;
  - a shell edit of it makes the Stop hook block;
  - `git commit` is rejected by pre-commit;
  - the owner's `lock unfreeze` in their own terminal succeeds and is logged.

## Public API contract

The kit files are `adapters/claude-code/settings.json.tmpl`, `adapters/claude-code/CLAUDE.md.tmpl`
and `adapters/claude-code/statusline.py`. The generator functions are
`adapters.claude_kit(cfg, src, ctx)`, `adapters.claude_derived(cfg, ctx)` and
`adapters.claude_skill(cfg, skill_dir)`.

## Additions beyond plan.md

- Chaos mode (020 amendment, ADR 0002, approved by the owner on 2026-10-03): denials for the chaos
  log, the stored reviews and `chaos clear` (R012-03).
- `env.AGENTKIT_AGENT` (used by R002-20).
- Read in the PreToolUse matcher (for R003-11).
- The plan's `.claude/rules/` examples are left to projects, not shipped by the kit.

## Open questions

None. (Decided 2026-10-03: ship the example, R012-13.)
