# Implementation review: spec 009 (lint-instructions), passes 1-2

Reviewer: impl-reviewer subagent (roles/impl-reviewer.md, standard tier), recorded by the main
session because the role is read-only. 28 frozen tests pass; no test gaming. On the repo itself
`agentkit lint-instructions` reports OK (~1601 tokens), with no false positives.

Pass 1 findings and resolutions:
- MED a BOM hid the front matter (false name/description errors, lost paths:). Fixed: utf-8-sig.
- MED YAML block scalars read as `>`/`|`; quotes stripped one-sided. Fixed: _parse_meta resolves
  `>`, `>-`, `|` from indented lines; quotes removed only as a matching pair.
- LOW non-int budgets silently ignored. Fixed: ConfigError, exit 2.
- LOW public DEFAULT_BUDGETS, redundant flush. Fixed.
- Kept: a name/directory mismatch hides the pattern error (one error is enough under R009-05).
Checked fine: CRLF, nested rules, block-list paths:, front matter excluded from duplicates,
three files give three pair errors, same-file repeats ignored, fence lines skipped.

Pass 2: all fixes verified; nothing broken.

verdict: approve
