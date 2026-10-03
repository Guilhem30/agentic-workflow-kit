"""Spec 003: shell analysis (R003-13 to R003-26, R003-32) and the spec's example table."""
from __future__ import annotations

import unittest

from tests.guard_fixtures import ALLOW, ASK, DENY, FROZEN, GuardCase, ShellAction, WriteAction


class ExampleTableTests(GuardCase):
    """Every row of the spec's table (frozen: app/src/test/FooTest.kt)."""

    def test_R003_07_example_rows(self):
        rows = [
            (WriteAction([FROZEN]), DENY),
            (WriteAction([FROZEN.upper()]), DENY),
            (WriteAction(["tests.lock.json"]), DENY),
            (WriteAction([".github/workflows/ci.yml"]), ASK),
            (WriteAction([".agentkit/state/last-test.log"]), ALLOW),
            (ShellAction(f"cat {FROZEN}"), ALLOW),
            (ShellAction(f"echo x > {FROZEN}"), DENY),
            (ShellAction("cd app/src/test && rm FooTest.kt"), DENY),
            (ShellAction("cd tools && rm FooTest.kt"), ALLOW),
            (ShellAction("cd $DIR && rm FooTest.kt"), DENY),
            (ShellAction("rm -rf app/src"), DENY),
            (ShellAction("sed -i 's/a/b/' app/src/test/*.kt"), DENY),
            (ShellAction("python -c \"open('app/src/test/FooTest.kt','w')\""), DENY),
            (ShellAction('git commit -nm "x"'), DENY),
            (ShellAction('git commit -m "fix nothing"'), ALLOW),
            (ShellAction("Remove-Item -Path app\\src\\test\\FooTest.kt"), DENY),
            (ShellAction("python .agentkit/bin/agentkit lock unfreeze x --reason y"), DENY),
        ]
        for action, expected in rows:
            with self.subTest(action=action):
                self.assertEqual(self.verdict(action), expected)


class ForbiddenCommandTests(GuardCase):

    def test_R003_13_lock_escapes_denied(self):
        self.assert_shell(DENY,
                          "agentkit lock unfreeze tests/x.py --reason r",
                          "python -m agentkit lock unfreeze app --reason why",
                          "agentkit lock freeze --force --spec 003",
                          "python3 .agentkit/bin/agentkit lock freeze app/src --force",
                          "agentkit chaos clear 3 --note ok",
                          "echo hi && agentkit lock unfreeze x --reason y")

    def test_R003_13_other_agentkit_commands_allowed(self):
        self.assert_shell(ALLOW, "agentkit lock freeze --spec 003", "agentkit lock status",
                          "agentkit lock verify", "python -m agentkit chaos log --open",
                          "agentkit test")

    def test_R003_14_no_verify_denied(self):
        self.assert_shell(DENY, *(f"git {sub} --no-verify" for sub in
                                  ("commit -m x", "push origin main", "merge dev", "rebase main",
                                   "am x.patch", "cherry-pick abc", "revert abc")))

    def test_R003_14_short_n_cluster_on_commit_denied(self):
        self.assert_shell(DENY, "git commit -n -m x", "git commit -nm x", "git commit -anm x",
                          "git commit -a -n", "git -C . commit -qn -m x")

    def test_R003_14_ordinary_git_allowed(self):
        self.assert_shell(ALLOW, "git commit -m x", "git commit -am 'no -n here'",
                          "git log -n 5", "git push origin main", "git rebase main",
                          "git status")

    def test_R003_15_hooks_and_index_tricks_denied(self):
        self.assert_shell(DENY, "git config core.hooksPath /dev/null",
                          "git -c core.hooksPath=/tmp/x commit -m y",
                          "git config --unset core.hookspath",
                          "git update-index --assume-unchanged app/src/main/Foo.kt",
                          "git update-index --skip-worktree docs/notes.md")

    def test_R003_15_other_git_config_allowed(self):
        self.assert_shell(ALLOW, "git config user.name x", "git update-index --refresh")


