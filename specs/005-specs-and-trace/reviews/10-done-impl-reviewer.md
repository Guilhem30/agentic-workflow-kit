# Implementation review: spec 005 (specs-and-trace), pass 4, commit 0d3a43f

## Diff

`git diff ab00fb8 0d3a43f` changes only `agentkit/specs.py`, `new_spec`, 3 lines:
- The title check adds `"Cs"` to the rejected Unicode categories (`agentkit/specs.py:230`).
- Each template is encoded with `text.encode("utf-8")` while rendering (`:239`), before `mkdir` (`:242`). The write loop (`:245-246`) writes the prepared bytes.

No test, spec or lock file changed, and the working tree is clean.

## Runs

- The five 005 modules: 81 tests, OK.
- The full suite (`discover -s tests -t .`): 542 tests, errors=16, skipped=1. All 16 errors are in `tests.test_020_guard_status` (the 006 stub). This is unchanged from pass 3.

## P1 re-verified

In a fresh scratch repository, `new-spec 032 s --title "$(printf 'caf\xe9')"` now exits 1 with "the title must be a single line without control characters", and `specs/` stays empty. Then `new-spec 032 s --title 'Données ✓'` exits 0 and creates the four files with the title intact. Because encoding now happens before `mkdir`, no encoding failure can leave a folder behind, even if the category check ever missed one.

## Findings

### HIGH
None.

### MEDIUM
None.

### LOW
- In the write loop at `agentkit/specs.py:245`, the variable `text` now holds bytes. Renaming it (for example to `data`) would make that clearer. This is cosmetic.
- P2 (rejecting `Cf` blocks the emoji ZWJ and the soft hyphen), P3 (a lone `\r` in hand-edited front matter is read two ways) and P4 (N4, L2 and L7 leftovers, `[""]` from a bare `-`) remain LOW, as agreed.

## Open owner questions (flagged, not failed)

- R005-11: its own text contains the literal `[manual]`, so it counts as excluded.
- R005-19 and R005-20: the code uses the scoped reading.
- R005-18: "terminal" is implemented as "a dropped spec can never change status". The `lock freeze --force` guard stays with 002.

verdict: approve
