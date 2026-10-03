# 020 chaos-mode: tasks

- [x] ADR 0002 accepted
- [x] Apply the approved amendments to 000, 001, 002, 003, 005, 006, 010, 011, 012, 014, 018
- [x] `chaos.py`: `Settings`, `settings()` with validation (R020-01 to R020-06)
- [x] Log: `read_log`, append, `open_escalations`, record fields (R020-07 to R020-11)
- [x] `REVIEWS`, `parse_verdict`, review copy and hash (R020-12 to R020-14)
- [x] Base commit and changed paths; critical checks (R020-19)
- [x] `approve`: gates, phases, trace, pause, needs-owner, reject count, freeze (R020-15 to R020-22, R020-43)
- [x] Private unfreeze-log writer in `lock.py`; `chaos.unfreeze` (R020-23 to R020-25)
- [x] `clear`, `log`, `audit` (R020-26 to R020-28)
- [x] CLI: `chaos` subcommands and exit codes; agent refusal in `spec-status` and `lock freeze` (R020-31)
- [ ] Guard rules (R020-29, R020-30, R020-42): with 003 (`guard.evaluate`)
- [ ] Status line and next actions (R020-32 to R020-34): `chaos.status_suffix` done; the rest with 006 (`status.status_lines`), which must cut line 1, suffix included, to 200 characters
- [ ] WORKFLOW.md chaos section (R020-35): with 011
- [ ] Full suite green; impl-reviewer
