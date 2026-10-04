# Test audit: spec 009 (lint-instructions), passes 1-2

Reviewer: test-auditor subagent (roles/test-auditor.md), recorded by the main session because
the role is read-only. All 28 tests fail on NotImplementedError; no import or fixture errors.

Pass 1 findings (12) and resolutions:
- MED claude/rule/skill budgets not exercised when configured. Fixed: all four, at and over.
- MED front matter shared only 2 lines. Fixed: 4 lines.
- MED "consecutive" untested. Fixed: test_R009_07_must_be_consecutive.
- MED duplicate_min_lines=2 accepted any error. Fixed: one error naming both files.
- MED no check that under-budget gives no token warning. Fixed: test_R009_11_at_budget_no_warning.
- LOW message wording (@AGENTS.md, SKILL.md) over-specified. Fixed: CLAUDE.md / file or dir name.
- LOW unclosed fence. Fixed: closed pair.
- LOW 12-char threshold boundary. Fixed: test_R009_08_twelve_character_threshold.
- LOW front matter without paths:. Fixed: warns.
- LOW bytes vs characters. Fixed: "éééé" gives 1.
- LOW generated copy duplicates. Fixed: test_R009_07_generated_copy_not_a_duplicate.

Pass 2: all 12 fixed, nothing broken. Note: front matter counts toward line budgets (the spec's
"a file with more lines than its budget").

verdict: ready to freeze
