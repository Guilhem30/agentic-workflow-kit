# Implementation review: spec 006 (status and handoff), passes 1-2

Reviewer: impl-reviewer subagent (roles/impl-reviewer.md, standard tier), recorded by the main
session because the role is read-only. 64 frozen tests pass (006 and 020 status). No test gaming.

Pass 1 findings and resolutions:
- MED CRLF progress.md rewritten as LF. Fixed: bytes in and out, block in the file's endings.
- MED `\s*` after **Next:** crossed lines. Fixed: [ \t]* and a non-space start.
- MED first Next line won over the snapshot's. Fixed: the snapshot block's, else the last.
- LOW unsanitised error text in line 1. Fixed: whitespace collapsed (lock and chaos).
- LOW orphan markers duplicated. Fixed: dropped before appending.
- LOW multi-line note/--next. Fixed: collapsed to one line.
- LOW BEGIN/END public beyond the contract. Fixed: private.
- Kept: handoff reuses status's private action helpers (consistent Next text); `*` bullets.

Checked fine: a missing dependency blocks; a lone blocked spec gives `next: blocked by X`;
the 9-spec overflow; a malformed chaos table keeps owner actions and shows BROKEN with exit 0.

Pass 2: all fixes verified.

verdict: approve
