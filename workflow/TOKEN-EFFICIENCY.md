# Token efficiency

The kit's default playbook. It is tool-neutral; `lint-instructions` and the other commands
enforce the numbers below.

## 1. Small always-loaded context
Target about 3k tokens at session start. AGENTS.md stays within 150 lines. CLAUDE.md is the
`@AGENTS.md` import plus tool-only notes. Path-scoped rules and on-demand skills carry the rest.
Link docs instead of importing them. `lint-instructions` enforces it.

## 2. No exploration tax
`docs/CODEMAP.md` maps modules, files and public symbols up front. Each spec's public API
contract says where code goes. Use LSP or code-intelligence plugins where the tool has them.

## 3. Compressed tool output
`agentkit test` prints only the summary and the failures, at most 60 lines; the full log is kept
in `.agentkit/state/last-test.log`. Test commands run in quiet mode. Reads of build outputs are
denied. Golden files are compact text.

## 4. Short sessions that resume from files
One spec phase per session, and `/clear` between phases. State lives in files: the spec's
`status:`, the `tasks.md` checkboxes and `progress.md` from `handoff`. The session-start
`status` is at most 10 lines. When compacting, keep the spec ID, its phase, the failing tests
and the next task.

## 5. Model and effort routing
- Specs, tests and audits: strong model, high effort. Frozen tests are permanent.
- Implementation: standard model, medium effort. The frozen tests are the oracle.
- Summarising and exploration: fast model, in subagents, so verbose output stays out of the
  main context. Trivial shell or git steps never go to a subagent.

## 6. Prompt-cache hygiene
Keep instruction files stable. Do not edit instructions, settings or MCP servers mid-session.
Prefer CLIs over MCP servers. Avoid idle gaps longer than the cache lifetime during active work.

## 7. Fast loops
Run targeted tests (`test_one_cmd`) while implementing, and the full check only before a
commit. Keep the toolchain's own caches on.

## 8. Measure
Show context usage in the status line where the tool can. Check usage per skill and subagent.
The budgets below are the defaults.

| Budget | Default | Set by |
|---|---|---|
| `status` output | 10 lines, 200 characters each | 006 |
| `agentkit test` output | 60 lines | 007 |
| `agents_md_lines` | 150 | 009 |
| `claude_md_lines` | 40 | 009 |
| `rule_md_lines` | 80 | 009 |
| `skill_md_lines` | 500 | 009 |
| `skill_description_chars` | 200 | 009 |
| `duplicate_min_lines` | 3 | 009 |
| `always_loaded_tokens` | 3000 | 009 |
