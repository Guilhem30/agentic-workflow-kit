<!-- agentkit:begin (managed by agentkit; edit outside this block) -->
@AGENTS.md

## Claude Code

- New project: `/kickoff <idea>`. New idea later: `/feature <idea>`. Then one skill per phase:
  `/spec NNN`, `/write-tests NNN`, `/implement NNN`, `/handoff NNN`.
  `/freeze NNN` is for the owner only; never invoke it on your own.
- Reviews run as subagents in `.claude/agents/`: `spec-reviewer`, `test-auditor`,
  `impl-reviewer`. Send log digging and summaries to `summarizer`.
- Run `/handoff` and then `/clear` between phases. The next session resumes from `progress.md`.
- When compacting, keep: the spec ID, its phase, the failing tests and the next task.
- `.claude/skills/` and `.claude/agents/` are generated from `.agents/skills/` and `roles/`.
  Edit the source, then run `python3 scripts/bootstrap_sync.py` and commit both.
<!-- agentkit:end -->
