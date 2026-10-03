---
id: "001"
title: Configuration, profiles, globs and model tiers
status: approved
---

# 001 Configuration, profiles, globs and model tiers

## Context

Every command needs the repository root, the paths of the lock and the specs, and the language
profile (test command, frozen globs, requirement ID regex, and so on). Model tiers let any
provider be used, including local models.

## Requirements (EARS)

### Locating the configuration
- **R001-01** When a command starts, agentkit shall use the directory named by the environment
  variable `AGENTKIT_ROOT` as the repository root if it contains `agentkit.toml`.
- **R001-02** Otherwise, agentkit shall search for `agentkit.toml` from the current directory
  upward and use the first directory that contains one as the root.
- **R001-03** If no `agentkit.toml` is found, then the command (other than `install` and
  `version`) shall exit 2 with a message suggesting `agentkit install`.
- **R001-04** If `agentkit.toml` is not valid TOML, then the command shall exit 2 and name the
  file and the parser's line/column.

### Settings
- **R001-05** agentkit shall read these tables from `agentkit.toml`: `[kit]` (`version`,
  `profile`, `adapters`, `python`, `self_hosted`), `[ci]` (R001-20), `[paths]`, `[models]`,
  `[models.<adapter>]`, `[budgets]`, `[guard]`, `[profile]`.
- **R001-06** Where a `[paths]` key is absent, agentkit shall use these defaults:
  `specs = "specs"`, `lock = "tests.lock.json"`, `unfreeze_log = "tests.unfreeze-log.md"`,
  `codemap = "docs/CODEMAP.md"`, `skills = ".agents/skills"`, `roles = "roles"`.
- **R001-20** agentkit shall read a `[ci]` table:
  - `providers`: a list of `github` and/or `gitlab`; an empty list means no CI;
  - `os`: a list of `linux`, `windows` and/or `macos`;
  - `gitlab_tags`: an optional map from OS to GitLab runner tag.

  A value outside these sets shall make the command exit 2, naming the key.
- **R001-07** Where `[kit] python` is absent, the interpreter command shall be `python` on
  Windows and `python3` elsewhere.

### Profiles
- **R001-08** agentkit shall load the profile named by `[kit] profile` (default `generic`) from
  the first directory that has `<name>.toml`, in this order: `<root>/.agentkit/profiles`,
  `<root>/profiles`, then the kit's own `profiles/`.
- **R001-09** If the profile is not found, then the command shall exit 2 and list the directories
  it searched.
- **R001-10** A profile shall support these keys, with these defaults when absent:
  `test_cmd` (""), `test_cmd_windows` (""), `test_one_cmd` (""), `test_one_cmd_windows` (""),
  `junit_report_glob` ([]), `frozen_globs` (["tests/**", "test/**"]), `test_globs`
  (default: same as `frozen_globs`), `source_globs` ([]), `build_output_globs`
  (["**/build/**", "**/dist/**", "**/node_modules/**", "**/__pycache__/**"]), `req_id_regex`
  (see R001-13), `output_filter_regex`, `format_cmd`, `lint_cmd`, `ci_setup` (""),
  `codemap.symbol_regexes` ([]).
- **R001-11** Values in `agentkit.toml`'s `[profile]` table shall override the profile's values.
  Nested tables (such as `codemap`) shall be merged one level deep.
- **R001-12** If `req_id_regex` does not have at least two capture groups, then the command
  shall exit 2 naming the key.
- **R001-13** The default `req_id_regex` shall match `R004-07`, `R004_07` and `test_R004_07_x`.
  It shall not match `XR004-07` or `R004-0712`. Group 1 is the spec number and group 2 is the
  requirement number.

### Globs
- **R001-14** Glob matching shall work on repo-relative paths with `/` separators. `**/` matches
  zero or more directories, `**` matches anything, `*` and `?` stay within one path segment, and
  `[...]` is a character class (`[!...]` negates).
- **R001-15** Glob matching shall be case-insensitive, so that protection holds on
  case-insensitive filesystems.
