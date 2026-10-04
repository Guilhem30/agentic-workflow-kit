# Test audit: spec 003 (guard), round 3

This round covers commit `e852a0e`, which changes only `tests/test_003_degraded.py`. The other
files are unchanged since round 2.

## Stub run

- 93 tests. 91 fail, and every one of their 409 subtest errors is `NotImplementedError("R003-01")`.
  None fail on an import or fixture error.
- `test_R003_01_contract_names` passes on the stub, which is acceptable.
  `test_R003_05_git_bash_drive_paths` is skipped on Linux.

## Round-2 finding 1 (eager lock read): fixed

1. Every case that must show the degraded verdict or the degraded warning under a corrupt lock
   with a loading configuration now involves an in-repository write:
   - writes (`tests/test_003_degraded.py:53-55`, `:73-77`, `:79-83`, `:85-90`, `:92-95`, `:105-114`)
   - or a shell write argument inside the repository (`:82`, `:101`)

   Judging each of these needs the frozen list, so any correct implementation reads the lock
   and hits the internal error, whether it reads eagerly or lazily. `.github/workflows/ci.yml`
   also qualifies, because a frozen deny outranks ask.

2. The lock-independent allow cases now run with `cfg=None` (`:135-144`): reads, a
   build-output read, `./gradlew test`, `make`, `git commit --no-verify` and paths outside the
   repository. There degraded mode is unconditional (R003-29, plan.md).

3. **`assert_denied_either_way` (`:34-40`) is sound.** It still forces the behaviour that
   matters:
   - An eager implementation enters degraded mode and must still deny the configured lock,
     unfreeze log, reviews path and chaos log (R003-27, "the configured one when it can be
     read").
   - A lazy implementation denies them in normal mode under R003-09.
   - A crash in both modes still errors the test.
   - The degraded reason text for kit files stays pinned by the `cfg=None` twin (`:130-133`).

## Remaining notes (not blocking)

4. **Low, carried over:**
   - The null-device ignore rule cannot be observed on its own.
   - `robocopy` is not tested.
   - `core.hookspath` in lower case goes beyond the literal R003-15 text.
   - There is no negative case for `--no-verify` outside git.

   All four were accepted in round 2.

5. **Info, open owner question:** R003-30 (exit 1 on a degraded allow) and R003-31 (stderr
   warning for an unparseable payload) are not owned by any 004 requirement.
   - R004-02 turns a bad payload into `{}` silently.
   - R004-10 says an allow exits 0.
   - `Decision` has no degraded flag.

   This is recorded in `specs/003-guard/progress.md`. It does not affect the 003 tests, which
   stay compatible with adding a defaulted `Decision` field later. It must be settled before
   004's tests freeze.

6. **Info:** No contradictions with `tests/test_020_guard_status.py`. Isolation and flakiness
   are unchanged from round 2: tests use their own temp directories, a cleaned environment, a
   restored cwd, no network, no real home directory, best-of-3 timing with a fresh `cfg`, and
   git mocks asserted uncalled.

verdict: ready to freeze
