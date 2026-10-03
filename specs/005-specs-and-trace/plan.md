# 005 Specs and trace: plan

## Approach

Most of the surface already exists, because the bootstrap needed it for lock (002) and chaos
(020): `agentkit/specs.py` (phases, `Spec`, `list_specs`, `find_spec`, `set_status`,
`spec_requirements`), `agentkit/trace.py` (`trace_specs`, `format_results`, plus the private
`check_tree` and `_trace_command`) and the CLI commands `spec-status` and `trace`. This spec
adds the tests that pin all of it down, and the parts that are still missing:

- `specs.new_spec(cfg, spec_id, slug, title="")`. It validates the slug (R005-01). It refuses
  an existing number, including a number shared by two folders (R005-05, R005-19). When
  `spec_id` is None it picks the next free number (R005-17). It renders the four templates and
  returns the new folder.
- The templates `workflow/templates/{spec,plan,tasks,progress}.md`, read from the kit source
  (`config._kit_source()`; install copies `workflow/` into `.agentkit/`, R010-06). This spec
  adds minimal versions. 011 owns their final content (R011-03, R011-04).
- `agentkit new-spec [NNN] slug [--title T]`. It prints the number it chose. Errors exit 1.

Errors from `new_spec` raise a `ValueError` whose text names the problem; the CLI prints it and
exits 1. The tests only require an exception and an untouched tree.

## Files

- `agentkit/specs.py`, `agentkit/trace.py`, `agentkit/cli.py`
- `workflow/templates/spec.md`, `plan.md`, `tasks.md`, `progress.md`

## Test strategy

- `tests/test_005_folders.py`: R005-01 to R005-03, R005-18 to R005-20, `next_action`
- `tests/test_005_status.py`: R005-06 to R005-08, R005-18 transitions, CRLF and byte stability
- `tests/test_005_new_spec.py`: R005-04, R005-05, R005-17, R005-19
- `tests/test_005_reqids.py`: R005-09 to R005-11
- `tests/test_005_trace.py`: R005-12 to R005-16 and the spec's examples

Fixtures are `support.RepoTestCase` repositories. Other specs' IDs are built with `rid()`.
