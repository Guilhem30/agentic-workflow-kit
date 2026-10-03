---
id: "020"
title: Chaos mode: agent-approved gates
status: draft
depends: ["001", "002", "003", "005", "006"]
---

# 020 Chaos mode: agent-approved gates

## Context

An opt-in mode in which agents pass the gates themselves, without the owner, unless a critical
problem arises. Only the owner turns it on, in `[chaos]` of `agentkit.toml` (a file agents cannot
write, R003-09), for the whole repository or for chosen specs. With chaos mode on, an agent may
set `approved`, `tests-approved` and `done` and run `lock freeze`, each only with a passing
verdict from the matching reviewer role (spec-reviewer, test-auditor, impl-reviewer). An agent may
unfreeze a test when a reviewer agrees; the unfreeze log marks it as an agent unfreeze for later
audit. Every agent approval is appended to an append-only approval log. A critical problem stops
the run and writes an escalation record: the same gate rejected twice in a row (N configurable),
a failing `lock verify` or `lock audit`, or a change that touches spec 000 or a hard rule.
`status` shows open escalations, and chaos mode stays paused until the owner clears them. Off by
default; with it off, every existing owner gate behaves exactly as before.

The kit cannot prove that a verdict came from an independent reviewer: an agent could write the
review file itself. Chaos mode trades that guarantee for speed. What it keeps is visibility: every
agent gate pass, rejection, unfreeze and escalation is in one append-only log, with a hashed copy
of the review it relied on, and the critical checks run mechanically at every step.

The `/autopilot` skill and the reviewer role wiring are 021. This spec is the CLI and the checks.

## Requirements (EARS)

### Conventions
- "Agent environment" means `lock.human_check()` returns a reason (R002-20).
- "Chaos applies to spec NNN" means chaos mode is enabled and either `[chaos] specs` is empty or
  lists NNN. It never applies to spec 000 (R020-03).
- `chaos` functions raise `ChaosError` for refusals that exit 1 and `ChaosUsageError` (a
  `ChaosError`) for those that exit 2. `clear` raises `lock.OwnerCheckError` (exit 2) in an agent
  environment. A malformed `[chaos]` table raises `ConfigError` (exit 2).
- Timestamps are UTC `YYYY-MM-DDTHH:MM:SSZ`. `now` and `user` are injectable as in 002.
- The "base commit" is the `commit` of the newest log record, or, when the log has no record, the
  newest commit that changed `agentkit.toml`.

### Configuration
- **R020-01** agentkit shall read an optional `[chaos]` table with `enabled` (bool, default
  `false`), `specs` (list of 3-digit spec numbers, default `[]` = every spec), `max_rejections`
  (int ≥ 1, default 2), `log` (repo-relative path, default `chaos-log.jsonl`) and `escalate_globs`
  (list of globs, default `["<paths.specs>/000-*/**", "AGENTS.md", "CLAUDE.md", "docs/adr/**"]`).
- **R020-02** If a `[chaos]` value has the wrong type or is out of range, then chaos commands
  shall exit 2 naming the dotted key (for example `chaos.max_rejections`).
- **R020-03** If `[chaos] specs` lists `000`, then chaos commands shall exit 2 naming
  `chaos.specs`. Spec 000 (vision and constitution) is never under chaos mode.
- **R020-04** Where chaos mode is off (no `[chaos]` table, or `enabled = false`), `chaos approve`
  and `chaos unfreeze` shall exit 2 saying that the owner approves gates, and no other command
  shall change its behaviour because of this spec, except the guard rules of R020-29 and R020-30.
- **R020-05** If spec NNN exists but chaos does not apply to it, then `chaos approve NNN …` and a
  `chaos unfreeze` of its files shall exit 1 saying that the spec is not under chaos mode.
- **R020-06** Chaos commands other than `log` shall exit 2 when the root is not a git repository,
  or when there is no base commit, with a hint to commit `agentkit.toml`.

### The chaos log
- **R020-07** The chaos log shall be a UTF-8 JSON Lines file: one JSON object per line, keys
  sorted, LF endings. A new record is appended; earlier lines are never rewritten.
