---
id: "002"
title: Test-freeze lock
status: tests-draft
depends: ["001", "005"]
---

# 002 Test-freeze lock

## Context

Once the owner approves a spec's tests, they are frozen. `tests.lock.json` records a hash of
every frozen file and is the source of truth for every enforcement layer. Only the owner
unfreezes, by running a command themselves, and every unfreeze is logged.

## Requirements (EARS)

### Conventions
- Paths given to the API are absolute or relative to the root. The CLI resolves its arguments
  against the current directory. Lock keys are always repo-relative with `/` separators.
- Lock functions raise `LockError` for refusals that make the command exit 1 (R002-04, R002-12,
  R002-19, R002-22, R002-23) and `OwnerCheckError` (a `LockError`) for those that exit 2
  (R002-20, R002-31). `freeze` reports per-path problems in `FreezeResult.errors` (R002-11). The
  CLI maps `LockError` to 1, and `OwnerCheckError` and `ConfigError` to 2.
- Spec status is the `status:` front-matter field and the phases are those of R005-02 and R005-03.

### Lock file
- **R002-01** The lock shall be a JSON object
  `{"version": 1, "algorithm": "sha256-lf", "files": {<repo-relative path>: {"sha256": <hex>, "spec": <"NNN">?}}}`.
- **R002-02** The lock shall be written deterministically: `files` sorted by path, 2-space
  indentation, LF line endings and a trailing newline.
- **R002-03** A file's hash shall be the SHA-256 of its bytes after every CRLF is replaced by LF.
- **R002-04** If the lock is not valid JSON, lacks a `files` object, or names another algorithm,
  then lock commands shall exit 1 with a message naming the problem.
- **R002-05** A missing or empty lock file shall be treated as a lock with no frozen files.

### Freeze
- **R002-06** `lock freeze PATH...` shall freeze each given file, even one that matches no
  `frozen_globs`. A given directory freezes the candidates (R002-07) inside it.
- **R002-07** `lock freeze --spec NNN` shall freeze every not-yet-frozen candidate file that
  belongs to spec NNN. A candidate is a tracked or untracked, non-ignored file that matches
  `frozen_globs` and not `build_output_globs`. A file belongs to the spec when it contains a
  requirement ID of spec NNN (contents decoded as UTF-8 with replacement), or when its path has
  a segment `NNN` or `NNN-*`.
- **R002-08** `lock freeze --all` shall freeze every not-yet-frozen candidate.
- **R002-09** When `--spec NNN` is given, each newly frozen entry shall record `"spec": "NNN"`.
- **R002-10** If a given file is already frozen with the same hash, freeze shall report it as
  unchanged.
- **R002-11** If a file is already frozen with a different hash, or is the lock or the unfreeze
  log, or is outside the repository, or does not exist, then freeze shall write nothing at all,
  list every such problem and exit 1.
- **R002-12** If `--spec NNN` is given and spec NNN does not exist, or its status is not
  `tests-approved`, then freeze shall write nothing and exit 1, naming the current status (or
  saying that the spec does not exist).
- **R002-31** `lock freeze --spec NNN --force` shall bypass R002-12 only after the same owner
  checks as unfreeze: it refuses in an agent environment (R002-20) and requires a console
  confirmation (R002-21, expected answer `force freeze NNN`), otherwise it writes nothing and
  exits 2. `freeze(force=True)` performs the check itself, so no caller can skip it.
- **R002-32** A forced freeze shall append an entry to the unfreeze log:
  `## <UTC timestamp> - <git user.name>`, then `forced freeze of spec NNN (status was <status>)`,
  then one `- <path>` line per frozen file.
- **R002-13** When `lock freeze --spec NNN` succeeds, it shall set spec NNN's status to `frozen`.
  The `freeze` API does this, not only the CLI.
- **R002-14** freeze without paths, `--spec` or `--all` shall exit 2.
- **R002-15** Where the root is not a git repository, candidates shall come from a filesystem walk
  that skips `.git`, `node_modules`, `__pycache__` and `.gradle`.

### Verify and status
- **R002-16** `lock verify` shall report every frozen file that is missing or whose hash differs,
  and exit 1 when there is at least one; otherwise it prints the frozen count and exits 0.
- **R002-17** `lock verify --staged` shall read both the lock and each frozen file from the git
  index instead of the worktree.
- **R002-18** `lock status` shall print the frozen count (per spec), the verify result, and the
  candidates that are not yet frozen (at most 20 listed, with a total). It exits 1 when verify
  finds a violation. `status(cfg)` returns `frozen: int`, `by_spec: dict[str | None, int]` (None
  for entries without a spec), `unfrozen_candidates: list[str]` (sorted, not capped) and
  `violations: list[Violation]`.

### Unfreeze (owner only)
- **R002-19** `lock unfreeze PATH... --reason TEXT` shall require a reason of at least 5
  characters after stripping surrounding whitespace. This is checked before any confirmation.
- **R002-20** If any of the environment variables `AGENTKIT_AGENT`, `CLAUDECODE`,
  `CODEX_SANDBOX`, `CODEX_THREAD_ID`, `OPENCODE` or `PI_CODING_AGENT` is set to a non-empty
  value, then unfreeze shall refuse, name the variable, and exit 2. `unfreeze()` performs the
  check itself, through `human_check()`.
- **R002-21** unfreeze shall ask for confirmation on the controlling console (`/dev/tty` on
  POSIX, `CONIN$`/`CONOUT$` on Windows), never on stdin, by showing the files and requiring
  the exact answer `unfreeze <N>`, where N counts files. The default `confirm` opens the console
  only through `open_console()`, which raises `OSError` when there is no console.
