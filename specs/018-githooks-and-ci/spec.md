---
id: "018"
title: Git hooks and CI
status: approved
---

# 018 Git hooks and CI

## Context

The tool-neutral layers that hold for any agent and any human: a git pre-commit hook, a
commit-msg hook, and CI. With CODEOWNERS on GitHub, the owner must review changes to tests and
the lock.

## Requirements (EARS)

### pre-commit
- **R018-01** `.githooks/pre-commit` shall be a POSIX `sh` script. It uses the first of
  `python3`, `python` and `py` that runs Python 3.11 or later, then runs
  `.agentkit/bin/agentkit pre-commit` from the repo top level.
- **R018-02** If no suitable Python is found, then the hook shall print a message and fail.
- **R018-03** `agentkit pre-commit` shall fail (exit 1) when any of these fails:
  - `lock verify --staged`;
  - `lock audit --base HEAD --staged`;
  - `lint-instructions`;
  - `sync --check`;
  - `codemap --check` (008).
- **R018-04** On failure, pre-commit shall list every problem, then a line saying that
  `--no-verify` is forbidden and that frozen tests change only through the owner's
  `lock unfreeze`.

### commit-msg
- **R018-05** `.githooks/commit-msg` shall run `agentkit check-commit-msg <file>` the same way.
- **R018-06** check-commit-msg shall accept a first non-comment line that matches
  `<type>(<scope>)?!?: <subject>`, with type one of
  `feat fix docs style refactor perf test build ci chore revert spec`. It also accepts lines
  starting `Merge `, `Revert "`, `fixup! `, `squash! ` and `amend! `. Anything else exits 1 with
  an example.

### CI
- **R018-11** CI files shall be rendered only for the providers in `[ci] providers`. Several
  providers may be enabled at once.
- **R018-12** The GitHub workflow shall run its job as a matrix over `[ci] os`, using
  `ubuntu-latest`, `windows-latest` and `macos-latest`, with `fail-fast: false`, so that every
  environment runs in parallel and reports separately.
- **R018-13** The GitLab template shall define one job per OS in `[ci] os`, all in the same stage
  so that they run in parallel. Each non-Linux job is tagged with `[ci.gitlab_tags].<os>`,
  defaulting to GitLab's hosted runners (`saas-windows-medium-amd64`, `saas-macos-medium-m1`).
- **R018-14** CI steps shall call `python .agentkit/bin/agentkit …`, which works on all three OSes
  after the Python setup step. The profile's `ci_setup` steps shall work on every OS they are
  used on, or the profile shall document which OSes it supports.
- **R018-07** The GitHub Actions workflow (`.github/workflows/agentkit.yml`) shall, on push and
  pull request, for each OS:
  1. check out the full history;
  2. set up Python 3.12;
  3. run the profile's `ci_setup` steps;
  4. run `lock verify`;
  5. on pull requests only, run `lock audit --base origin/<base branch>`;
  6. run `sync --check`, `codemap --check`, `lint-instructions`, `trace` and `test`.
- **R018-08** The GitLab template (`.gitlab/agentkit.gitlab-ci.yml`, meant to be included) shall
  run the same checks. On merge requests, the audit base is `origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME`.
- **R018-09** Rendered CI files shall keep the CI system's own `${{ … }}` and `$VAR` expressions
  intact (R010 rendering).
- **R018-10** The CODEOWNERS block (R010-10) shall be documented in the README as the way to
  require the owner's review on GitHub. [manual]

## Public API contract

The kit files are `githooks/pre-commit`, `githooks/commit-msg`, `ci/github-actions.yml` and
`ci/gitlab-ci.yml`. The CLI commands are `agentkit pre-commit` and
`agentkit check-commit-msg FILE`.

## Examples and edge cases

- `feat(004): rule engine priorities` passes. `test(004): freeze tests` passes. `wip` fails.
- A commit that stages a modified frozen file, while the worktree copy is restored, still fails
  (R018-03 checks the index).

## Additions beyond plan.md

- The `spec` commit type. Running `sync --check` in pre-commit (the plan had it in CI only).
- The `--staged` checks.
- CI providers and operating systems are chosen per project at install time and run in parallel
  (R018-11 to R018-14). Owner's decision, 2026-10-03.

## Open questions

None.
