# 021 chaos-autopilot: plan

## Approach

A thin, read-only core and an instruction file. `agentkit/autopilot.py` maps the spec's phase
to a `Step` (R021-01, R021-02) after the refusal checks of R021-03, reusing `chaos.settings`,
`chaos.read_log`, `chaos.open_escalations`, `chaos.format_log` (020), `specs.find_spec`, `specs.list_specs` (005)
and `lock.verify` (002). The CLI prints it (R021-05 to R021-07). The skill
`skills/autopilot/SKILL.md` loops on that command and delegates each phase to writer and
reviewer subagents (R021-10 to R021-20). WORKFLOW.md gains a paragraph (R021-21).

## Files

- `agentkit/autopilot.py` (new)
- `agentkit/cli.py`: the `autopilot` subcommand
- `skills/autopilot/SKILL.md` (new, kit content, 011)
- `workflow/WORKFLOW.md`: the chaos-mode section
- Bootstrap instance: `.agents/skills/autopilot/SKILL.md`, then `scripts/bootstrap_sync.py`

## Test strategy

- `tests/test_021_autopilot.py`: temporary git repositories built with `tests/support.py`; one
  spec per phase, `[chaos]` variants (absent, off, malformed, listing other specs, paused through
  a hand-written log, rejects, unfreezes and clears for R021-22 to R021-24), an unreadable and a
  violated lock, `depends` not done or missing, duplicate folders, no git, no base commit. Assert the Step fields, the CLI
  lines and exit codes, and that `next_step` leaves the tree unchanged (hash every file before
  and after).
- `tests/test_021_skill.py`: parse the kit's `skills/autopilot/SKILL.md` front matter (R021-08)
  and check the references of R021-09 and the WORKFLOW.md string of R021-25.
- R021-10 to R021-21 are `[manual]`.