- **R002-22** If the console cannot be opened or the answer differs, then unfreeze shall change
  nothing and exit 1.
- **R002-23** If a given path is not frozen (or a given directory contains no frozen file), then
  unfreeze shall change nothing and exit 1.
- **R002-24** When unfreeze is confirmed, it shall remove the files from the lock and append to
  the unfreeze log an entry `## <UTC timestamp YYYY-MM-DDTHH:MM:SSZ> - <git user.name>`, a
  `reason: <text>` line, and one `- <path>` line per file, sorted by path. Every log entry,
  including R002-32's, is preceded by a blank line. The user is `unknown` when git
  `user.name` is unset.
- **R002-25** A new unfreeze log shall start with `LOG_HEADER`, which states it is append-only. An
  existing log is appended to as it is. Earlier entries shall never be rewritten.

### Restore and audit (approved 2026-10-03)
- **R002-26** `lock restore` shall rewrite each violated frozen file with its content at `--ref`
  (default `HEAD`) only when that content's hash equals the lock entry, and shall list the files
  it could not restore and exit 1 if any. A given path that is not frozen counts as not restored.
- **R002-27** `lock audit --base REF` shall exit 1 when any lock entry present at REF is missing
  or has a different hash now, unless its path appears in an unfreeze-log entry whose header is
  not present in the log at REF.
- **R002-28** `lock audit` shall exit 1 when the log at REF is not a prefix of the current log.
- **R002-29** `lock audit` shall pass when REF does not exist (for example, the first commit). A
  lock or log missing at REF counts as empty.
- **R002-30** `lock audit --staged` shall read the lock and the log from the git index.

## Public API contract

```text
agentkit/lock.py:
  class LockError(Exception)            # exit 1
  class OwnerCheckError(LockError)      # exit 2 (R002-20, R002-31)
  LOG_HEADER: str                       # R002-25
  @dataclass class Violation: path: str; kind: str  # "missing" | "modified"
  @dataclass class FreezeResult: added: list[str]; unchanged: list[str]; errors: list[str]
  def load_lock(cfg) -> dict
  def verify(cfg, staged: bool = False) -> list[Violation]
  def status(cfg) -> dict  # frozen, by_spec, unfrozen_candidates, violations
  def freeze(cfg, paths=None, spec=None, all_candidates=False,
             force=False, confirm=None, user=None, now=None) -> FreezeResult
  def unfreeze(cfg, paths, reason, confirm=None, user=None, now=None) -> list[str]
      # confirm(prompt, expected) -> bool; default = console prompt (injected in tests)
      # user: default git user.name; now: aware UTC datetime, default the current time
  def human_check() -> str | None   # reason for refusing, or None
  def open_console() -> (reader, writer)   # raises OSError when there is no console
  def restore(cfg, paths=None, ref="HEAD") -> (restored: list[str], failed: list[str])
  def audit(cfg, base="HEAD", staged=False) -> list[str]  # problems
CLI: agentkit lock {freeze,verify,status,unfreeze,restore,audit}
```

## Examples and edge cases

- A CRLF checkout and an LF checkout of the same file give the same hash.
- Freezing `core/model/src/test/` freezes `…/R001Test.kt` and `…/golden/ring.txt`, but not
  `core/model/build/…`.
- `--spec 004` freezes `rules/src/test/R004EngineTest.kt` (it contains `R004-02`) and
  `fixtures/004-rules/a.json` (path segment), but not `fixtures/0040/x`.
- Unfreezing inside Claude Code's Bash tool fails with R002-20 (`CLAUDECODE` is set).

## Out of scope

Signing the lock cryptographically. Protection relies on git history, the hooks and CI (018).

## Additions beyond plan.md

- R002-12: freeze refuses unless the spec is `tests-approved`. This enforces the gate order.
- R002-31 and R002-32: an owner-only, logged `--force` (owner's decision, 2026-10-03). An agent
  cannot use it, because of the same environment check and console confirmation as unfreeze, and
  the guard's shell rule (003).
- R002-17: `--staged` verify, used by pre-commit (018) so the committed content is what gets checked.
- R002-20 to R002-22: detecting an agent environment, and confirming on the console, so that an
  agent's piped shell cannot unfreeze.
- Two extra commands, approved by the owner on 2026-10-03 (R002-26 to R002-30):
  - `lock restore [PATH] [--ref REF]`: puts modified or missing frozen files back from git when
    the content at REF matches the lock hash. It gives agents a safe undo, since the guard denies
    `git checkout` on frozen files.
  - `lock audit [--base REF] [--staged]`: fails when a lock entry was removed or re-hashed since
    REF without a matching new unfreeze-log entry, or when the log was rewritten. It closes the
    gap of editing a test and its lock entry together. Used by pre-commit and CI (018).

- Clarifications made while writing the tests (owner's decision, 2026-10-03): the Conventions
  section (paths, errors, spec status); explicit files and directories in R002-06; content
  decoding in R002-07; a missing spec in R002-12; the status set by the API in R002-13; status
  types and exit code in R002-18; the reason length in R002-19; checks inside the API for R002-20
  and R002-31; `open_console()` in R002-21; the log layout, sorting and `unknown` user in
  R002-24/25; unfrozen paths in R002-26; an empty lock or log at REF in R002-29; `force`,
  `confirm`, `user` and `now` on `freeze`.

## Open questions

None.
