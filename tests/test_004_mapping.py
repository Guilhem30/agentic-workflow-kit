"""Spec 004: tool calls to neutral actions (R004-03 to R004-09)."""
from __future__ import annotations

import unittest

from agentkit.payloads import FORMATS
from agentkit.payloads.common import actions_for, patch_paths
from tests.hook_fixtures import ReadAction, ShellAction, WriteAction, normalize

SHELL_TOOLS = ("bash", "powershell", "shell", "exec_command", "local_shell", "run_shell_command",
               "terminal", "run_terminal_cmd", "execute_command", "unified_exec", "sh")
PATCH_TOOLS = ("apply_patch", "patch", "applypatch")
PATCH_KEYS = ("patch", "patchText", "patch_text", "input", "command", "diff", "content")
WRITE_TOOLS = ("edit", "write", "multiedit", "notebookedit", "str_replace_editor",
               "str_replace_based_edit_tool", "create_file", "edit_file", "write_file", "replace",
               "insert", "delete_file", "move_file", "rename_file")
WRITE_WORDS = ("write", "edit", "create", "delete", "remove", "move", "rename", "replace")
READ_TOOLS = ("read", "view", "read_file", "cat", "open_file")
PATH_KEYS = ("file_path", "filePath", "path", "notebook_path", "notebookPath", "target_file",
             "filename", "file")
LIST_KEYS = ("paths", "files", "file_paths", "filePaths")
DEST_KEYS = ("destination", "new_path", "newPath", "to", "target")

CODEX_PATCH = """*** Begin Patch
*** Add File: app/src/main/New.kt
+class New
*** Update File: app/src/main/Foo.kt
@@
-class Foo
+class Foo2
*** Move to: app/src/main/Bar.kt
*** Delete File: docs/notes.md
*** End Patch
"""
CODEX_PATHS = {"app/src/main/New.kt", "app/src/main/Foo.kt", "app/src/main/Bar.kt",
               "docs/notes.md"}

UNIFIED_DIFF = """diff --git a/app/src/main/Foo.kt b/app/src/main/Foo.kt
--- a/app/src/main/Foo.kt
+++ b/app/src/main/Foo.kt
@@ -1 +1 @@
-class Foo
+class Foo2
--- /dev/null
+++ b/docs/added.md
@@ -0,0 +1 @@
+new
--- a/docs/gone.md
+++ /dev/null
@@ -1 +0,0 @@
-old
"""
UNIFIED_PATHS = {"app/src/main/Foo.kt", "docs/added.md", "docs/gone.md"}


class ToolNameTests(unittest.TestCase):

    def test_R004_03_tool_name_is_case_insensitive(self):
        for name in ("Bash", "BASH", "bash", "bAsH"):
            with self.subTest(name=name):
                self.assertEqual(normalize(actions_for(name, {"command": "ls"})), {"shell": {"ls"}})
        for name in ("Edit", "EDIT", "MultiEdit", "NotebookEdit", "Write"):
            with self.subTest(name=name):
                self.assertEqual(normalize(actions_for(name, {"file_path": "a.txt"})),
                                 {"write": {"a.txt"}})
        self.assertEqual(normalize(actions_for("Read", {"file_path": "a.txt"})),
                         {"read": {"a.txt"}})

    def test_R004_03_mcp_prefix_is_stripped_to_last_segment(self):
        self.assertEqual(normalize(actions_for("mcp__fs__write_file", {"path": "a.txt"})),
                         {"write": {"a.txt"}})
        self.assertEqual(normalize(actions_for("mcp__filesystem__read_file", {"path": "a.txt"})),
                         {"read": {"a.txt"}})
        self.assertEqual(normalize(actions_for("mcp__term__Bash", {"command": "ls"})),
                         {"shell": {"ls"}})
        self.assertEqual(normalize(actions_for("MCP__Desktop__Commander__Edit_File",
                                               {"path": "a.txt"})), {"write": {"a.txt"}})

    def test_R004_03_prefix_only_counts_for_mcp(self):
        # "foo__bash" is not an MCP name: it is an unknown tool, so no shell action.
        self.assertEqual(normalize(actions_for("foo__bash", {"command": "ls"})), {})


