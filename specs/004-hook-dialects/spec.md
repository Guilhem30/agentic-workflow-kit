---
id: "004"
title: Hook dialects, end-of-turn verify and session-start status
status: approved
depends: ["003", "006"]
---

# 004 Hook dialects

## Context

Each agent tool sends its own hook payload and expects its own response. A dialect turns a
payload into neutral actions (003) and renders the guard's decision, the end-of-turn verify
result and the session-start status in the tool's format. The plan requires conformance tests:
recorded payloads per tool, fed to `guard`, with the expected decision checked.

## Facts verified against official docs on 2026-10-03

| Tool | Pre-tool input | Pre-tool response | End of turn | Session start |
|---|---|---|---|---|
| Claude Code ([hooks](https://code.claude.com/docs/en/hooks)) | `{tool_name, tool_input, cwd, …}`. Bash: `command`. Edit/Write: `file_path`. MultiEdit: `edits[].file_path`. NotebookEdit: `notebook_path` | `hookSpecificOutput.permissionDecision` = `allow`/`deny`/`ask`, plus `permissionDecisionReason`; exit 2 also blocks | Stop: `{"decision":"block","reason"}`, or top-level `systemMessage` for a warning | stdout or `additionalContext` |
| Codex CLI ([hooks](https://learn.chatgpt.com/docs/hooks)) | Bash and `apply_patch` both carry `tool_input.command` (for `apply_patch` it is the patch text) | Same JSON as Claude. `ask` is "parsed but not supported yet" | Stop input has `stop_hook_active`; output `{"decision":"block","reason"}` | stdout or `additionalContext` |
| DeepSeek Harness (`dsh-hooks-codex` README) | Codex-shaped, but **only `tool_input: {command}`** for every tool. File-edit arguments are not exposed | deny only | Stop: block and reason | context |
| OpenCode ([plugins](https://opencode.ai/docs/plugins/)) | `tool.execute.before(input{tool}, output{args})`; args such as `filePath`, `command` | throw an Error to block | `session.idle` event | none |
| Pi (`docs/extensions.md`) | `pi.on("tool_call")` with `event.toolName` and input | return `{block: true, reason}`; `ctx.ui.confirm` can ask | `agent_end` event; `pi.sendUserMessage` | none |

The OpenCode and Pi plugins are written by us (014, 016), so they speak the **plugin protocol**
defined below.

## Requirements (EARS)

### Commands
- **R004-01** `agentkit guard --format F`, `agentkit verify --format F` and
  `agentkit status --format F` shall accept F in {`claude`, `codex`, `dsh`, `opencode`, `pi`}.
  An unknown F exits 2.
- **R004-02** These commands shall read one JSON payload from stdin. An empty, non-JSON or
  non-object payload is treated as `{}`.

### Mapping tool calls to actions
- **R004-03** The tool name shall be compared case-insensitively, after stripping any `mcp__…__`
  prefix down to its last segment.
- **R004-04** Shell tools (`bash`, `powershell`, `shell`, `exec_command`, `local_shell`,
  `run_shell_command`, `terminal`, `run_terminal_cmd`, `execute_command`, `unified_exec`, `sh`)
  shall produce a ShellAction from `command` (a string, or a list joined with spaces), `cmd` or
  `script`.
- **R004-05** Patch tools (`apply_patch`, `patch`, `applypatch`) shall produce a WriteAction
  with every path named by `*** Add File:`, `*** Update File:`, `*** Delete File:` and
  `*** Move to:` lines, read from `patch`, `patchText`, `patch_text`, `input`, `command`, `diff`
  or `content`. Where there are none, the paths come from unified-diff `---`/`+++` headers
  (stripping `a/` and `b/`, ignoring `/dev/null`).
- **R004-06** A ShellAction whose command contains `*** Begin Patch` shall also produce a
  WriteAction for the paths in the patch.
- **R004-07** Write tools (`edit`, `write`, `multiedit`, `notebookedit`, `str_replace_editor`,
  `str_replace_based_edit_tool`, `create_file`, `edit_file`, `write_file`, `replace`, `insert`,
  `delete_file`, `move_file`, `rename_file`), and any tool whose name contains `write`, `edit`,
  `create`, `delete`, `remove`, `move`, `rename` or `replace`, shall produce a WriteAction with
  the paths in `file_path`, `filePath`, `path`, `notebook_path`, `notebookPath`, `target_file`,
  `filename`, `file`, `paths`/`files`/`file_paths`/`filePaths` (lists), `edits[].<path keys>`
  and `destination`/`new_path`/`newPath`/`to`/`target`.
- **R004-08** Read tools (`read`, `view`, `read_file`, `cat`, `open_file`) shall produce a
  ReadAction with the same path keys.
- **R004-09** Any other tool shall produce no action, except that a `command` containing
  `*** Begin Patch` produces a WriteAction. This is how the DeepSeek bridge's `{command}`-only
  payloads are handled.

### Pre-tool responses
- **R004-10** For `claude`, an allow decision shall produce no output and exit 0, so that the
  user's own permission prompts are never bypassed.
- **R004-11** For `claude`, ask and deny shall print
  `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":<verdict>,"permissionDecisionReason":"agentkit: <reason>"}}`
  and exit 0.
- **R004-12** For `codex` and `dsh`, deny shall be printed as in R004-11. Ask shall be turned into
  deny, with the reason prefixed by `needs the human's approval (ask them to make this change): `.
  Allow produces no output.
- **R004-13** Plugin protocol (`opencode`, `pi`): the input is `{"tool": str, "args": object, "cwd": str}`.
  The output is always `{"decision": "allow"|"ask"|"deny", "reason": str}` with exit 0.
- **R004-14** For `opencode`, ask shall be turned into deny as in R004-12. For `pi`, ask is kept.

### End-of-turn verify
- **R004-15** `verify --format F` shall run `lock verify` (002). Its problems are each violated
  file, plus a hint line about `lock restore` or asking the owner.
- **R004-16** For `claude`, `codex` and `dsh`, when there are problems and the payload's
  `stop_hook_active` is not true, verify shall print `{"decision":"block","reason":<problems>}`.
- **R004-17** For `claude`, when there are problems and `stop_hook_active` is true, verify shall
  print `{"systemMessage": <problems>}` instead of blocking again, so there is no endless loop.
  For `codex` and `dsh` it prints nothing.
- **R004-18** For the plugin protocol, verify shall print `{"ok": bool, "message": str}`.
- **R004-19** `verify` without `--format` shall print the problems or `verify: OK`, and exit 1
  or 0.

### Session-start status
- **R004-20** For `claude` and `codex`, `status --format F` shall print
  `{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":<status lines>}}`.
  For the plugin protocol it prints `{"context": <status lines>}`.

### Conformance fixtures
- **R004-21** The kit shall contain recorded payloads under `tests/fixtures/payloads/<tool>/`,
  each with its expected verdict. For each tool they cover at least: an allowed edit, a denied
  edit of a frozen file, a denied shell write, an allowed read-only shell command, and (for
  Codex) an `apply_patch` touching a frozen file.

## Public API contract

```text
agentkit/payloads/__init__.py: FORMATS: dict[str, HookFormat]; get_format(name) -> HookFormat
agentkit/payloads/common.py: actions_for(tool_name: str, tool_input) -> list[Action]
                             patch_paths(text: str) -> list[str]
agentkit/payloads/base.py:
  @dataclass Response(stdout: str = "", stderr: str = "", code: int = 0)
  class HookFormat: name; supports_ask
      parse(payload: dict) -> (list[Action], cwd: str | None)
      pre_response(decision) -> Response
      stop_response(payload: dict, problems: list[str]) -> Response
      session_response(text: str) -> Response
  class PluginFormat(HookFormat)
modules claude.py, codex.py, dsh.py, opencode.py, pi.py each export FORMAT
```

## Out of scope

Live end-to-end runs inside each tool. These are optional manual checks (019).

## Additions beyond plan.md

- Facts the plan did not have: Codex `ask` is unsupported, so it becomes deny; the DeepSeek bridge
  exposes only `{command}`, so frozen-file edits there are caught by Stop verify, not by the guard.
- The plugin protocol for OpenCode and Pi (R004-13).
- The anti-loop rule (R004-17).
- `status --format` for session-start hooks.

## Open questions

1. The DeepSeek gap: should we also write a native DeepSeek plugin (Cordis) so that file edits are
   guarded too? That is extra scope; this draft documents the limitation instead (015).
