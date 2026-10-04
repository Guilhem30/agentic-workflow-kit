# 004 Hook dialects: plan

## Approach

A package `agentkit/payloads/` turns each tool's hook payload into 003's neutral actions and
renders decisions, verify problems and status text in the tool's format.

- `common.actions_for(tool_name, tool_input)` holds the whole mapping (R004-03 to R004-09);
  `patch_paths(text)` reads Codex patches and unified diffs (R004-05).
- `base.HookFormat` is the Claude-shaped dialect: `parse` reads `tool_name`, `tool_input` and
  `cwd`; `pre_response`, `stop_response`, `session_response` render R004-10/11, R004-16/17,
  R004-20. `supports_ask` False turns ask into deny with the R004-12 prefix.
- `base.PluginFormat` reads `{tool, args, cwd}` and always prints a JSON decision (R004-13,
  R004-14, R004-18, R004-20).
- `claude.py`, `codex.py`, `dsh.py`, `opencode.py`, `pi.py` each define `FORMAT`;
  `payloads.FORMATS` maps the five names.
- Degraded mode (R004-22): `pre_response` reads 003's `Decision.degraded` (added by the owner's
  decision of 2026-10-03). A degraded allow gives code 1 and the reason on stderr.

CLI (`agentkit/cli.py`):
- `guard --format F`: read stdin (R004-02; a bad payload is a degraded allow), `load_config()`
  (a `ConfigError` gives `cfg=None`, so 003 runs degraded), `guard.evaluate`, `pre_response`.
- `verify [--format F]`: `lock.verify`; problems are `<kind> <path>` lines plus the hint
  `restore with \`agentkit lock restore\`, or ask the owner to unfreeze` (R004-15, R004-19).
- `status [--format F]`: `agentkit.status.status_lines(cfg)` (006) joined with `\n`. Called
  through the module attribute so tests can patch it until 006 ships. Plain `status` is 006's.
- argparse `choices` give exit 2 for an unknown format (R004-01).

## Files

- `agentkit/payloads/{__init__,base,common,claude,codex,dsh,opencode,pi}.py`
- `agentkit/cli.py`; `agentkit/guard.py` (`Decision.degraded`, already added with the amendment)

## Test strategy

- `tests/hook_fixtures.py`: `HookCase` (003's `GuardCase` repo with a frozen file) and
  `hook(argv, stdin)` returning `(code, stdout, stderr)` separately.
- `tests/test_004_mapping.py`: R004-03 to R004-09 through `actions_for`, `patch_paths`, `parse`.
- `tests/test_004_responses.py`: R004-10 to R004-14, R004-22 through `pre_response` and the CLI.
- `tests/test_004_verify_status.py`: R004-15 to R004-20 (status lines patched).
- `tests/test_004_cli.py`: R004-01, R004-02, and the API surface (`FORMATS`, `FORMAT`).
- `tests/test_004_conformance.py` + `tests/fixtures/payloads/<tool>/*.json`: R004-21. Each
  fixture carries `"req": "R004-21"` so that `lock freeze --spec 004` picks it up (R002-07).