class ShellToolTests(unittest.TestCase):

    def test_R004_04_every_shell_tool_gives_a_shell_action(self):
        for name in SHELL_TOOLS:
            with self.subTest(name=name):
                actions = actions_for(name, {"command": "ls -la"})
                self.assertEqual(normalize(actions), {"shell": {"ls -la"}})
                self.assertTrue(all(isinstance(a, ShellAction) for a in actions))

    def test_R004_04_command_list_is_joined_with_spaces(self):
        actions = actions_for("shell", {"command": ["bash", "-lc", "echo hi"]})
        self.assertEqual(normalize(actions), {"shell": {"bash -lc echo hi"}})

    def test_R004_04_cmd_and_script_keys(self):
        self.assertEqual(normalize(actions_for("exec_command", {"cmd": "pwd"})),
                         {"shell": {"pwd"}})
        self.assertEqual(normalize(actions_for("powershell", {"script": "Get-ChildItem"})),
                         {"shell": {"Get-ChildItem"}})

    def test_R004_04_shell_tool_without_command_has_no_shell_action(self):
        self.assertEqual(normalize(actions_for("bash", {"description": "nothing"})), {})


class PatchTests(unittest.TestCase):

    def test_R004_05_patch_paths_reads_codex_headers(self):
        self.assertEqual(set(patch_paths(CODEX_PATCH)), CODEX_PATHS)

    def test_R004_05_patch_paths_strips_whitespace_around_the_path(self):
        text = "*** Begin Patch\n*** Update File:   app/src/main/Foo.kt  \n*** End Patch\n"
        self.assertEqual(set(patch_paths(text)), {"app/src/main/Foo.kt"})

    def test_R004_05_patch_paths_falls_back_to_unified_diff(self):
        self.assertEqual(set(patch_paths(UNIFIED_DIFF)), UNIFIED_PATHS)
        self.assertNotIn("/dev/null", patch_paths(UNIFIED_DIFF))

    def test_R004_05_unified_diff_only_when_no_codex_headers(self):
        text = CODEX_PATCH + "--- a/other/x.txt\n+++ b/other/x.txt\n"
        self.assertEqual(set(patch_paths(text)), CODEX_PATHS)

    def test_R004_05_no_paths_in_plain_text(self):
        self.assertEqual(patch_paths(""), [])
        self.assertEqual(patch_paths("just some words\n"), [])

    def test_R004_05_patch_tools_read_every_patch_key(self):
        for name in PATCH_TOOLS:
            for key in PATCH_KEYS:
                with self.subTest(name=name, key=key):
                    actions = actions_for(name, {key: CODEX_PATCH})
                    self.assertEqual(normalize(actions).get("write"), CODEX_PATHS)
                    self.assertNotIn("read", normalize(actions))

    def test_R004_05_patch_tool_with_unified_diff(self):
        self.assertEqual(normalize(actions_for("apply_patch", {"diff": UNIFIED_DIFF})),
                         {"write": UNIFIED_PATHS})

    def test_R004_05_codex_apply_patch_payload(self):
        actions, _ = FORMATS["codex"].parse(
            {"tool_name": "apply_patch", "tool_input": {"command": CODEX_PATCH}})
        self.assertEqual(normalize(actions).get("write"), CODEX_PATHS)

    def test_R004_06_shell_heredoc_patch_also_writes(self):
        command = "apply_patch <<'EOF'\n" + CODEX_PATCH + "EOF\n"
        result = normalize(actions_for("bash", {"command": command}))
        self.assertEqual(result["write"], CODEX_PATHS)
        self.assertEqual(result["shell"], {command})

    def test_R004_06_shell_without_patch_has_no_write_action(self):
        actions = actions_for("bash", {"command": "echo '*** Update File: x' > /dev/null"})
        self.assertFalse(any(isinstance(a, WriteAction) for a in actions))