class SegmentTests(GuardCase):

    def test_R003_16_operators_split_segments(self):
        self.assert_shell(DENY, *(f"ls {op} rm {FROZEN}" for op in (";", "&&", "||", "|", "&")))
        self.assert_shell(DENY, f"ls\nrm {FROZEN}", f"(rm {FROZEN})", f"ls;rm {FROZEN}",
                          f"(cd app/src/test; rm FooTest.kt)")

    def test_R003_16_prefix_words_and_assignments_skipped(self):
        self.assert_shell(DENY, *(f"{prefix} rm {FROZEN}" for prefix in
                                  ("sudo", "env", "command", "builtin", "exec", "nohup",
                                   "time", "xargs", "FOO=1", "A=1 B=2", "sudo FOO=1",
                                   "env LANG=C")))

    def test_R003_16_echo_is_not_a_write(self):
        self.assert_shell(ALLOW, f"echo rm {FROZEN}", "true && ls && pwd")


class WorkingDirectoryTests(GuardCase):

    def test_R003_17_cd_changes_resolution(self):
        self.assert_shell(DENY, "cd app/src/test && rm FooTest.kt",
                          "cd app && cd src/test && rm FooTest.kt",
                          "cd app/src && rm test/FooTest.kt",
                          "cd app/src/main && rm ../test/FooTest.kt",
                          "Set-Location app/src/test; Remove-Item FooTest.kt",
                          "pushd app/src/test && rm FooTest.kt")
        self.assert_shell(ALLOW, "cd tools && rm FooTest.kt", "cd app && rm FooTest.kt")

    def test_R003_17_popd_restores(self):
        self.assert_shell(ALLOW, "pushd app/src/test && popd && rm FooTest.kt")
        self.assert_shell(DENY, "pushd tools && popd && rm app/src/test/FooTest.kt",
                          "pushd app/src && pushd test && popd && rm test/FooTest.kt")

    def test_R003_17_cwd_argument_is_the_start(self):
        self.assert_shell(DENY, "rm FooTest.kt", cwd=self.root / "app/src/test")
        self.assert_shell(DENY, "cd ../test && rm FooTest.kt", cwd=self.root / "app/src/main")
        self.assert_shell(ALLOW, "rm FooTest.kt", cwd=self.root / "tools")

    def test_R003_17_absolute_cd_target(self):
        self.assert_shell(DENY, f"cd {(self.root / 'app/src/test').as_posix()} && rm FooTest.kt")

    def test_R003_32_unknown_directory_markers(self):
        self.assert_shell(DENY, *(f"cd {target} && rm FooTest.kt" for target in
                                  ("$DIR", "%DIR%", "~", "~/x", "`pwd`", "$(pwd)", "-",
                                   "${HOME}/x")))

    def test_R003_32_unknown_directory_persists_for_the_command(self):
        self.assert_shell(DENY, "cd $X; ls; rm FooTest.kt", "cd $X && cd sub && rm FooTest.kt")

    def test_R003_32_unknown_directory_allows_other_names(self):
        self.assert_shell(ALLOW, "cd $DIR && rm Other.kt", "cd $DIR && cat FooTest.kt")


