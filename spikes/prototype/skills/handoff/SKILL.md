---
name: handoff
description: Save the current spec's progress to progress.md so the next session resumes from files. Use before clearing the context or ending a session.
metadata:
  agentkit-tier: fast
  agentkit-effort: low
  agentkit-args: "NNN"
---
# Handoff

1. Add any decisions, dead ends or gotchas from this session above the snapshot in
   `specs/NNN-*/progress.md`. Keep it to five lines or fewer, written for a reader with no
   context.
2. Run `{{python}} .agentkit/bin/agentkit handoff NNN --next "<the next concrete step>"`.
3. Tell the human it is safe to clear the context. The next session starts with `status`.