- **R001-16** A path given with `\` separators shall be matched as if it used `/`.

### Model routing

Nobody types model names. At install, the owner picks one of two modes with `--models tool|kit`.

**How the kit routes tasks.** Each role and skill has a tier and an effort level:

| Tier | Effort | Roles (subagents) | Skills |
|---|---|---|---|
| strong | high | spec-writer, spec-reviewer, test-writer, test-auditor, impl-reviewer | `/spec`, `/write-tests` |
| standard | medium | implementer | `/implement` |
| fast | low | summarizer | `/freeze`, `/handoff` |

**The two modes:**

| | `--models tool` | `--models kit` |
|---|---|---|
| Who picks the model | The agent tool, exactly as if agentkit were not installed | agentkit, from the tier map it ships for that tool |
| What gets written | No `model` and no `effort` in generated skills and subagents | `model` and `effort` on every generated skill and subagent |
| Claude Code | Your session's model and effort for everything. Subagents follow Claude Code's own default for subagents | strong = Opus, standard = Sonnet, fast = Haiku, with the efforts above |
| Effect on cost | Everything costs what your session model costs. For example, an Opus session pays Opus prices for summaries | The expensive model is used only where frozen tests are written and audited; cheap models do the rest |
| Effect on quality | Depends on the session model. A Sonnet session writes the frozen tests with Sonnet | The strongest model always writes and audits the frozen tests |
| Model updates | Whatever the tool does | Maps use aliases (for example `opus` follows the newest Opus). `agentkit update` brings refreshed maps |
| Best for | Owners who want the tool's own behaviour, or a single fixed model | Most projects: the cost/quality balance of plan Part B §5 |

- **R001-17** In `kit` mode, a tier shall resolve to the kit's built-in map for the adapter.
  In `tool` mode, or when the adapter has no built-in map, it shall resolve to nothing, and the
  adapter omits `model` and `effort`, so the tool decides.
- **R001-18** The built-in maps shall be:
  - `claude-code`: `strong = "opus"`, `standard = "sonnet"`, `fast = "haiku"`;
  - `codex`: the current OpenAI model names for each tier, verified against the Codex docs when
    013 is implemented and recorded with the date in `adapters/README.md`;
  - `opencode`, `pi` and `deepseek-harness`: none, because they work with any provider and the
    kit cannot know which one the owner uses (tool mode always).
- **R001-19** The chosen mode shall be stored as `[models] mode = "tool" | "kit"`.
- **R001-21** The install help text, and the message when `--models` is missing (R010-25), shall
  summarise the two modes in at most 8 lines, with `kit` marked as recommended.
- **R001-22** `agentkit models` shall print, for each configured adapter, the mode, and for each
  tier the model and effort that will be written (or "decided by the tool"). `status` shall not
  print models, so this costs nothing per session.
- **R001-23** Where an owner really wants a specific model, an optional `[models.<adapter>]`
  table with `strong` / `standard` / `fast` shall override the built-in map in `kit` mode. It is
  never required, and install never asks for it.

## Public API contract

```text
agentkit/config.py:
  CONFIG_NAME = "agentkit.toml"
  class ConfigError(Exception)
  @dataclass class Config:
      root: Path; data: dict; profile: dict; kit_source: Path
      def path(key: str) -> str
      lock_rel, unfreeze_log_rel: str; lock_path, unfreeze_log_path, specs_dir, state_dir: Path
      adapters: list[str]; python_cmd: str; self_hosted: bool
      def models(adapter: str | None = None) -> dict[str, str]
      budgets: dict; guard: dict; frozen_globs: list[str]; test_globs: list[str]
  def find_root(start: Path | None = None) -> Path | None
  CLI: agentkit models   # R001-22
  def load_profile(name: str, root: Path | None = None) -> dict
  def load_config(start: Path | None = None, root: Path | None = None) -> Config
agentkit/util.py:
  def glob_to_regex(pattern: str) -> re.Pattern
  def glob_match(path: str, patterns: Iterable[str]) -> bool
```

## Examples and edge cases

| Pattern | Path | Match |
|---|---|---|
| `**/src/test/**` | `core/model/src/test/kotlin/A.kt` | yes |
| `**/src/test/**` | `src/test/A.kt` | yes |
| `tests/**` | `tests` | no (it is the directory itself) |
| `*.md` | `docs/a.md` | no |
| `**/*.md` | `a.md` | yes |
| `**/BUILD/**` | `app/build/x` | yes (case-insensitive) |

Model routing: with `--models kit` and the claude-code and opencode adapters, Claude's
`/write-tests` runs on Opus at high effort, while OpenCode's subagents get no model (the tool
decides). With `--models tool`, no generated file contains `model` or `effort`.

## Out of scope

Validating every profile key's type beyond R001-12. Unknown keys are ignored.

## Additions beyond plan.bkp

- `AGENTKIT_ROOT` (R001-01): the launcher sets it so hooks work from any subdirectory.
- `test_cmd_windows` / `test_one_cmd_windows`, `test_globs`, `output_filter_regex`, `ci_setup`.
- Model routing modes `tool` / `kit` with kit-shipped tier maps, no manual model names (R001-17 to
  R001-23; owner's decision, 2026-10-03).
- Case-insensitive globs (R001-15).
- The `[ci]` table (R001-20), following the owner's decision that each project chooses its CI
  environments.

## Open questions

None. (Decided 2026-10-03: the owner picks `--models tool|kit` at install and never types model names.)
