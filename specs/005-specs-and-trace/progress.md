# 005 specs-and-trace: progress

History is in git (`git log -- specs/005-specs-and-trace/`) and the chaos log.

<!-- agentkit:snapshot:begin -->
- 2026-10-03 (UTC), phase `done` (chaos log #10)
- Tests: all 005 tests pass (81). Full suite: only 020's status classes fail (16 errors on the
  006 stub). `trace`: 001, 002, 003, 005, 020 OK. `lock verify` and `chaos audit` OK.
- **Owner questions:** all settled 2026-10-03. Q1: markers in backticks ignored, spec 022
  (R022-02). Q2: scoped reading kept, R005-19 reworded. Q3: forced freeze of a dropped spec
  refused, spec 022 (R022-03).
- Known LOW gaps: titles with `Cf` characters (ZWJ emoji, soft hyphen) are refused; a quoted
  title loses its quotes; a lone `\r` in hand-edited front matter is read two ways; the
  duplicate-number check exists in three places.
- `workflow/templates/{spec,plan,tasks,progress}.md` are minimal; 011 owns their content.

**Next:** none for this spec.
<!-- agentkit:snapshot:end -->
