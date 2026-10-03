---
id: "003"
title: Guard (tool-neutral pre-tool decisions)
status: frozen
depends: ["001", "002"]
---

# 003 Guard

## Context

Every agent tool with pre-tool hooks calls `agentkit guard`. Hook payloads are first turned into
neutral actions (004), then the guard decides `allow`, `ask` or `deny`. This is an early
warning layer. The lock (002), end-of-turn verify (004), pre-commit and CI (018) are the
guarantee, so the shell analysis is best effort and favours few false positives on read-only
commands.

## Requirements (EARS)

### Actions and decisions
- **R003-01** The guard shall judge a list of neutral actions: `WriteAction(paths)`,
  `ReadAction(paths)` and `ShellAction(command)`.
- **R003-02** The decision shall be the most severe verdict over all actions (`deny` > `ask` >
  `allow`), with the de-duplicated reasons of every non-allow verdict.
- **R003-03** Every deny or ask reason shall name the path or command involved and say what to
  do instead: ask the owner, or run `agentkit lock restore`.

### Path classification
- **R003-04** Paths shall be resolved relative to the payload's working directory (default: the
  root) and turned into repo-relative paths. Paths outside the repository are ignored.
- **R003-05** On Windows, Git-Bash paths of the form `/c/...` shall be read as `C:/...`.
- **R003-06** The comparison of a path with frozen paths and protected globs shall be
  case-insensitive.
- **R003-07** A write to a frozen path shall be denied.
- **R003-08** A write to a path matching `.agentkit/state/**` (or `[guard] allow_globs`) shall
  be allowed, unless it is frozen.
- **R003-09** A write to the lock, the unfreeze log, `agentkit.toml`, `.agentkit/**` or
  `[guard] deny_globs` shall be denied. So shall a write to the chaos log or to
  `<paths.specs>/*/reviews/**`, whether chaos mode is on or off and whatever `[guard]
  allow_globs` says (R020-29); with a malformed `[chaos]` table the default log path is
  protected (R020-42).
- **R003-10** A write to an enforcement configuration file shall be `ask`. These are
  `.claude/settings.json`, `.codex/hooks.json`, `.codex/config.toml`, `.opencode/plugins/**`,
  `opencode.json`, `.pi/**`, `.githooks/**`, `.github/workflows/**`, `.gitlab-ci.yml`,
  `CODEOWNERS`, `.github/CODEOWNERS`, and `[guard] ask_globs`.
- **R003-11** Where `[guard] deny_build_output_reads` is true (the default), a read of a path
  matching the profile's `build_output_globs` shall be denied, with a hint to use
  `agentkit test`.
- **R003-12** Reads of any other path, including frozen files, shall be allowed.

### Shell analysis
- **R003-13** A command containing `agentkit` and either `lock unfreeze`, or `lock freeze`
  together with `--force`, or the consecutive tokens `chaos clear` (R020-30), shall be denied.
- **R003-14** A `git commit`, `push`, `merge`, `rebase`, `am`, `cherry-pick` or `revert` with
  `--no-verify` shall be denied, and so shall `git commit` with `-n` in a short-flag cluster.
- **R003-15** A git command that mentions `core.hooksPath`, and `git update-index` with
  `--assume-unchanged` or `--skip-worktree`, shall be denied.
- **R003-16** The command shall be split into segments at `;`, `&&`, `||`, `|`, `&`, newlines and
  parentheses. Leading `VAR=value` assignments and the prefix words `sudo`, `env`, `command`,
  `builtin`, `exec`, `nohup`, `time` and `xargs` shall be skipped.
- **R003-17** A `cd DIR`, `pushd DIR` or `Set-Location DIR` segment shall change the working
  directory used to resolve later segments. `popd` restores the previous one. Every write
  argument is resolved against the tracked directory and compared, as a repo-relative path, with
  the frozen paths.
- **R003-32** When the tracked directory becomes unknown (the target contains `$`, `%`, `~`,
  backquotes or `$(`, or is `cd -`), the working directory shall be marked unknown for the
  following segments of that command.
- **R003-18** The target of an output redirection (`>`, `>>`, `>|`, `&>`, `N>`) shall be
  classified as a write. `/dev/null`, `NUL` and `$null` are ignored.
- **R003-19** For a write command, each non-flag argument (and the value part of `--opt=value`)
  shall be classified as a write. Write commands are: POSIX `rm rmdir mv cp tee truncate dd
  touch ln install unlink shred chmod chown patch`; cmd.exe `del erase rd ren rename move copy
  xcopy robocopy`; PowerShell `Set-Content Add-Content Out-File Remove-Item Move-Item Copy-Item
  New-Item Clear-Content Rename-Item` and their aliases `sc ac ri mi cpi ni rni clc`; `sed` or
  `perl` with an in-place flag; `find` with `-delete`, `-exec` or `-execdir`.
- **R003-20** For `git checkout`, `restore`, `rm`, `mv`, `apply`, `am` and `update-index`, each
  path argument shall be classified as a write.
- **R003-21** An interpreter (`python`, `python3`, `py`, `node`, `deno`, `bun`, `ruby`, `perl`,
  `php`, `pwsh`, `powershell`, `bash`, `sh`, `zsh`) run with an inline script (`-c`, `-e`,
  `-Command`, `--eval`, `-r`) that mentions a frozen path, a frozen file's basename (more than
  4 characters), the lock, the unfreeze log, the chaos log or a path under
  `<paths.specs>/*/reviews/` shall be denied.
- **R003-22** A write argument containing `*`, `?` or `[` shall be denied when the glob matches
  a frozen path.
