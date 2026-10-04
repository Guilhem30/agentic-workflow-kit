# 007 test-runner: plan

## Approach

`agentkit/runtests.py` per the contract. `subprocess.run(cmd, shell=True, cwd=root)` with stdout
and stderr merged; reports found with `os.walk` (pruning `.git`, `node_modules`, `.gradle`,
`.idea`) and `util.glob_match`; XML with `xml.etree.ElementTree`. The CLI only prints the lines.

## Test strategy

`tests/test_007_runtests.py`: a fake test command (`fake.py`, driven by `behave.json`) writes
JUnit reports and output in a fixture repo, so every path runs without a real toolchain.
