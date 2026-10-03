# 001 Config and profiles: plan

## Approach

Implement the stubs in `agentkit/config.py` and `agentkit/util.py` exactly as the API contract
says. `tomllib` parses the config. `Config` is a dataclass whose properties read `data` and
`profile`, with defaults applied once at load time. Globs compile to one regular expression per
pattern (R001-14 to R001-16), cached.

## Files

- `agentkit/config.py`: root discovery, loading, the profile overlay, model tiers,
  `MODELS_HELP`
- `agentkit/util.py`: `glob_to_regex`, `glob_match`
- `agentkit/cli.py`: `main()` dispatch, the `models` command, mapping `ConfigError` to exit 2
- `profiles/generic.toml`: shipped from 001 on (R001-08); it may be empty

## Test strategy

Frozen tests: `tests/test_001_config.py`, `tests/test_001_globs.py`, `tests/test_001_models.py`.
Run one module at a time while working, then the full suite.