- **R003-23** A destructive command (`rm rmdir rd del erase Remove-Item ri mv move Move-Item mi
  shred`, `find -delete`, `git rm`, `git mv`) whose argument is a directory that contains a
  frozen file shall be denied.
- **R003-24** A write argument without `/` that equals the basename of a frozen file shall be
  denied **only while the working directory is unknown** (R003-32). When the directory is known,
  only the resolved repo-relative path counts, so `rm FooTest.kt` in an unrelated folder is
  allowed.
- **R003-25** Read-only commands that mention frozen paths (for example `cat`, `grep`,
  `git diff`, `git log`) shall be allowed.
- **R003-26** Command text shall be tokenised with POSIX quoting rules after replacing `\` with
  `/`. If tokenisation fails (unbalanced quotes), the guard shall fall back to splitting on
  whitespace and operators.

### Robustness and performance
- **R003-27** If the guard hits an internal error after the payload was turned into actions, it
  shall switch to **degraded mode** (fail-closed for tests, fail-open for everything else; the
  owner's decision of 2026-10-03):
  - a WriteAction to a path matching the degraded globs (R003-29) or the lock, the unfreeze log,
    `agentkit.toml`, `.agentkit/**`, the default chaos log (`chaos-log.jsonl`, or the configured
    one when it can be read) or `<paths.specs>/*/reviews/**` is denied, with the reason
    `agentkit guard error (<message>): writes to test files are refused until the guard is fixed`;
  - every other action (other writes, reads, shell commands) is allowed, with
    `agentkit guard error (allowing): <message>` printed on stderr.
- **R003-29** In degraded mode, the globs shall be the profile's `frozen_globs` when the
  configuration and profile load. Otherwise they are the union of `frozen_globs` across every
  profile shipped with the kit. Degraded mode shall not depend on the lock file, the shell
  analysis or git.
- **R003-30** A degraded-mode deny shall be returned in the tool's normal deny format (004). A
  degraded-mode allow shall exit 1 with the message on stderr, which the tools treat as a
  non-blocking error.
- **R003-31** If the payload itself cannot be turned into actions, the guard shall allow, warning
  on stderr. There is nothing to classify.
- **R003-28** The guard shall decide within 300 ms for a repository with 5,000 files and 1,000
  frozen files, on a typical laptop, without running git.

## Public API contract

```text
agentkit/guard.py:
  ALLOW, ASK, DENY = "allow", "ask", "deny"
  @dataclass WriteAction(paths: list[str]); ReadAction(paths: list[str]); ShellAction(command: str)
  @dataclass Decision: verdict: str; reasons: list[str]; reason -> str (joined "; ")
  def evaluate(cfg, actions: list, cwd: str | None = None) -> Decision
```

## Examples and edge cases

Degraded mode (for example, `agentkit.toml` has a syntax error): Edit
`core/src/test/FooTest.kt` is denied, Edit `core/src/main/Foo.kt` is allowed with a warning,
`./gradlew test` is allowed with a warning.

| Frozen: `app/src/test/FooTest.kt` | Verdict |
|---|---|
| Write `app/src/test/FooTest.kt` | deny |
| Write `APP/SRC/TEST/FOOTEST.KT` | deny (R003-06) |
| Write `tests.lock.json` | deny |
| Write `.github/workflows/ci.yml` | ask |
| Write `.agentkit/state/last-test.log` | allow |
| Read `app/build/reports/x.html` | deny |
| `cat app/src/test/FooTest.kt` | allow |
| `echo x > app/src/test/FooTest.kt` | deny |
| `cd app/src/test && rm FooTest.kt` | deny |
| `cd tools && rm FooTest.kt` (no frozen `tools/FooTest.kt`) | allow |
| `cd $DIR && rm FooTest.kt` | deny (directory unknown, basename matches) |
| `rm -rf app/src` | deny (contains a frozen file) |
| `sed -i 's/a/b/' app/src/test/*.kt` | deny |
| `python -c "open('app/src/test/FooTest.kt','w')"` | deny |
| `git commit -nm "x"` | deny |
| `git commit -m "fix nothing"` | allow |
| `Remove-Item -Path app\src\test\FooTest.kt` | deny |
| `python .agentkit/bin/agentkit lock unfreeze x --reason y` | deny |

## Out of scope

- Degraded mode when the guard cannot start at all (for example, Python is missing) under Claude
  Code or Codex. Those tools treat a hook that fails to start as a non-blocking error, so the
  action goes through. End-of-turn verify cannot run either, so pre-commit and CI catch it. The
  OpenCode and Pi plugins handle this case themselves (R014-03, R016-03).

Full shell semantics: variables, command substitution, aliases, scripts written to disk and then
run. These are caught by end-of-turn verify and pre-commit.

## Additions beyond plan.md

- The `ask` verdict, for hook and CI configuration (the plan's "ask before edits to the guard,
  hooks and CI" moved from permissions into the guard so that every tool gets it).
- Denying build-output reads in the guard as well (the plan had it in permission config only),
  so that tools without permission config get it too.
- The detailed shell rules R003-14 to R003-26.
- Degraded mode R003-27 to R003-31 (owner's decision: fail-closed for test files only).
- The chaos log, the stored reviews and `chaos clear` in R003-09, R003-13, R003-21 and R003-27
  (020 amendment, approved by the owner on 2026-10-03).

## Open questions

None. (Decided 2026-10-03: resolve paths against the project root through the tracked working
directory, and use basename matching only when that directory cannot be known; R003-17,
R003-24, R003-32. This runs inside the hook, so it costs no tokens.)
