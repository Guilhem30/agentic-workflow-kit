# 021 chaos-autopilot: progress

- 2026-10-03: reserved through /feature; spec is a skeleton in phase `draft`. Next: `/spec 021`.
- 2026-10-03: spec, plan and tasks written (21 requirements, 3 open questions); spec-reviewer
  pass running. **Next:** fix its findings, then the owner answers the open questions and approves.
- 2026-10-03: first spec-reviewer pass: needs changes (3 blocking). Fixed: review files in a
  gitignored `.autopilot/` (Claude Code denies edits under `.agentkit/`); `Step` gains `last`,
  `findings`, `reason`, `unfreezes` so the skill tells a fresh reject from other failures and
  resumes from files; stop on anything else. Second pass running.