- **R020-08** Every record shall hold `seq` (1 + the number of existing records), `time`, `kind`
  (`approve`, `reject`, `unfreeze`, `escalate` or `clear`), `commit` (HEAD's full hash), `user`
  (git `user.name`, or `unknown`) and `actor` (`agent` in an agent environment, else `human`).
- **R020-09** `approve` and `reject` records shall also hold `spec`, `gate`, `role`, `verdict`
  (the normalised verdict line, R020-13), `review` (repo-relative path of the stored review) and
  `review_sha256`. An `approve` of gate `frozen` holds `files` (the newly frozen paths) and
  `based_on` (the `seq` of the spec's newest `approve` of `tests-approved`, or `null`) instead of
  `verdict`, `review` and `review_sha256`.
- **R020-10** `escalate` records shall also hold `spec`, `gate`, `cause` (`rejections`,
  `verify`, `audit`, `protected` or `spec-000`) and `detail` (a list of strings). `unfreeze`
  records hold `spec`, `files`, `reason`, `role`, `verdict`, `review` and `review_sha256`.
  `clear` records hold `escalations` (a list of `seq`) and `note`.
- **R020-11** An escalation is open when no `clear` record lists its `seq`. Chaos mode is
  **paused** while at least one escalation is open.

### Reviews and verdicts
- **R020-12** The review for each gate shall come from this role, with this passing and this
  failing verdict line (`chaos.REVIEWS`):
  - `approved`: spec-reviewer, `verdict: ready for owner approval` / `verdict: needs changes`;
  - `tests-approved`: test-auditor, `verdict: ready to freeze` / `verdict: needs changes`;
  - `done`: impl-reviewer, `verdict: approve` / `verdict: needs changes`;
  - `unfreeze`: test-auditor, `verdict: unfreeze justified` / `verdict: keep frozen`.
- **R020-13** The verdict shall be the review file's last non-empty line, with surrounding
  whitespace, backquotes and asterisks removed and lowercased. If it equals neither line of the
  gate, or the file is missing or not UTF-8, then the command shall exit 2, write nothing, and
  quote the line it found.
- **R020-14** When a record cites a review, the review file shall be copied byte for byte to
  `<spec dir>/reviews/<seq>-<gate>.md` and its SHA-256 (as R002-03) stored in the record.

### Gates
- **R020-15** `agentkit chaos approve NNN GATE [--review FILE]` shall accept the gates
  `approved`, `tests-approved`, `frozen` and `done`. `--review` is required for every gate except
  `frozen`, where it is refused. A missing or refused `--review`, or an unknown gate, exits 2.
- **R020-16** The spec's phase shall be `draft` for `approved`, `tests-draft` for
  `tests-approved`, `tests-approved` for `frozen`, and `frozen` for `done`. Otherwise the command
  shall exit 1, naming the current phase, and write nothing. A spec that does not exist exits 1.
- **R020-17** For `tests-approved`, the command shall exit 1 and write nothing when
  `trace --spec NNN` reports an untraced requirement, listing them.
- **R020-18** While chaos mode is paused, `chaos approve` and `chaos unfreeze` shall exit 1,
  write nothing, and list the open escalations with the hint to ask the owner.
- **R020-19** After R020-15 to R020-18 pass, the command shall run the critical checks, in this
  order, and on the first failure append an `escalate` record with its cause and detail, change
  nothing else, print what is blocked and why, and exit 1:
  - `spec-000`: the spec is 000 (possible only through `chaos unfreeze` of a 000 test);
  - `verify`: `lock.verify(cfg)` reports a violation (detail: the violations);
  - `audit`: `lock.audit(cfg, base=<base commit>)` reports a problem (detail: the problems);
  - `protected`: a path changed since the base commit (committed, staged, unstaged or untracked
    and not ignored) matches `escalate_globs` (detail: the paths, sorted).
- **R020-20** When the verdict fails, the command shall append a `reject` record, leave the
  phase unchanged and exit 1.
- **R020-21** When the `reject` records for the same spec and gate since the newest `approve` of
  that spec and gate, and since the newest `clear` record, reach `max_rejections`, the command
  shall also append an `escalate` record with cause `rejections` right after the `reject`.
- **R020-22** When the verdict passes, the command shall set the spec's status to the gate (for
  `frozen`, through `lock.freeze(cfg, spec=NNN)`, R002-13), then append the `approve` record, and
  exit 0. If `lock.freeze` reports errors, it shall exit 1 and append nothing.

### Agent unfreeze
- **R020-23** `agentkit chaos unfreeze PATH... --reason TEXT --review FILE` shall require a
  reason of at least 5 characters after stripping (else exit 2), and paths that are all frozen
  with the same non-null `spec` in the lock (else exit 1, naming the offending paths, with a hint
  to ask the owner). It then applies R020-18, R020-19 and R020-13 with gate `unfreeze`.
- **R020-24** When the unfreeze verdict fails, R020-20 and R020-21 shall apply with gate
  `unfreeze`.
- **R020-25** When the unfreeze verdict passes, the command shall remove the paths from the
  lock, append to the unfreeze log an entry `## <timestamp> - chaos agent (<user>)`, then
  `reason: <text>`, then `review: <stored review path> sha256 <hex> (chaos log #<seq>)`, then one
  `- <path>` line per file sorted by path (blank line before, as R002-24), set the spec's status
  to `tests-draft`, append the `unfreeze` record, and exit 0. It shall not call `human_check()`
  or ask on the console.

### Owner commands
- **R020-26** `agentkit chaos clear SEQ... --note TEXT` (or `--all` for every open escalation)
  shall refuse in an agent environment (exit 2), require a note of at least 5 characters, ask on
  the console for the exact answer `clear <N>` (N escalations, as R002-21), and append one
  `clear` record. An unknown or already cleared SEQ, a refused confirmation, or no console exits
  1 and writes nothing. It works whether chaos mode is on or off.
- **R020-27** `agentkit chaos log [--open] [--spec NNN] [--last N]` shall print one line per
  record, newest last: `#<seq> <time> <kind> <spec> <gate|cause> <verdict|reason|note> (<actor>)`,
  at most 200 characters each; default `--last 20`. `--open` prints only open escalations, each
  followed by its detail lines indented by two spaces. It exits 0, also with chaos mode off.
- **R020-28** `agentkit chaos audit [--base REF] [--staged]` shall exit 1 when the log at REF
  (default `HEAD`) is not a line prefix of the current log, when a line does not parse as a
  record, or when a cited review file is missing or its hash differs. A log missing at REF counts
  as empty; a REF that does not exist passes (as R002-29). `--staged` reads the log and the
  review files from the git index.

### Guard
- **R020-29** The guard shall deny a write to the chaos log and to `<paths.specs>/*/reviews/**`,
  whether chaos mode is on or off, with a reason naming the path.
- **R020-30** A shell command containing `agentkit` and `chaos clear` shall be denied, with a
  reason saying that only the owner clears escalations.

### Gate commands in an agent environment
- **R020-31** While chaos applies to spec NNN, `agentkit spec-status NNN approved|tests-approved|done`
  and `agentkit lock freeze --spec NNN` run in an agent environment shall exit 1, change nothing,
  and point to `agentkit chaos approve NNN <gate>`. The APIs (`specs.set_status`, `lock.freeze`)
  do not check this.

### Status
- **R020-32** Where chaos mode is enabled, line 1 of `status` shall end with ` | chaos: on`, or
  ` | chaos: PAUSED (<k> open escalation(s))` while paused, or ` | chaos: BROKEN (<error>)` when
  the `[chaos]` table or the log cannot be read (status still exits 0). With chaos mode off,
  line 1 is unchanged.
- **R020-33** For a spec chaos applies to, the next actions of R006-03 shall be: `draft`:
  `run /spec NNN, then chaos approve NNN approved`; `tests-draft`:
  `chaos approve NNN tests-approved`; `tests-approved`: `chaos approve NNN frozen`; `frozen`:
  `run /implement NNN, then chaos approve NNN done` (R006-13 still applies).
- **R020-34** While chaos mode is paused and the lock is not violated, the last line of `status`
  shall be `next: HUMAN reviews <k> escalation(s): agentkit chaos log --open`.

### Documentation
- **R020-35** WORKFLOW.md (011) shall describe chaos mode: how the owner enables it, what agents
  may then do, the critical checks, the log, clearing escalations, and the limit that verdicts
  cannot be proven independent. [manual]

## Public API contract

```text
agentkit/chaos.py:
  class ChaosError(Exception)               # exit 1
  class ChaosUsageError(ChaosError)         # exit 2
  GATES = ("approved", "tests-approved", "frozen", "done")
  REVIEWS: dict[str, tuple[str, str, str]]  # gate or "unfreeze" -> (role, pass line, fail line)
  CAUSES = ("rejections", "verify", "audit", "protected", "spec-000")
  @dataclass class Settings:
      enabled: bool; specs: list[str]; max_rejections: int; log_rel: str
      escalate_globs: list[str]; log_path: Path
      def applies(spec_id: str) -> bool
  def settings(cfg) -> Settings                     # raises ConfigError (R020-02, R020-03)
  def read_log(cfg) -> list[dict]                   # [] when the log is missing
  def open_escalations(cfg) -> list[dict]
  def parse_verdict(text: str, gate: str) -> bool   # True = pass; raises ChaosUsageError
  def approve(cfg, spec_id, gate, review=None, user=None, now=None) -> dict
      # returns the last record appended; kind "approve" -> exit 0, "reject"/"escalate" -> exit 1
  def unfreeze(cfg, paths, reason, review, user=None, now=None) -> dict   # same convention
  def clear(cfg, seqs=None, note="", all_open=False, confirm=None, user=None, now=None) -> dict
      # confirm(prompt, expected) -> bool; default = lock.open_console() prompt
  def audit(cfg, base="HEAD", staged=False) -> list[str]   # problems
  def status_suffix(cfg) -> str                     # R020-32; "" when chaos is off
CLI: agentkit chaos {approve,unfreeze,clear,log,audit}
Changed: agentkit/guard.py (R020-29, R020-30), agentkit/status.py (R020-32 to R020-34),
         agentkit/cli.py (R020-31 for spec-status and lock freeze)
```

## Examples and edge cases

`agentkit.toml`: `[chaos] enabled = true`, `specs = ["012"]`. Spec 012 is `draft`.

| Step | Result |
|---|---|
| `chaos approve 012 approved --review r.md`, last line `verdict: needs changes` | `reject` #1, exit 1 |
| same again | `reject` #2, `escalate` #3 (`rejections`), exit 1; chaos paused |
| `chaos approve 012 approved --review r2.md`, passing | exit 1: paused, lists #3 |
| owner: `chaos clear 3 --note "spec reworded"` | `clear` #4 |
| `chaos approve 012 approved --review r3.md`, last line `` **`Verdict: Ready for owner approval`** `` | phase `approved`, `approve` #5, review at `specs/012-…/reviews/5-approved.md` |
| `chaos approve 013 approved --review r.md` | exit 1: 013 not under chaos mode |
| `spec-status 012 tests-approved` inside Claude Code | exit 1: use `chaos approve 012 tests-approved` |
| `chaos approve 012 frozen --review r.md` | exit 2: `frozen` takes no review |
| agent edited `AGENTS.md`, then `chaos approve 012 done --review r.md` | `escalate` (`protected`, detail `AGENTS.md`), phase stays `frozen` |
| `chaos unfreeze tests/test_012_x.py tests/support.py …` | exit 1: `tests/support.py` has no spec; ask the owner |
| `chaos clear 3 --note x` inside Claude Code | denied by the guard (R020-30); run directly, exit 2 |

- Uncommitted protected changes still count after a `clear` (the base is the clear record's
  commit). The owner commits or reverts them before clearing.
- Rejections of `approved` and of `tests-approved` count separately; an `approve` of a gate
  resets that gate's count.
- With chaos off, `chaos log` and `chaos audit` still work on an existing log, and the guard still
  protects it.

## Out of scope

- Proving that a review came from an independent reviewer, or that every rejection was submitted.
- Concurrent chaos commands on one repository.
- The `/autopilot` skill, and the reviewer role prompts that emit `verdict: unfreeze justified`
  (021).
- Changes to approved specs: listed below for the owner to apply.

## Amendments needed in other specs (owner's decision, pending)

- **000**: principle 5 and R000-10 gain "except in chaos mode, which only the owner enables
  (020)"; the glossary's Owner and Gate say the same. A principle changes only with an ADR, so
  this needs ADR 0002.
- **002**: R002-20 and R002-21 note that `chaos unfreeze` (R020-25) bypasses them by design;
  R002-24 notes the `chaos agent` log entry; R002-27/R002-28 (`lock audit`) also run
  `chaos.audit` so pre-commit and CI (018) check the chaos log; freeze in R020-31.
- **003**: R003-09 lists the chaos log and reviews (R020-29); R003-13 lists `chaos clear` (R020-30).
- **005**: R005-06 notes the agent refusal of R020-31; the Open questions decision gains the
  chaos exception.
- **006**: R006-02, R006-03 and R006-06 refer to R020-32 to R020-34.
- **011**: AGENTS.md hard rule 2 (never edit the chaos log or reviews, never run `chaos clear`)
  and rule 3 (gates go through `chaos approve` where chaos applies).

## Additions beyond plan.md

The whole spec is the owner's idea of 2026-10-03, not in plan.md. Design choices to approve:
- One JSON Lines log for approvals, rejections, unfreezes, escalations and clears, rather than a
  log plus separate escalation files, so "open" and "in a row" are computed from one file.
- Reviews copied into `specs/NNN-*/reviews/` with their hash in the log.
- `frozen` takes no review of its own: the test-auditor's `ready to freeze` verdict on
  `tests-approved` is the freeze verdict (R020-09 `based_on`).
- `tests-approved` requires a clean `trace` (R020-17).
- An agent unfreeze is limited to one spec's tests and sends that spec back to `tests-draft`, so
  the changed tests are audited and frozen again.
- The pause is global, not per spec.
- The base commit for `protected` and `audit` checks is the newest log record's commit.
- `spec-status` and `lock freeze --spec` refuse gate moves by agents where chaos applies (R020-31),
  so every agent gate pass is in the log.
- Requires git (R020-06).

## Open questions

1. Who reviews an agent unfreeze: the test-auditor with new verdict lines (proposed, R020-12), the
   impl-reviewer, or both?
2. Should a spec whose Open questions section is not empty escalate on chaos `approved` instead
   of letting the reviewer decide? Open questions are by definition the owner's.
3. `escalate_globs` default: all of `AGENTS.md` and `CLAUDE.md` (proposed; any edit escalates), or
   only the agentkit block between its markers?
4. ADR 0002 for the principle 5 change: write it now with this spec, or when 020 is implemented?
