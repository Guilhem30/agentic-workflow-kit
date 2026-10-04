# 000 kit-vision: progress

History is in git (`git log -- specs/000-kit-vision/`).

- 2026-10-04: tests written, phase `tests-draft`. Audit: pass 1 changes needed (B1 fixed),
  pass 2 `verdict: ready to freeze` (reviews kept outside the repo).
- Tests: `tests/test_000_portability.py` (R000-01, -02, -03), `tests/test_000_cli.py` (R000-04,
  -08, -09), `tests/test_000_text_files.py` (R000-07); helpers in `tests/process_fixtures.py`
  (no IDs: frozen by path). Trace 7/7.
- Red: stubs of 010 (install, update, sync), 018 (pre-commit, check-commit-msg), 021
  (autopilot); missing `hint: ` lines in codemap --check, lint-instructions, trace; raw
  `last-test.log` (needs UTF-8 + LF). 000 can only go `done` after 010, 018 and 021.
- Owner decisions open: H1 (add `* text=auto eol=lf` to the kit, or 010 normalises copied files;
  else `test_R000_07_installed_files` fails on Windows checkouts); R000-09 "hint" is tested as
  one `hint: ` line (worth writing into the spec); R000-07 vs R005-06 keeping CRLF.

**Next:** owner reviews the tests -> tests-approved -> owner `/freeze 000`; implement the
000-only parts (hints, log normalisation) any time after; the rest lands with 010/018/021.
