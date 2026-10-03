# 021 chaos-autopilot: progress

- 2026-10-03: reserved through /feature; spec is a skeleton in phase `draft`. Next: `/spec 021`.
- 2026-10-03: spec, plan and tasks written (21 requirements, 3 open questions); spec-reviewer
  pass running. **Next:** fix its findings, then the owner answers the open questions and approves.
- 2026-10-03: first spec-reviewer pass: needs changes (3 blocking). Fixed: review files in a
  gitignored `.autopilot/` (Claude Code denies edits under `.agentkit/`); `Step` gains `last`,
  `findings`, `reason`, `unfreezes` so the skill tells a fresh reject from other failures and
  resumes from files; stop on anything else.
- 2026-10-03: second pass: previous blockers resolved; fixed its new findings (full suite runs
  before `chaos approve done`; findings survive an escalation and clear; one agent unfreeze per
  spec, then the owner's `lock unfreeze`; exact duplicate-folder and paused output).
  **Next:** owner answers the 3 open questions, approves 021 and its amendments (000, 010, 011,
  012); then apply the amendments and `/write-tests 021` after 020's tests.
- 2026-10-03: owner decided: one agent unfreeze per run, dependencies under chaos run first,
  commit per gate. Added the dependency walk, chain and working spec; third spec-reviewer pass
  (one blocker: walk order) fixed. **Next:** owner approves 021 and its amendments (000, 010,
  011, 012); then apply the amendments; `/write-tests 021` after 020's tests.
