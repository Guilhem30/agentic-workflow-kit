# Spec 004 implementation review (impl-reviewer, pass 2 on pass-1 findings + fix diff 7555d0a)

1 (blocking) fixed: with --format, ConfigError/LockError become stop_response problems or session_response text; exit 0.
2 fixed: _read_payload catches RecursionError.
3 fixed: _ASK_PREFIX is private.
4 fixed: _emit no longer captures stderr; skips response stderr when decision.degraded.
5 fixed: stdout written as UTF-8 bytes to sys.stdout.buffer (LF on Windows).
6 accepted: load_config() as the plan specifies; hooks run at the project root.
7 fixed: list-valued command joined with newlines for patch tools.

Full suite: 741 tests OK (1 skipped). No new blocking findings.

verdict: approve
