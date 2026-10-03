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
audit. Every agent approval made through the CLI is appended to an append-only log. A critical
problem stops the run and writes an escalation record: the same gate rejected twice in a row (N
configurable), a failing `lock verify` or `lock audit`, or a change that touches spec 000 or a
hard rule. `status` shows open escalations, and chaos mode stays paused until the owner clears
them. Off by default; with it off, every existing owner gate behaves exactly as before.

The kit cannot prove that a verdict came from an independent reviewer: an agent could write the
review file itself, skip submitting a rejection, or edit `status:` in `spec.md` by hand. Chaos
mode trades those guarantees for speed. What it keeps is visibility: the CLI refuses agent gate
moves outside `chaos approve` (R020-31), every pass, rejection, unfreeze and escalation made
through it is in one append-only log with a hashed copy of the review it relied on, and the
critical checks run mechanically at every step.

The `/autopilot` skill is 021. This spec is the CLI and the checks.

## Requirements (EARS)

### Conventions
- "Agent environment" means `lock.human_check()` returns a reason (R002-20).
- "Chaos applies to spec NNN" means chaos mode is enabled, NNN is not `000`, and either
  `[chaos] specs` is empty or lists NNN.
- `chaos` functions raise `ChaosError` for refusals that exit 1 and `ChaosUsageError` (a
  `ChaosError`) for those that exit 2. `clear` raises `lock.OwnerCheckError` (exit 2) in an agent
  environment. A malformed `[chaos]` table raises `ConfigError` (exit 2).
- Timestamps are UTC `YYYY-MM-DDTHH:MM:SSZ`. `now` and `user` are injectable as in 002.
- The **base commit** is the `commit` of the newest log record, or, when the log has no record,
  the newest commit that changed `agentkit.toml`.
- "Changed since the base commit" means listed by `git diff --name-only --no-renames <base>`
  (worktree and index against the base) or by `git ls-files --others --exclude-standard`.

### Configuration
- **R020-01** agentkit shall read an optional `[chaos]` table:
  - `enabled` (bool, default `false`);
  - `specs` (list of strings matching `^\d{3}$`, default `[]` = every spec; numbers of specs
    that do not exist are ignored);
  - `max_rejections` (int ≥ 1, default 2);
  - `log` (repo-relative path inside the root, default `chaos-log.jsonl`);
  - `escalate_globs` (list of globs; when set it replaces the default
    `["{specs}/000-*/**", "AGENTS.md", "CLAUDE.md", "docs/adr/**", "agentkit.toml", "{roles}/**"]`;
    `{specs}` and `{roles}` are replaced by `[paths] specs` and `[paths] roles` in both).

  Unknown keys are ignored.
- **R020-02** If a `[chaos]` value has the wrong type or is out of range, or `log` is absolute or
  leaves the root, then `chaos.settings()` shall raise `ConfigError` naming the dotted key (for
  example `chaos.max_rejections`), and chaos commands exit 2.
- **R020-03** If `[chaos] specs` lists `000`, then `chaos.settings()` shall raise `ConfigError`
  naming `chaos.specs`. Spec 000 (vision and constitution) is never under chaos mode.
- **R020-04** Where chaos mode is off (no `[chaos]` table, or `enabled = false`), `chaos approve`
  and `chaos unfreeze` shall exit 2 saying that the owner approves gates.
- **R020-36** Where chaos mode is off, no command other than the `chaos` commands shall change
  its behaviour because of this spec, except the guard (R020-29, R020-30, R020-42) and
  `lock audit`, which checks an existing chaos log (R020-28, through the 002 amendment).
- **R020-05** If spec NNN exists but chaos does not apply to it (including spec 000), then
  `chaos approve NNN …` and a `chaos unfreeze` of its files shall exit 1 saying that the spec is
  not under chaos mode.
- **R020-06** `chaos approve`, `chaos unfreeze` and `chaos clear` shall exit 2 when the root is
  not a git repository. `chaos approve` and `chaos unfreeze` shall also exit 2 when there is no
  base commit, with a hint to commit `agentkit.toml`.

