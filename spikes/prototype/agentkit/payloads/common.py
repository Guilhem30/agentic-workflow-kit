"""Shared extraction of neutral actions from tool-call payloads."""

from __future__ import annotations

import re

from ..guard import ReadAction, ShellAction, WriteAction

SHELL_TOOLS = {
    "bash", "powershell", "shell", "exec_command", "local_shell", "run_shell_command",
    "terminal", "run_terminal_cmd", "execute_command", "unified_exec", "sh",
}
PATCH_TOOLS = {"apply_patch", "patch", "applypatch"}
WRITE_TOOLS = {
    "edit", "write", "multiedit", "notebookedit", "str_replace_editor", "str_replace_based_edit_tool",
    "create_file", "edit_file", "write_file", "replace", "insert", "delete_file", "move_file", "rename_file",
}
READ_TOOLS = {"read", "view", "read_file", "cat", "open_file"}
PATH_KEYS = ("file_path", "filePath", "path", "notebook_path", "notebookPath", "target_file", "filename", "file")
MULTI_PATH_KEYS = ("paths", "files", "file_paths", "filePaths")
PATCH_KEYS = ("patch", "patchText", "patch_text", "input", "command", "diff", "content")

_PATCH_FILE_RX = re.compile(r"^\*\*\* (?:Add File|Update File|Delete File|Move to):\s*(.+?)\s*$", re.MULTILINE)
_DIFF_FILE_RX = re.compile(r"^(?:\+\+\+|---) (?:[ab]/)?(.+?)(?:\t.*)?$", re.MULTILINE)


def patch_paths(text: str) -> list[str]:
    """Files touched by a Codex-style `*** Begin Patch` block or a unified diff."""
    if not isinstance(text, str):
        return []
    paths = _PATCH_FILE_RX.findall(text)
    if not paths and ("\n+++ " in text or text.startswith("--- ")):
        paths = [p for p in _DIFF_FILE_RX.findall(text) if p != "/dev/null"]
    out = []
    for p in paths:
        p = p.strip()
        if p and p not in out:
            out.append(p)
    return out


def _command_str(value) -> str:
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return value if isinstance(value, str) else ""


def _paths_from(inp: dict) -> list[str]:
    paths = []
    for k in PATH_KEYS:
        v = inp.get(k)
        if isinstance(v, str) and v:
            paths.append(v)
    for k in MULTI_PATH_KEYS:
        v = inp.get(k)
        if isinstance(v, list):
            paths.extend(x for x in v if isinstance(x, str))
    edits = inp.get("edits")
    if isinstance(edits, list):
        for e in edits:
            if isinstance(e, dict):
                for k in PATH_KEYS:
                    if isinstance(e.get(k), str):
                        paths.append(e[k])
    for k in ("destination", "new_path", "newPath", "to", "target"):
        if isinstance(inp.get(k), str):
            paths.append(inp[k])
    return paths


def actions_for(tool_name: str, tool_input) -> list:
    """Neutral actions for one tool call. Unknown read-only tools produce no action."""
    name = (tool_name or "").strip()
    key = name.casefold().rsplit("__", 1)[-1]  # mcp__server__tool -> tool
    inp = tool_input if isinstance(tool_input, dict) else {}
    if not isinstance(tool_input, dict) and isinstance(tool_input, str):
        inp = {"command": tool_input}
    actions: list = []
    if key in PATCH_TOOLS:
        for k in PATCH_KEYS:
            paths = patch_paths(_command_str(inp.get(k)))
            if paths:
                actions.append(WriteAction(paths))
                break
        else:
            # Patch text we cannot parse: treat every string argument as a possible patch.
            joined = "\n".join(str(v) for v in inp.values() if isinstance(v, str))
            if patch_paths(joined):
                actions.append(WriteAction(patch_paths(joined)))
        return actions
    if key in SHELL_TOOLS:
        cmd = _command_str(inp.get("command") or inp.get("cmd") or inp.get("script"))
        if cmd:
            actions.append(ShellAction(cmd))
            embedded = patch_paths(cmd) if "*** Begin Patch" in cmd else []
            if embedded:
                actions.append(WriteAction(embedded))
        return actions
    if key in READ_TOOLS:
        paths = _paths_from(inp)
        return [ReadAction(paths)] if paths else []
    if key in WRITE_TOOLS or re.search(r"(write|edit|create|delete|remove|move|rename|replace)", key):
        paths = _paths_from(inp)
        if paths:
            actions.append(WriteAction(paths))
        return actions
    # Bridges (e.g. DeepSeek Harness) may only expose `{command}` for every tool.
    cmd = _command_str(inp.get("command"))
    if cmd and "*** Begin Patch" in cmd:
        actions.append(WriteAction(patch_paths(cmd)))
    return actions
