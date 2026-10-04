# 010 install-update-sync: progress

History is in git (`git log -- specs/010-install-update-sync/`).

## Tests phase (2026-10-04)

- Tests: `tests/test_010_install.py`, `test_010_managed.py`, `test_010_blocks.py`,
  `test_010_sync.py`; fixtures in `tests/install_fixtures.py` (a fixture kit run in a
  subprocess so `KIT_ROOT` is the fixture, and fake adapters for 012 to 016).
- Stubs: `agentkit/install.py`, `agentkit/adapters.py`, CLI `install` options, `update`, `sync`.
- 76 tests: 75 fail on the stubs, 3 skip on Windows (executable bit). The one that already
  passes, `test_R010_25_first_install_requires_models`, covers the R001-21 check that
  `cmd_install` already had.
- Audit: first audit `needs changes` (saved in `.autopilot/010-tests-audit-1.md`), all fixed;
  re-check `ready to freeze`.
- Spec amendments (owner, 2026-10-04): `Planned` semantics, `ci_os`/`models` in `install()`,
  list arguments, `Report` paths, `--python` stored as `[kit] python`, exit 2 on a missing kit
  source. R010-12 stays literal: a customised file conflicts even when the kit is unchanged.
- Consequence: the real kit cannot install until 018 ships `githooks/` and `ci/`.
- The owner is stored as `[kit] owner`, and `update` rebuilds CODEOWNERS from it (R010-10, owner's
  choice, 2026-10-04; 2 tests added after the re-check). 78 tests in all.
- Tests approved by the owner on 2026-10-04.

<!-- agentkit:snapshot:begin -->
- 2026-10-04 03:16 (UTC), phase `tests-approved`
- Tasks: 0/0 done
- Last `agentkit test`:
  FAIL (exit 1): python -m unittest discover -s tests -t .
  ERROR: test_R010_14_hash_markers (tests.test_010_blocks.TestMarkers.test_R010_14_hash_markers)
  ERROR: test_R010_14_markdown_markers (tests.test_010_blocks.TestMarkers.test_R010_14_markdown_markers)
  ERROR: test_R010_15_gitignore_region_replaced (tests.test_010_blocks.TestPlacement.test_R010_15_gitignore_region_replaced)
  ERROR: test_R010_15_markers_present_only_region_replaced (tests.test_010_blocks.TestPlacement.test_R010_15_markers_present_only_region_replaced)
  ERROR: test_R010_15_missing_file_gets_whole_template (tests.test_010_blocks.TestPlacement.test_R010_15_missing_file_gets_whole_template)
  ERROR: test_R010_15_missing_file_initial_written (tests.test_010_blocks.TestPlacement.test_R010_15_missing_file_initial_written)
  ERROR: test_R010_15_missing_file_without_initial_gets_markers_around_content (tests.test_010_blocks.TestPlacement.test_R010_15_missing_file_without_initial_gets_markers_around_content)
  ERROR: test_R010_15_no_markers_block_added_at_end (tests.test_010_blocks.TestPlacement.test_R010_15_no_markers_block_added_at_end)
- Branch `main`, 14 uncommitted change(s)

**Next:** owner runs /freeze 010; then /implement 010
<!-- agentkit:snapshot:end -->
