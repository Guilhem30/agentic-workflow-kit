# Implementation review: spec 008 (codemap), passes 1-2

Reviewer: impl-reviewer subagent (roles/impl-reviewer.md, standard tier), recorded by the main
session because the role is read-only. 18 frozen tests pass; no test gaming.

Pass 1 findings and resolutions:
- HIGH a directory was split when path sorting interleaved a subdirectory (a/b.py, a/b/c.py,
  a/bz.py). Fixed: sorted by (dirname, path), one heading per directory.
- HIGH the map listed itself when its path matched source_globs, so --check never settled.
  Fixed: the configured map path is excluded (case-insensitive, `/`-normalised).
- LOW zero-group regexes use the whole match. Documented.
- LOW stray colon in the CLI message. Fixed.
Checked fine: non-participating groups skipped, non-UTF-8 decoded with replace, LF bytes, the
no-git fallback, .agentkit/ exclusion, R008-11, symbol order across regexes, the contract.

Pass 2: all fixes verified.

verdict: approve
