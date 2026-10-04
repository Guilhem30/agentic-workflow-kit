---
name: handoff
description: Save the current spec's progress to its progress.md so the next session resumes from files. Use before clearing the context or ending a session.
metadata:
  agentkit-tier: fast
  agentkit-effort: low
  agentkit-args: "NNN"
---
# Handoff

Run `{{python}} .agentkit/bin/agentkit handoff NNN --next "<one concrete step>" [--note "<gotcha>"]`. It
writes the snapshot block (phase, tasks, last `agentkit test` summary, branch, Next). Then:

1. Above the snapshot, keep only what the next session needs: open owner questions and live
   gotchas, at most ten lines, written for a reader with no context. Drop settled history
   (git and the chaos log keep it).
2. Never edit the snapshot block by hand; run the command again instead.
3. Commit `docs(NNN): handoff` if anything else in the session was committed. Then tell the
   owner it is safe to clear the context.
