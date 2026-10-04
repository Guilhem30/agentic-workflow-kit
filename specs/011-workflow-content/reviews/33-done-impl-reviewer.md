Review of spec 011 (workflow content). The 36 frozen tests in test_011_templates, test_011_roles and test_011_skills pass. I did not get a result from the full suite because it exceeded the 120 s tool timeout. No test file or `tests/content_fixtures.py` was touched. The `tests.lock.json`, `chaos-log.jsonl` and spec status/tasks changes in the working tree are the owner's freeze record and task ticks.

## Blocking
None.

## Test gaming
None found.
- `roles(cfg)` at `agentkit/roles.py:13-16` is a plain two-folder merge: kit `workflow/roles/*.md`, then `<root>/<paths.roles>/*.md` overriding by file stem. It has no fixture-specific branches.
- The 36-line AGENTS.md block is genuinely under the 45-line cap, not trimmed to fit a test.
- The skill and role contents match the spec text, not just the checks the tests make.

## Should fix (docs vs specs 005/020/021)
1. `workflow/WORKFLOW.md:107-116` (chaos limits) covers only "the kit cannot prove a verdict came from an independent reviewer". R020-35 requires "the limits listed in the Context" of 020. That Context also lists two more limits:
   - an agent can skip submitting a rejection;
   - an agent can edit `status:` in `spec.md` by hand.
2. `workflow/WORKFLOW.md:90-91` (enabling) omits that the owner can scope chaos mode to chosen specs with `[chaos] specs`. R021-03 hint 8 and the autopilot "not under chaos mode" stop depend on this. It also never names `max_rejections` (default 2), so "repeated rejections" has no number.
3. `workflow/WORKFLOW.md:16,18-19` says `done` is a non-gate phase set by `agentkit spec-status`. Where chaos applies, R020-31 refuses `spec-status ... done` for agents and requires `chaos approve NNN done`. `skills/implement/SKILL.md:35` ("set `status: done`") has the same gap. The freeze skill already handles chaos, so implement should get one clause too. It is self-correcting, because the refusal names the right command, and non-chaos behaviour is correct.
4. R011-17 says "Each skill" names its review role and gives the no-subagent fallback.
   - `kickoff`, `spec`, `write-tests` and `implement` comply.
   - `autopilot` complies (both writer and reviewer roles, plus the "No subagents" paragraph).
   - `feature` (`skills/feature/SKILL.md`), `freeze` and `handoff` delegate no review, so they name no role.
   - Either the owner reads R011-17 as applying to skills that review, or those three get a one-line note. I would accept it as is.

## Autopilot skill vs R021-08..21
It conforms on every point I checked. Minor omissions:
- `skills/autopilot/SKILL.md:21-26` omits the R021-11 line that a spec-writer lists open questions without guessing.
- It omits R021-12's "ask once when `then` exits 2 on an invalid verdict" detail; line 31 only says "if the verdict line is invalid".
- The stop-and-report paragraph (`:49-53`) does not say the report quotes the command output or the `blocked:` lines (R021-16).
- Step 3 (`:32-34`) does not say to re-run `agentkit autopilot NNN` to read `last` before deciding between "new reject" and "stop" (R021-13).

All of these are nits; none changes behaviour materially.

## Constitution and robustness (low)
- `agentkit/roles.py:10` globs `*.md` and keys on `p.stem`.
  - A `README.md` in the roles folder would become a role named "README".
  - On a case-insensitive filesystem a project file `Impl-Reviewer.md` would not override the kit's `impl-reviewer.md`. It would add a second entry that collides when synced to the same target path. Normalising names, or ignoring names that are not valid role names, would harden it. The spec defines the name only as "file name without `.md`", so this is not a violation.
- Cosmetic: replacing the launcher placeholder left over-long wrapped lines in `skills/freeze/SKILL.md:18`, `skills/handoff/SKILL.md:11` and `skills/write-tests/SKILL.md:24`. They are about 105-117 characters against the 100-character wrap used elsewhere.

## Other checks (all OK)
- R011-02: the 8 sections match plan Part B. The budget table matches 006 (10 lines, 200 characters each), 007 (60 lines) and 009 (all seven defaults).
- R011-03/05/06/07: all nine templates exist. The agentkit block runs from the begin marker to the end marker in 37 lines (cap 45). It has the session-start text, the five hard rules including chaos log, `reviews/` and `chaos clear`, the `{{python}} .agentkit/bin/agentkit` command table, and the token rules.
- `workflow/templates/agentkit.toml.tmpl` uses only known keys. The `[chaos]` table (`enabled`, `log`) matches R020-01 and 010.
- R011-09..12: the seven roles have the right tiers (implementer and impl-reviewer are standard, per the owner's 2026-10-03 decision). The three reviewers have no `edit` tool. Verdict lines match R020-12, including `verdict: needs owner` and the unfreeze verdicts for the test-auditor and impl-reviewer.
- R011-14..16, 19..21: metadata, tiers and `agentkit-user-only` (freeze and autopilot) are correct. The numbering rules (default branch or local, including dropped, reserve with an immediate commit) are in `feature`. `spec` states it assigns no numbers. `kickoff` requires an accepted breakdown before any spec is written, uses batches of at most eight questions, and approves nothing without the owner.
- R011-01 and R021-21/25: WORKFLOW.md covers every required topic, and `/autopilot` is described accurately (who starts it, dependencies first, stop conditions, resume via `agentkit autopilot NNN`).

## Info
`/roles/` at the repo root has `impl-reviewer`, `spec-reviewer` and `test-auditor` without the `verdict: needs owner` and unfreeze-verdict lines that `workflow/roles/` now carries. It also lacks the other four roles. This is the bootstrap copy that `.claude/agents` is generated from. Reconciling it belongs to the self-hosting and sync specs, not 011. Files under `roles/` are in the chaos `escalate_globs`, so I did not suggest touching them here.

verdict: approve