class WriteToolTests(unittest.TestCase):

    def test_R004_07_every_write_tool_gives_a_write_action(self):
        for name in WRITE_TOOLS:
            with self.subTest(name=name):
                actions = actions_for(name, {"file_path": "src/a.py"})
                self.assertEqual(normalize(actions), {"write": {"src/a.py"}})

    def test_R004_07_names_containing_a_write_word(self):
        for word in WRITE_WORDS:
            name = f"my_{word}_thing"
            with self.subTest(name=name):
                self.assertEqual(normalize(actions_for(name, {"path": "src/a.py"})),
                                 {"write": {"src/a.py"}})
        for name in ("createDirectory", "rewriteSymbol", "SearchAndReplace", "removeFiles"):
            with self.subTest(name=name):
                self.assertEqual(normalize(actions_for(name, {"path": "src/a.py"})),
                                 {"write": {"src/a.py"}})

    def test_R004_07_every_single_path_key(self):
        for key in PATH_KEYS:
            with self.subTest(key=key):
                self.assertEqual(normalize(actions_for("edit", {key: "src/a.py"})),
                                 {"write": {"src/a.py"}})

    def test_R004_07_list_keys(self):
        for key in LIST_KEYS:
            with self.subTest(key=key):
                self.assertEqual(normalize(actions_for("write", {key: ["a.py", "b/c.py"]})),
                                 {"write": {"a.py", "b/c.py"}})

    def test_R004_07_edits_entries(self):
        for key in PATH_KEYS:
            with self.subTest(key=key):
                tool_input = {"edits": [{key: "a.py", "old_string": "x"}, {key: "b.py"}]}
                self.assertEqual(normalize(actions_for("multiedit", tool_input)),
                                 {"write": {"a.py", "b.py"}})

    def test_R004_07_destination_keys(self):
        for key in DEST_KEYS:
            with self.subTest(key=key):
                self.assertEqual(normalize(actions_for("move_file", {"path": "a.py", key: "b.py"})),
                                 {"write": {"a.py", "b.py"}})

    def test_R004_07_all_keys_together(self):
        tool_input = {"file_path": "a", "paths": ["b", "c"], "edits": [{"filePath": "d"}],
                      "new_path": "e", "old_string": "not a path"}
        self.assertEqual(normalize(actions_for("edit", tool_input)),
                         {"write": {"a", "b", "c", "d", "e"}})

    def test_R004_07_claude_notebook_and_multiedit_payloads(self):
        fmt = FORMATS["claude"]
        actions, _ = fmt.parse({"tool_name": "NotebookEdit",
                                "tool_input": {"notebook_path": "nb/a.ipynb", "new_source": "x"}})
        self.assertEqual(normalize(actions), {"write": {"nb/a.ipynb"}})
        actions, _ = fmt.parse({"tool_name": "MultiEdit",
                                "tool_input": {"file_path": "a.py",
                                               "edits": [{"old_string": "x", "new_string": "y"}]}})
        self.assertEqual(normalize(actions), {"write": {"a.py"}})


class ReadAndOtherToolTests(unittest.TestCase):

    def test_R004_08_every_read_tool_gives_a_read_action(self):
        for name in READ_TOOLS:
            for key in PATH_KEYS:
                with self.subTest(name=name, key=key):
                    actions = actions_for(name, {key: "src/a.py"})
                    self.assertEqual(normalize(actions), {"read": {"src/a.py"}})
                    self.assertTrue(all(isinstance(a, ReadAction) for a in actions))

    def test_R004_08_read_tool_list_keys(self):
        self.assertEqual(normalize(actions_for("read", {"paths": ["a", "b"]})),
                         {"read": {"a", "b"}})

    def test_R004_09_other_tools_produce_no_action(self):
        for name, tool_input in (("glob", {"pattern": "**/*.py", "path": "src"}),
                                 ("grep", {"pattern": "x", "path": "src"}),
                                 ("WebFetch", {"url": "https://example.invalid"}),
                                 ("list_dir", {"path": "src"}),
                                 ("dsh_tool", {"command": "rm -rf src"})):
            with self.subTest(name=name):
                self.assertEqual(actions_for(name, tool_input), [])

    def test_R004_09_other_tool_with_a_patch_command_writes(self):
        result = normalize(actions_for("dsh_tool", {"command": CODEX_PATCH}))
        self.assertEqual(result, {"write": CODEX_PATHS})

    def test_R004_09_dsh_command_only_payload(self):
        actions, _ = FORMATS["dsh"].parse({"tool_name": "dsh_tool",
                                           "tool_input": {"command": CODEX_PATCH}})
        self.assertEqual(normalize(actions), {"write": CODEX_PATHS})


class ParseTests(unittest.TestCase):

    def test_R004_03_claude_shaped_parse_reads_tool_input_and_cwd(self):
        for name in ("claude", "codex", "dsh"):
            with self.subTest(fmt=name):
                actions, cwd = FORMATS[name].parse(
                    {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": "/w",
                     "session_id": "s"})
                self.assertEqual(normalize(actions), {"shell": {"ls"}})
                self.assertEqual(cwd, "/w")

    def test_R004_03_parse_without_tool_or_cwd(self):
        for name in FORMATS:
            with self.subTest(fmt=name):
                actions, cwd = FORMATS[name].parse({})
                self.assertEqual(actions, [])
                self.assertIsNone(cwd)

    def test_R004_13_plugin_parse_reads_tool_args_cwd(self):
        for name in ("opencode", "pi"):
            with self.subTest(fmt=name):
                actions, cwd = FORMATS[name].parse(
                    {"tool": "edit", "args": {"filePath": "src/a.py"}, "cwd": "/w"})
                self.assertEqual(normalize(actions), {"write": {"src/a.py"}})
                self.assertEqual(cwd, "/w")


if __name__ == "__main__":
    unittest.main()
