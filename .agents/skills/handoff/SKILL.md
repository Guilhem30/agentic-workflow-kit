---
name: handoff
description: Save the current spec's progress to its progress.md so the next session resumes from files. Use before clearing the context or ending a session.
metadata:
  agentkit-tier: fast
  agentkit-effort: low
  agentkit-args: "NNN"
---
# Handoff

Until `agentkit handoff` (spec 006) exists, update `specs/NNN-*/progress.md` by hand:

1. Above the snapshot, keep only what the next session needs: open owner questions and live
   gotchas, at most ten lines, written for a reader with no context. Drop settled history
   (git and the chaos log keep it).
2. Replace the block between `<!-- agentkit:snapshot:begin -->` and
   `<!-- agentkit:snapshot:end -->` with:
   - the UTC date and the phase;
   - `Tasks: <done>/<total> done` and the first open task from `tasks.md`;
   - the last test summary line (`Ran N tests …`, `FAILED (…)`);
   - the branch and the number of uncommitted files;
   - a last line `**Next:** <one concrete step>`.
3. Commit `docs(NNN): handoff` if anything else in the session was committed. Then tell the
   owner it is safe to clear the context.
