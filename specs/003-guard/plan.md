# 003 Guard: plan

## Approach

Implement `agentkit/guard.py` per the API contract. Only the contract names are public; every
helper is private. `evaluate(cfg, actions, cwd)` runs in three layers:

1. **Context** (built once per call): repository root, tracked working directory, the frozen
   set from `lock.load_lock(cfg)` lower-cased (plus a basename index and a set of frozen parent
   directories, so every lookup is O(1) for R003-28), the protected and ask globs, the chaos
   log path (`chaos._log_rel_lenient`, R020-42) and the specs path for `*/reviews/**`.
2. **Path rules** for Write and Read actions (R003-04 to R003-12), matched with
   `util.glob_match` (already case-insensitive, R003-06).
3. **Shell analysis** (R003-13 to R003-26, R003-32): `\` → `/`, `shlex` with
   `punctuation_chars`, a regex fallback on unbalanced quotes; segments at operators; prefix
   words and assignments skipped; a cwd stack for `cd`/`pushd`/`popd`/`Set-Location`; write
   arguments from redirections, write commands, git path commands and inline interpreters.
   Every write argument goes through the path rules of layer 2 plus the glob, directory and
   basename rules.

The verdict is the most severe one; reasons are de-duplicated in order (R003-02).

**Degraded mode** (R003-27, R003-29): any exception in layers 1 to 3 switches to a minimal
evaluator that uses only globs: the profile's `frozen_globs`, or, when `cfg` is `None` (the
configuration did not load), the union of `frozen_globs` over the kit's shipped profiles. It
never reads the lock, runs the shell analysis or calls git. `cfg=None` is how the CLI (004)
passes "no configuration"; the root then comes from `config.find_root(cwd)`.

R003-30 (exit 1 for a degraded allow) and R003-31 (payload that does not parse) are rendered by
the `guard` command of 004; 003 tests the decision and the stderr message.

## Files

- `agentkit/guard.py`

## Test strategy

`tests/test_003_paths.py` (R003-01 to R003-12), `tests/test_003_shell.py` (R003-13 to R003-26,
R003-32, every example row), `tests/test_003_degraded.py` (R003-27, R003-29 to R003-31),
`tests/test_003_perf.py` (R003-28). Fixture: a frozen `app/src/test/FooTest.kt`.
