"""Tool calls to neutral actions (R004-03 to R004-09)."""
from __future__ import annotations

import re

from ..guard import ReadAction, ShellAction, WriteAction

_SHELL_TOOLS = {"bash", "powershell", "shell", "exec_command", "local_shell", "run_shell_command",
                "terminal", "run_terminal_cmd", "execute_command", "unified_exec", "sh"}
_PATCH_TOOLS = {"apply_patch", "patch", "applypatch"}
_WRITE_TOOLS = {"edit", "write", "multiedit", "notebookedit", "str_replace_editor",
                "str_replace_based_edit_tool", "create_file", "edit_file", "write_file", "replace",
                "insert", "delete_file", "move_file", "rename_file"}
_WRITE_WORDS = ("write", "edit", "create", "delete", "remove", "move", "rename", "replace")
_READ_TOOLS = {"read", "view", "read_file", "cat", "open_file"}

_SHELL_KEYS = ("command", "cmd", "script")
_PATCH_KEYS = ("patch", "patchText", "patch_text", "input", "command", "diff", "content")
_PATH_KEYS = ("file_path", "filePath", "path", "notebook_path", "notebookPath", "target_file",
              "filename", "file")
_LIST_KEYS = ("paths", "files", "file_paths", "filePaths")
_DEST_KEYS = ("destination", "new_path", "newPath", "to", "target")

_BEGIN_PATCH = "*** Begin Patch"
_PATCH_HEADER = re.compile(r"^\*\*\* (?:Add File|Update File|Delete File|Move to):[ \t]*(.*?)\s*$",
                           re.M)


def _tool(tool_name) -> str:
    """Lower case, an `mcp__server__tool` name cut to its last segment (R004-03)."""
    name = str(tool_name or "").strip().lower()
    if name.startswith("mcp__"):
        name = name.rsplit("__", 1)[-1]
    return name


def _dedupe(paths) -> list[str]:
    seen: dict[str, None] = {}
    for p in paths:
        if isinstance(p, str) and p.strip():
            seen.setdefault(p, None)
    return list(seen)


def _values(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [v for v in value if isinstance(v, str)]
    return []


def _paths(tool_input: dict) -> list[str]:
    """Every path named by the path keys of R004-07."""
    found: list[str] = []
    for key in (*_PATH_KEYS, *_LIST_KEYS, *_DEST_KEYS):
        found += _values(tool_input.get(key))
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for edit in edits:
            if isinstance(edit, dict):
                for key in _PATH_KEYS:
                    found += _values(edit.get(key))
    return _dedupe(found)


def _command(tool_input: dict) -> str | None:
    for key in _SHELL_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, (list, tuple)) and value:
            return " ".join(str(v) for v in value)
    return None


def _patch_write(text) -> list:
    """A WriteAction for a Codex patch embedded in `text` (R004-06, R004-09)."""
    if isinstance(text, str) and _BEGIN_PATCH in text:
        paths = patch_paths(text)
        if paths:
            return [WriteAction(paths)]
    return []


def patch_paths(text: str) -> list[str]:
    """Paths of a Codex patch, else of unified-diff headers (R004-05)."""
    if not isinstance(text, str):
        return []
    paths = _dedupe(m.group(1) for m in _PATCH_HEADER.finditer(text))
    if paths:
        return paths
    lines = text.splitlines()
    found: list[str] = []
    for old, new in zip(lines, lines[1:]):
        if old.startswith("--- ") and new.startswith("+++ "):
            for header in (old[4:], new[4:]):
                path = header.split("\t", 1)[0].strip()
                if path == "/dev/null" or not path:
                    continue
                if path.startswith(("a/", "b/")):
                    path = path[2:]
                found.append(path)
    return _dedupe(found)


def actions_for(tool_name: str, tool_input) -> list:
    """The neutral actions of one tool call (R004-03 to R004-09)."""
    name = _tool(tool_name)
    args = tool_input if isinstance(tool_input, dict) else {}
    if name in _SHELL_TOOLS:
        command = _command(args)
        if command is None:
            return []
        return [ShellAction(command), *_patch_write(command)]
    if name in _PATCH_TOOLS:
        paths: list[str] = []
        for key in _PATCH_KEYS:
            value = args.get(key)
            if isinstance(value, str):
                paths += patch_paths(value)
        paths = _dedupe(paths)
        return [WriteAction(paths)] if paths else []
    if name in _READ_TOOLS:
        paths = _paths(args)
        return [ReadAction(paths)] if paths else []
    if name in _WRITE_TOOLS or any(word in name for word in _WRITE_WORDS):
        paths = _paths(args)
        actions = [WriteAction(paths)] if paths else []
        return actions + _patch_write(args.get("command"))
    return _patch_write(args.get("command"))