### The chaos log
- **R020-07** The chaos log shall be a UTF-8 JSON Lines file: one object per line, written with
  `json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"))` and an LF. A new
  record is appended; earlier lines are never rewritten.
- **R020-08** Every record shall hold `seq` (its 1-based line number), `time`, `kind`
  (`approve`, `reject`, `unfreeze`, `escalate` or `clear`), `commit` (HEAD's full hash), `user`
  (git `user.name`, or `unknown`) and `actor` (`agent` in an agent environment, else `human`).
- **R020-09** `approve` and `reject` records shall also hold `spec`, `gate`, `role`, `verdict`
  (the normalised verdict line, R020-13), `review` (repo-relative path of the stored review) and
  `review_sha256`. An `approve` of gate `frozen` has `role`, `verdict`, `review` and
  `review_sha256` set to `null`, and also holds `files` (the newly frozen paths, sorted) and
  `based_on` (the `seq` of the spec's newest `approve` of `tests-approved`, or `null`).
- **R020-10** `escalate` records shall also hold `spec`, `gate`, `cause` (`rejections`,
  `verify`, `audit`, `protected` or `base`) and `detail` (a list of strings). `unfreeze` records
  hold `spec`, `gate` (`"unfreeze"`), `files`, `reason`, `role`, `verdict`, `review` and
  `review_sha256`. `clear` records hold `escalations` (a list of `seq`) and `note`.
- **R020-11** An escalation is open when no `clear` record lists its `seq`. Chaos mode is
  **paused** while it is enabled and at least one escalation is open.
- **R020-37** If a log line is not a JSON object with the common fields of R020-08, the fields
  of its kind (R020-09, R020-10), and `seq` equal to its line number, then `chaos.read_log()`
  shall raise `ChaosError` naming the line number. A missing log reads as no records.

### Reviews and verdicts
- **R020-12** The review for each gate shall come from this role, with this passing and this
  failing verdict line (`chaos.REVIEWS`):
  - `approved`: spec-reviewer, `verdict: ready for owner approval` / `verdict: needs changes`;
  - `tests-approved`: test-auditor, `verdict: ready to freeze` / `verdict: needs changes`;
  - `done`: impl-reviewer, `verdict: approve` / `verdict: needs changes`;
  - `unfreeze`: test-auditor, `verdict: unfreeze justified` / `verdict: keep frozen`.
- **R020-13** The verdict shall be the review file's last non-empty line, with surrounding
  whitespace, backquotes and asterisks removed, inner runs of whitespace collapsed to one space,
  and lowercased. If it equals neither line of the gate, or the file is missing, empty or not
  UTF-8, then the command shall exit 2, write nothing, and quote the line it found (or say that
  there is none).
- **R020-14** When a record cites a review, the review file shall be copied byte for byte to
  `<spec dir>/reviews/<seq>-<gate>.md` (replacing any file there) and its SHA-256 (as R002-03)
  stored in the record.

### Order of checks
- **R020-38** `chaos approve` and `chaos unfreeze` shall check in this order, stopping at the
  first failure; steps 1 to 5 write nothing:
  1. exit 2: the `[chaos]` table (R020-02, R020-03), chaos off (R020-04), arguments (R020-15,
     R020-23), git and base commit (R020-06);
  2. exit 1: the log reads (R020-37), the spec exists, chaos applies (R020-05), the phase
     (R020-16, R020-39), the paths (R020-23);
  3. exit 2: the review (R020-13);
  4. exit 1: not paused (R020-18);
  5. exit 1: trace, for `tests-approved` only (R020-17);
  6. the critical checks (R020-19);
  7. the verdict (R020-20 to R020-22, R020-24, R020-25).

### Gates
- **R020-15** `agentkit chaos approve NNN GATE [--review FILE]` shall accept the gates
  `approved`, `tests-approved`, `frozen` and `done`. `--review` is required for every gate except
  `frozen`, where it is refused. A missing or refused `--review`, or an unknown gate, exits 2.
- **R020-16** The spec's phase shall be `draft` for `approved`, `tests-draft` for
  `tests-approved`, `tests-approved` for `frozen`, and `frozen` for `done`. Otherwise the command
  shall exit 1 naming the current phase. A spec that does not exist exits 1.
- **R020-17** For `tests-approved`, the command shall exit 1 when `trace --spec NNN` fails for
  any reason (R005-16, R005-19, R005-20), listing its output.
- **R020-18** While chaos mode is paused, `chaos approve` and `chaos unfreeze` shall exit 1 and
  list the open escalations with the hint to ask the owner.
- **R020-19** The critical checks shall run in this order. On the first failure the command shall
  append an `escalate` record with that cause and detail, change nothing else, print what is
  blocked and why with the hint `owner: agentkit chaos log --open`, and exit 1:
  - `base`: the base commit no longer exists in the repository (detail: its hash);
  - `verify`: `lock.verify(cfg)` reports a violation (detail: `<kind> <path>` per violation);
  - `audit`: `lock.audit(cfg, base=<base commit>)` reports a problem (detail: the problems);
  - `protected`: a path changed since the base commit matches `escalate_globs` (detail: the
    paths, sorted).
- **R020-20** When the verdict fails, the command shall append a `reject` record, leave the
  phase unchanged and exit 1.
- **R020-21** When the `reject` records for the same spec and gate that are newer than the
  newest `approve` or `unfreeze` record of that spec and gate, and newer than the newest `clear`
  record, number `max_rejections` or more, the command shall append, right after the `reject`, an
  `escalate` record with cause `rejections` and detail `#<seq>` of each of those rejects.
- **R020-22** When the verdict passes, the command shall set the spec's status to the gate, then
  append the `approve` record, and exit 0. For `frozen`, which has no verdict, it shall instead
  call `lock.freeze(cfg, spec=NNN)` (which sets the status, R002-13); when the result has errors
  it raises `ChaosError` listing them and appends nothing, otherwise it appends the `approve`
  record (with `files` possibly empty) and exits 0.

### Agent unfreeze
- **R020-23** `agentkit chaos unfreeze PATH... --reason TEXT --review FILE` shall require a
  reason of at least 5 characters after stripping and a `--review` (else exit 2). Directory
  arguments stand for the frozen files inside them. Every resulting path shall be frozen and all
  of them shall have the same non-null `spec` in the lock; otherwise the command exits 1 naming
  the offending paths, with a hint to ask the owner.
- **R020-39** The spec named by the paths shall be in phase `frozen` or `done`; otherwise
  `chaos unfreeze` exits 1 naming the phase.
- **R020-24** When the unfreeze verdict fails, R020-20 and R020-21 shall apply with gate
  `unfreeze`.
- **R020-25** When the unfreeze verdict passes, the command shall remove the paths from the
  lock, set the spec's status to `tests-draft`, append the `unfreeze` record, and append to the
  unfreeze log (creating it with `LOG_HEADER`, R002-25) these lines, exactly:

  ```text
  <empty line>
  ## <timestamp> - chaos agent (<user>)
  reason: <stripped reason>
  review: <stored review path> sha256 <hex> (chaos log #<seq>)
  - <path>            (one line per file, sorted by path)
  ```

  It exits 0. It shall not call `human_check()` or open the console.

### Owner commands
- **R020-26** `agentkit chaos clear (SEQ... | --all) --note TEXT` shall check, in this order:
  agent environment (raise `OwnerCheckError`, exit 2); exactly one of SEQs or `--all` (exit 2);
  a note of at least 5 characters after stripping (exit 2); the SEQs (R020-40); then ask on the
  console for the exact answer `clear <N>`, N being the number of escalations, as R002-21. When
  confirmed it appends one `clear` record listing them, sorted, and exits 0. It works whether
  chaos mode is on or off.
- **R020-40** If a SEQ is not an open escalation, or `--all` finds none, or the console cannot be
  opened, or the answer differs, then `clear` shall raise `ChaosError` (exit 1) and write nothing.
  The SEQs are checked before the console is opened.
- **R020-27** `agentkit chaos log [--spec NNN] [--last N]` shall print the last N records
  (default 20; N < 1 exits 2), oldest first, one line each:
  `#<seq> <time> <kind> <spec> <gate> <info> (<actor>)`, where an absent spec or gate prints `-`
  and info is the verdict (`approve`/`reject`; `files=<n>` for `frozen`), the cause
  (`escalate`), the reason (`unfreeze`) or `#<a>,#<b>: <note>` (`clear`). A line longer than 200
  characters is cut to 199 and ends with `…`. `--spec` keeps only records of that spec. It exits
  0, also with chaos mode off, and exits 1 naming the line when the log is malformed (R020-37).
- **R020-41** `agentkit chaos log --open` shall print only open escalations, in the format of
  R020-27, each followed by its detail lines indented by two spaces, or `no open escalation`.
- **R020-28** `agentkit chaos audit [--base REF] [--staged]` shall exit 1 when the log fails
  R020-37, when a cited review file is missing or its hash differs, or when the log at REF
  (default `HEAD`) is not a line prefix of the current log. A log missing at REF counts as empty.
  When REF does not exist or the root is not a git repository, only the prefix check is skipped.
  `--staged` reads the log and the review files from the git index. No log at all passes.

### Guard
- **R020-29** The guard shall deny a write (by any route R003 classifies as a write) to the chaos
  log and to `<paths.specs>/*/reviews/**`, whether chaos mode is on or off, with a reason naming
  the path. `[guard] allow_globs` does not override this.
- **R020-30** A shell command containing `agentkit` and the consecutive tokens `chaos clear`
  shall be denied, with a reason saying that only the owner clears escalations.
- **R020-42** If the `[chaos]` table is malformed, then the guard shall protect the default log
  path and the reviews (R020-29) instead of failing.

### Gate commands in an agent environment
- **R020-31** While chaos applies to spec NNN, `agentkit spec-status NNN approved|tests-approved|done`
  and `agentkit lock freeze --spec NNN` run in an agent environment shall exit 1, change nothing,
  and point to `agentkit chaos approve NNN <gate>`. A malformed `[chaos]` table makes them exit 2.
  The APIs (`specs.set_status`, `lock.freeze`) do not check this.

### Status
- **R020-32** When a `[chaos]` table exists, line 1 of `status` shall end with ` | chaos: on`
  (enabled), ` | chaos: PAUSED (<k> open escalation(s))` (paused), or ` | chaos: BROKEN (<error>)`
  when the table is malformed or the log fails R020-37, the error cut so that the line stays
  within 200 characters; status still exits 0. With chaos mode off and a valid table, or no
  table, line 1 is unchanged.
- **R020-33** For a spec chaos applies to, the next actions of R006-03 shall be: `draft`:
  `run /spec NNN, then chaos approve NNN approved`; `tests-draft`:
  `chaos approve NNN tests-approved`; `tests-approved`: `chaos approve NNN frozen`; `frozen`:
  `run /implement NNN, then chaos approve NNN done`. `approved` keeps `run /write-tests NNN`, and
  R006-13 still applies.
- **R020-34** While chaos mode is paused and the lock is not violated, the last line of `status`
  shall be `next: HUMAN reviews <k> escalation(s): agentkit chaos log --open`.

### Documentation
- **R020-35** WORKFLOW.md (011) shall describe chaos mode: how the owner enables it, what agents
  may then do, the critical checks, the log, clearing escalations, and the limits listed in the
  Context. [manual]

## Public API contract

```text
agentkit/chaos.py:
  class ChaosError(Exception)               # exit 1
  class ChaosUsageError(ChaosError)         # exit 2
  GATES = ("approved", "tests-approved", "frozen", "done")
  REVIEWS: dict[str, tuple[str, str, str]]  # gate or "unfreeze" -> (role, pass line, fail line)
  CAUSES = ("rejections", "verify", "audit", "protected", "base")
  DEFAULT_LOG = "chaos-log.jsonl"
  @dataclass class Settings:
      enabled: bool; specs: list[str]; max_rejections: int; log_rel: str
      escalate_globs: list[str]; log_path: Path
      def applies(spec_id: str) -> bool
  def settings(cfg) -> Settings                     # raises ConfigError (R020-02, R020-03)
  def read_log(cfg) -> list[dict]                   # raises ChaosError (R020-37)
  def open_escalations(cfg) -> list[dict]
  def parse_verdict(text: str, gate: str) -> bool   # True = pass; raises ChaosUsageError
  def approve(cfg, spec_id, gate, review=None, user=None, now=None) -> dict
      # returns the last record appended; kind "approve" -> exit 0, "reject"/"escalate" -> exit 1
  def unfreeze(cfg, paths, reason, review, user=None, now=None) -> dict   # same convention
  def clear(cfg, seqs=None, note="", all_open=False, confirm=None, user=None, now=None) -> dict
      # confirm(prompt, expected) -> bool; default = prompt through lock.open_console()
  def format_log(records: list[dict], open_only=False) -> list[str]   # R020-27, R020-41
  def audit(cfg, base="HEAD", staged=False) -> list[str]   # problems
  def status_suffix(cfg) -> str   # R020-32, with the leading " | "; "" when unchanged
CLI: agentkit chaos {approve,unfreeze,clear,log,audit}
Changed: agentkit/guard.py (R020-29, R020-30, R020-42), agentkit/status.py (R020-32 to
         R020-34), agentkit/cli.py (R020-31 for spec-status and lock freeze)
```

## Examples and edge cases

`agentkit.toml`: `[chaos] enabled = true`, `specs = ["012"]`. Spec 012 is `draft`; spec 013
exists and is `draft`. One run, in order:

| Step | Result |
|---|---|
| `chaos approve 012 approved --review r.md`, last line `verdict: needs changes` | `reject` #1, exit 1 |
| same again | `reject` #2, `escalate` #3 (`rejections`, detail `#1`, `#2`), exit 1; paused |
| `chaos approve 012 approved --review r2.md`, passing | exit 1: paused, lists #3 |
| owner: `chaos clear 3 --note "spec reworded"` | `clear` #4 |
| `chaos approve 012 approved --review r3.md`, last line `` **`Verdict: Ready for owner approval`** `` | phase `approved`, `approve` #5, review at `specs/012-…/reviews/5-approved.md` |
| `/write-tests 012`, then `chaos approve 012 tests-approved --review a.md`, passing | `approve` #6 |
| `chaos approve 012 frozen` | `lock freeze --spec 012`; `approve` #7, `based_on` 6 |

Independent cases:

| Case | Result |
|---|---|
| `chaos approve 013 approved --review r.md` | exit 1: 013 not under chaos mode |
| `spec-status 012 tests-approved` inside Claude Code, 012 `tests-draft` | exit 1: use `chaos approve 012 tests-approved` |
| `chaos approve 012 frozen --review r.md` | exit 2: `frozen` takes no review |
| 012 `frozen`; agent edited `AGENTS.md`; `chaos approve 012 done --review r.md` | `escalate` (`protected`, detail `AGENTS.md`), phase stays `frozen` |
| `chaos unfreeze tests/test_012_x.py tests/support.py …` | exit 1: `tests/support.py` has no spec; ask the owner |
| `chaos unfreeze tests/test_000_x.py …` | exit 1: spec 000 is not under chaos mode |
| `chaos clear 3 --note x` typed into Claude Code's Bash tool | denied by the guard (R020-30) |
| the branch was rebased and the newest record's commit is gone | `escalate` (`base`) |

- Uncommitted protected changes still count after a `clear` (the base becomes the clear record's
  commit). The owner commits or reverts them before clearing.
- Rejections of `approved` and of `tests-approved` count separately; an `approve` of a gate
  resets that gate's count, and an `unfreeze` resets the `unfreeze` count.
- With chaos off, `chaos log` and `chaos audit` still work on an existing log, and the guard still
  protects it.

## Out of scope

- Proving that a review came from an independent reviewer, that every rejection was submitted,
  or that no `status:` was edited by hand.
- Mechanical checks before `done` beyond the critical checks (running the tests, `depends`
  being `done`): see Open questions.
- Concurrent chaos commands on one repository.
- The `/autopilot` skill (021).
- Changes to approved specs: listed below for the owner to apply.

## Amendments needed in other specs (owner's decision, pending)

- **000**: principle 5 and R000-10 gain "except in chaos mode, which only the owner enables
  (020)"; the glossary's Owner and Gate say the same; the command list gains `chaos` (020). A
  principle changes only with an ADR, so this needs ADR 0002.
- **001**: R001-05 lists `[chaos]` (read by 020).
- **002**: R002-20 and R002-21 note that `chaos unfreeze` (R020-25) bypasses them by design;
  R002-24 notes the `chaos agent` entry; `lock audit` (R002-27, R002-28) also runs `chaos.audit`
  when a chaos log exists, so pre-commit and CI (018) check it; `lock freeze --spec` refuses
  agents where chaos applies (R020-31).
- **003**: R003-09 lists the chaos log and reviews (R020-29, R020-42); R003-13 lists
  `chaos clear` (R020-30); R003-21 (inline scripts) and R003-27 (degraded mode) also cover the
  chaos log.
- **005**: R005-06 notes the agent refusal of R020-31; the Open questions decision gains the
  chaos exception.
- **006**: R006-02, R006-03 and R006-06 refer to R020-32 to R020-34.
- **010**: the CODEOWNERS block (R010-10) covers the chaos log and `specs/*/reviews/`.
- **011**: R011-12: the test-auditor role also ends an unfreeze review with
  `verdict: unfreeze justified` or `verdict: keep frozen`; R011-05: AGENTS.md hard rule 2 (never
  edit the chaos log or reviews, never run `chaos clear`) and rule 3 (where chaos applies, gates
  go through `chaos approve`), within the R011-06 budget; R011-01: chaos mode in WORKFLOW.md
  (R020-35).
- **012** (R012-03) and **014** (R014-03, R014-07): deny edits of the chaos log and reviews and
  Bash `*chaos clear*`.
- **018**: R018-04's failure text also mentions `chaos clear`.

## Additions beyond plan.md

The whole spec is the owner's idea of 2026-10-03, not in plan.md. Design choices to approve:
- One JSON Lines log for approvals, rejections, unfreezes, escalations and clears, rather than a
  log plus separate escalation files, so "open" and "in a row" are computed from one file.
- Reviews copied into `specs/NNN-*/reviews/` with their hash in the log.
- `frozen` takes no review of its own: the test-auditor's `ready to freeze` verdict on
  `tests-approved` is the freeze verdict (R020-09 `based_on`).
- `tests-approved` requires a clean `trace` (R020-17).
- Spec 000 is simply outside chaos mode (R020-05); changes to it escalate through
  `escalate_globs`.
- An agent unfreeze is limited to one spec's tests, from `frozen` or `done`, and sends that spec
  back to `tests-draft`, so the changed tests are audited and frozen again.
- The pause is global, not per spec.
- The base commit for the `protected` and `audit` checks is the newest log record's commit; a
  vanished base escalates (`base`).
- `spec-status` and `lock freeze --spec` refuse gate moves by agents where chaos applies (R020-31).
- Requires git for the mutating commands (R020-06).

## Open questions

1. Who reviews an agent unfreeze: the test-auditor with new verdict lines (proposed, R020-12), the
   impl-reviewer, or both?
2. Should a spec whose Open questions section is not empty escalate on chaos `approved` instead
   of letting the reviewer decide? Open questions are by definition the owner's.
3. `escalate_globs` default: all of `AGENTS.md` and `CLAUDE.md` (proposed; any edit escalates), or
   only the agentkit block between its markers?
4. Should `done` also require mechanical checks: the test command passing (007) and every
   `depends` being `done`? Proposed: no, the impl-reviewer runs the tests; adding 007 would add a
   dependency.
5. ADR 0002 for the principle 5 change: write it now with this spec, or when 020 is implemented?