class WriteArgumentTests(GuardCase):

    def test_R003_18_redirections_are_writes(self):
        self.assert_shell(DENY, *(f"echo x {op} {FROZEN}" for op in
                                  (">", ">>", ">|", "&>", "2>", "1>>")))
        self.assert_shell(DENY, f"echo x>{FROZEN}", f"echo x 2>>{FROZEN}",
                          f"cd app/src/test && echo x > FooTest.kt")

    def test_R003_18_null_devices_ignored(self):
        self.assert_shell(ALLOW, "make > /dev/null 2>&1", "dir > NUL", "ls > $null",
                          "echo x > docs/out.txt", f"cat {FROZEN} > /tmp/copy.txt")

    def test_R003_18_redirect_to_protected_file(self):
        self.assert_shell(DENY, "echo {} > tests.lock.json", "echo x >> chaos-log.jsonl")

    def test_R003_19_posix_write_commands(self):
        self.assert_shell(DENY, f"rm {FROZEN}", f"rm -f {FROZEN}", f"rmdir {FROZEN}",
                          f"mv {FROZEN} x.kt", f"mv x.kt {FROZEN}", f"cp x.kt {FROZEN}",
                          f"tee {FROZEN}", f"tee -a {FROZEN}", f"truncate -s 0 {FROZEN}",
                          f"dd if=/dev/zero of={FROZEN}", f"touch {FROZEN}",
                          f"ln -sf x {FROZEN}", f"install x {FROZEN}", f"unlink {FROZEN}",
                          f"shred {FROZEN}", f"chmod 000 {FROZEN}", f"chown me {FROZEN}",
                          f"patch {FROZEN}", f"cp --target-directory=x --backup={FROZEN} y")

    def test_R003_19_cmd_write_commands(self):
        self.assert_shell(DENY, *(f"{cmd} {FROZEN}" for cmd in ("del", "erase")))
        self.assert_shell(DENY, *(f"{cmd} {FROZEN} other.kt" for cmd in
                                  ("ren", "rename", "move")))
        self.assert_shell(DENY, *(f"{cmd} other.kt {FROZEN}" for cmd in ("copy", "xcopy")))

    def test_R003_19_powershell_write_commands(self):
        self.assert_shell(DENY, *(f"{cmd} -Path {FROZEN} -Value x" for cmd in
                                  ("Set-Content", "Add-Content", "sc", "ac")))
        self.assert_shell(DENY, *(f"{cmd} {FROZEN}" for cmd in
                                  ("Remove-Item", "ri", "Clear-Content", "clc", "New-Item", "ni")))
        self.assert_shell(DENY, f"Out-File -FilePath {FROZEN}", f"echo x | Out-File {FROZEN}")
        self.assert_shell(DENY, *(f"{cmd} other.kt {FROZEN}" for cmd in
                                  ("Move-Item", "mi", "Copy-Item", "cpi")))
        self.assert_shell(DENY, *(f"{cmd} {FROZEN} New.kt" for cmd in ("Rename-Item", "rni")))

    def test_R003_19_in_place_editors(self):
        self.assert_shell(DENY, f"sed -i 's/a/b/' {FROZEN}", f"sed -i.bak -e s/a/b/ {FROZEN}",
                          f"sed --in-place 's/a/b/' {FROZEN}", f"perl -pi -e 's/a/b/' {FROZEN}",
                          f"perl -i.orig -pe 1 {FROZEN}")
        self.assert_shell(ALLOW, f"sed 's/a/b/' {FROZEN}", f"sed -n 1,5p {FROZEN}",
                          "perl -ne 'print' docs/notes.md")

    def test_R003_19_find_with_actions(self):
        self.assert_shell(DENY, "find app/src/test -name '*.kt' -delete",
                          f"find {FROZEN} -exec rm {{}} ;",
                          f"find {FROZEN} -execdir chmod 0 {{}} +")
        self.assert_shell(ALLOW, "find app -name '*.kt'", "find . -type f")

    def test_R003_19_unfrozen_targets_allowed(self):
        self.assert_shell(ALLOW, "rm docs/notes.md", "touch app/src/test/NewTest.kt",
                          "cp app/src/main/Foo.kt docs/Foo.kt")

    def test_R003_19_write_commands_hit_protected_and_ask_paths(self):
        self.assert_shell(DENY, "rm tests.lock.json", "cp x agentkit.toml",
                          "mv x specs/003-guard/reviews/r.md")
        self.assert_shell(ASK, "cp x .github/workflows/ci.yml")

    def test_R003_20_git_path_commands(self):
        self.assert_shell(DENY, f"git checkout -- {FROZEN}", f"git checkout HEAD~1 {FROZEN}",
                          f"git restore {FROZEN}", f"git restore --source=HEAD~2 {FROZEN}",
                          f"git rm {FROZEN}", f"git rm --cached {FROZEN}",
                          f"git mv {FROZEN} x.kt", f"git mv x.kt {FROZEN}",
                          f"git apply {FROZEN}", f"git am {FROZEN}",
                          f"git update-index --chmod=+x {FROZEN}")
        self.assert_shell(ALLOW, "git checkout main", "git checkout -b feature",
                          "git restore docs/notes.md", "git apply fix.patch")

    def test_R003_21_inline_interpreters(self):
        script = f"open('{FROZEN}','w')"
        self.assert_shell(DENY, f'python -c "{script}"', f'python3 -c "{script}"',
                          f'py -c "{script}"', "node -e \"require('fs').rmSync('FooTest.kt')\"",
                          "deno eval --eval \"Deno.removeSync('FooTest.kt')\"",
                          "bun -e \"Bun.write('app/src/test/FooTest.kt','')\"",
                          "ruby -e \"File.delete('FooTest.kt')\"", "perl -e \"unlink 'FooTest.kt'\"",
                          "php -r \"unlink('FooTest.kt');\"",
                          f"pwsh -Command \"Remove-Item {FROZEN}\"",
                          "powershell -Command \"Clear-Content FooTest.kt\"",
                          f"bash -c 'rm {FROZEN}'", "sh -c 'echo > FooTest.kt'",
                          "zsh -c 'rm FooTest.kt'")

    def test_R003_21_inline_scripts_naming_kit_files(self):
        self.assert_shell(DENY, "python -c \"open('tests.lock.json','w').write('{}')\"",
                          "python -c \"open('tests.unfreeze-log.md','w')\"",
                          "node -e \"fs.appendFileSync('chaos-log.jsonl','x')\"",
                          "python -c \"open('specs/003-guard/reviews/r.md','w')\"")

    def test_R003_21_harmless_inline_scripts_allowed(self):
        self.assert_shell(ALLOW, "python -c \"print(1)\"", "node -e \"console.log(2)\"",
                          f"python -m unittest {FROZEN}", "python tools/run.py",
                          "bash tools/build.sh")

    def test_R003_22_globs_matching_frozen_paths(self):
        self.assert_shell(DENY, "rm app/src/test/*.kt", "rm app/src/test/Foo?est.kt",
                          "rm app/src/test/[F]ooTest.kt", "rm app/*/test/FooTest.kt",
                          "cd app/src && rm test/*.kt")
        self.assert_shell(ALLOW, "rm docs/*.md", "rm app/src/main/*.kt", "rm app/src/test/*.java")

    def test_R003_23_directories_holding_frozen_files(self):
        self.assert_shell(DENY, "rm -rf app/src", "rm -r app", "rm -rf app/src/", "rm -rf .",
                          "rmdir app/src/test", "mv app/src/test elsewhere",
                          "git rm -r app/src", "git mv app/src renamed",
                          "find app -delete", "Remove-Item -Recurse app/src", "ri app",
                          "shred -u app/src/test", "cd app && rm -rf src")
        self.assert_shell(ALLOW, "rm -rf docs", "rm -rf app/src/main", "cp -r app/src backup",
                          "touch app/src/test")

    def test_R003_24_basename_only_when_directory_unknown(self):
        self.assert_shell(ALLOW, "rm FooTest.kt", "cd tools && rm FooTest.kt")
        self.assert_shell(DENY, "cd $DIR && rm FooTest.kt", "cd ~ && touch FooTest.kt",
                          "cd $DIR && rm footest.KT")

    def test_R003_25_read_only_commands_allowed(self):
        self.assert_shell(ALLOW, f"cat {FROZEN}", f"grep -n Foo {FROZEN}", f"git diff {FROZEN}",
                          f"git log -- {FROZEN}", f"head -5 {FROZEN}", f"wc -l {FROZEN}",
                          f"less {FROZEN}", f"git show HEAD:{FROZEN}", "grep -rn Foo app/src/test",
                          "ls app/src/test", "cd app/src/test && cat FooTest.kt")

    def test_R003_26_backslashes_and_quotes(self):
        self.assert_shell(DENY, "Remove-Item -Path app\\src\\test\\FooTest.kt",
                          f'rm "{FROZEN}"', f"rm '{FROZEN}'", "del app\\src\\test\\FooTest.kt",
                          "cd app\\src\\test && del FooTest.kt")

    def test_R003_26_unbalanced_quotes_fall_back(self):
        self.assert_shell(DENY, f'rm {FROZEN} "oops', f"echo 'x && rm {FROZEN}",
                          f'echo "a;rm {FROZEN}')
        self.assert_shell(ALLOW, "echo \"it's", "grep -n 'unclosed docs/notes.md")


if __name__ == "__main__":
    unittest.main()
