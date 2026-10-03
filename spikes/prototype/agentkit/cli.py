"""Command line entry point: `python .agentkit/bin/agentkit <command>` or `python -m agentkit`."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from . import __version__
from .config import KIT_ROOT, ConfigError, find_root, load_config

CONVENTIONAL_RX = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert|spec)(\([\w.\-/,]+\))?!?: \S.*"
)
AUTO_MSG_RX = re.compile(r"^(Merge |Revert \"|fixup! |squash! |amend! )")


def _out(lines) -> None:
    text = "\n".join(lines) if isinstance(lines, list) else str(lines)
    if text:
        sys.stdout.write(text + "\n")


def _cfg(args=None, start: Path | None = None):
    root = os.environ.get("AGENTKIT_ROOT")
    if root and (Path(root) / "agentkit.toml").is_file():
        return load_config(root=Path(root))
    return load_config(start=start)


def _read_payload() -> dict:
    raw = sys.stdin.buffer.read() if not sys.stdin.isatty() else b""
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _emit(resp) -> int:
    if resp.stdout:
        sys.stdout.write(resp.stdout + "\n")
    if resp.stderr:
        sys.stderr.write(resp.stderr + "\n")
    return resp.code


# -- commands --------------------------------------------------------------------------


def cmd_install(a) -> int:
    from .install import install

    adapters = [x.strip() for x in a.adapters.split(",") if x.strip()] if a.adapters else []
    rep = install(
        Path(a.target),
        profile=a.profile,
        adapters=adapters,
        ci=a.ci,
        owner=a.owner or "",
        python=a.python,
        force=a.force,
        self_hosted=a.self_hosted,
    )
    _out(rep.lines() or ["nothing to do"])
    return 0


def cmd_update(a) -> int:
    from .install import update

    cfg = _cfg()
    src = Path(a.kit).resolve() if a.kit else cfg.kit_source
    rep = update(cfg.root, src, force=a.force)
    _out(rep.lines() or ["up to date"])
    return 1 if rep.conflicts else 0


def cmd_sync(a) -> int:
    from .install import sync

    rep = sync(_cfg(), check=a.check)
    if a.check:
        if rep.drift:
            _out(["generated agent files are out of date (run `agentkit sync`):"] + [f"  {p}" for p in rep.drift])
            return 1
        _out("sync: OK")
        return 0
    _out(rep.lines() or ["sync: up to date"])
    return 0


def cmd_lock(a) -> int:
    from . import lock

    cfg = _cfg()
    try:
        if a.lock_cmd == "verify":
            v = lock.verify(cfg, staged=a.staged)
            if v:
                _out([f"lock: {len(v)} frozen file(s) changed:"] + [f"  {x}" for x in v]
                     + ["undo with `agentkit lock restore`, or ask the human to unfreeze"])
                return 1
            _out(f"lock: OK ({len(lock.load_lock(cfg)['files'])} frozen files)")
            return 0
        if a.lock_cmd == "status":
            s = lock.status(cfg)
            lines = [f"frozen: {s['frozen']}" + (" (" + ", ".join(f"{k}: {v}" for k, v in s["by_spec"].items()) + ")" if s["by_spec"] else "")]
            lines.append("verify: " + ("OK" if not s["violations"] else f"{len(s['violations'])} violation(s)"))
            if s["unfrozen_candidates"]:
                lines.append(f"not yet frozen (match frozen globs): {len(s['unfrozen_candidates'])}")
                lines.extend(f"  {p}" for p in s["unfrozen_candidates"][:20])
            _out(lines)
            return 0
        if a.lock_cmd == "freeze":
            res = lock.freeze(cfg, paths=a.paths, spec=a.spec, all_candidates=a.all)
            if res.errors:
                _out(["freeze refused (nothing written):"] + [f"  {e}" for e in res.errors])
                return 1
            _out([f"frozen {len(res.added)} file(s)" + (f" for spec {a.spec}" if a.spec else "")]
                 + [f"  {p}" for p in res.added])
            if not res.added:
                _out("nothing new to freeze")
            return 0
        if a.lock_cmd == "unfreeze":
            why = lock.human_check()
            if why:
                _out(why)
                return 2
            rels = lock.unfreeze(cfg, a.paths, a.reason)
            _out([f"unfrozen {len(rels)} file(s); logged in {cfg.unfreeze_log_rel}"] + [f"  {r}" for r in rels])
            return 0
        if a.lock_cmd == "restore":
            restored, failed = lock.restore(cfg, a.paths or None, ref=a.ref)
            lines = [f"restored {len(restored)} file(s) from {a.ref}"] + [f"  {r}" for r in restored]
            if failed:
                lines += [f"could not restore {len(failed)} (no matching content at {a.ref}):"] + [f"  {r}" for r in failed]
            _out(lines)
            return 1 if failed else 0
        if a.lock_cmd == "audit":
            problems = lock.audit(cfg, base=a.base, staged=a.staged)
            if problems:
                _out(["lock audit failed:"] + [f"  {p}" for p in problems])
                return 1
            _out("lock audit: OK")
            return 0
    except lock.LockError as e:
        _out(f"lock: {e}")
        return 1
    return 2


def cmd_guard(a) -> int:
    from .guard import evaluate
    from .payloads import get_format

    fmt = get_format(a.format)
    payload = _read_payload()
    try:
        cfg = _cfg(start=Path(payload["cwd"]) if payload.get("cwd") else None)
        actions, cwd = fmt.parse(payload)
        decision = evaluate(cfg, actions, cwd)
    except Exception as e:  # never brick the agent: the neutral layers still hold
        sys.stderr.write(f"agentkit guard error (allowing): {e}\n")
        return 1
    return _emit(fmt.pre_response(decision))


def _verify_problems(cfg) -> list[str]:
    from . import lock

    try:
        problems = [f"{v} (frozen)" for v in lock.verify(cfg)]
    except lock.LockError as e:
        return [f"lock file broken: {e}"]
    if problems:
        problems.append("restore them with `agentkit lock restore` (or ask the human to unfreeze)")
    return problems


def cmd_verify(a) -> int:
    from .payloads import get_format

    payload = _read_payload()
    if a.format:
        fmt = get_format(a.format)
        try:
            cfg = _cfg(start=Path(payload["cwd"]) if payload.get("cwd") else None)
            problems = _verify_problems(cfg)
        except Exception as e:
            sys.stderr.write(f"agentkit verify error: {e}\n")
            return 1
        return _emit(fmt.stop_response(payload, problems))
    problems = _verify_problems(_cfg())
    _out(problems or ["verify: OK"])
    return 1 if problems else 0


def cmd_status(a) -> int:
    from .status import status_lines

    try:
        lines = status_lines(_cfg())
    except ConfigError as e:
        lines = [f"agentkit: {e}"]
    if a.format:
        from .payloads import get_format

        _read_payload()
        return _emit(get_format(a.format).session_response("\n".join(lines)))
    _out(lines)
    return 0


def cmd_trace(a) -> int:
    from .trace import format_results, trace_specs

    try:
        results = trace_specs(_cfg(), a.spec)
    except ValueError as e:
        _out(str(e))
        return 1
    _out(format_results(results))
    return 0 if all(r.ok for r in results) else 1


def cmd_handoff(a) -> int:
    from .handoff import snapshot

    try:
        block = snapshot(_cfg(), a.spec, note=a.note or "", next_step=a.next or "")
    except ValueError as e:
        _out(str(e))
        return 1
    _out(block)
    return 0


def cmd_test(a) -> int:
    from .runtests import run_tests

    try:
        code, lines = run_tests(_cfg(), a.scope)
    except ValueError as e:
        _out(str(e))
        return 2
    _out(lines)
    return code


def cmd_codemap(a) -> int:
    from . import codemap

    cfg = _cfg()
    ok = codemap.write(cfg, check=a.check)
    if a.check and not ok:
        _out(f"{cfg.path('codemap')} is out of date: run `agentkit codemap`")
        return 1
    _out(f"codemap: {'OK' if a.check else 'written to ' + cfg.path('codemap')}")
    return 0


def cmd_lint(a) -> int:
    from .lint_instructions import lint

    rep = lint(_cfg())
    lines = [f"error: {e}" for e in rep.errors] + [f"warning: {w}" for w in rep.warnings]
    lines.append(f"lint-instructions: {'OK' if rep.ok else 'FAILED'} (always-loaded instructions ~{rep.always_loaded_tokens} tokens)")
    _out(lines)
    return 0 if rep.ok else 1


def cmd_new_spec(a) -> int:
    from .specs import new_spec

    try:
        d = new_spec(_cfg(), a.id, a.slug, a.title or "")
    except ValueError as e:
        _out(str(e))
        return 1
    _out(f"created {d.relative_to(_cfg().root).as_posix()}/ (spec.md, plan.md, tasks.md, progress.md)")
    return 0


def cmd_spec_status(a) -> int:
    from .specs import find_spec, set_status

    cfg = _cfg()
    s = find_spec(cfg, a.id)
    if not s:
        _out(f"spec {a.id} not found")
        return 1
    if a.status == "frozen":
        _out("`frozen` is set by `agentkit lock freeze --spec` (the /freeze gate)")
        return 1
    try:
        set_status(s, a.status)
    except ValueError as e:
        _out(str(e))
        return 1
    _out(f"spec {s.id}: status -> {a.status}")
    return 0


def cmd_pre_commit(a) -> int:
    from . import lock
    from .install import sync
    from .lint_instructions import lint

    cfg = _cfg()
    failures = []
    try:
        v = lock.verify(cfg, staged=True)
        failures += [f"frozen file changed in the commit: {x}" for x in v]
        failures += lock.audit(cfg, base="HEAD", staged=True)
    except lock.LockError as e:
        failures.append(f"lock: {e}")
    rep = lint(cfg)
    failures += [f"lint-instructions: {e}" for e in rep.errors]
    drift = sync(cfg, check=True).drift
    failures += [f"out of date (run `agentkit sync`): {p}" for p in drift]
    if failures:
        _out(["agentkit pre-commit FAILED:"] + [f"  {f}" for f in failures]
             + ["(never bypass with --no-verify; frozen tests change only via `agentkit lock unfreeze` by the human)"])
        return 1
    return 0


def cmd_commit_msg(a) -> int:
    text = Path(a.file).read_text(encoding="utf-8", errors="replace")
    first = next((l for l in text.splitlines() if l.strip() and not l.startswith("#")), "")
    if CONVENTIONAL_RX.match(first) or AUTO_MSG_RX.match(first):
        return 0
    _out([f"commit message is not a conventional commit: '{first[:80]}'",
          "expected e.g. `feat(001): add config loader`, `test(001): freeze model tests`, `chore: bootstrap`"])
    return 1


def cmd_version(a) -> int:
    _out(f"agentkit {__version__}")
    return 0


# -- parser ---------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agentkit", description="Spec -> tests -> freeze -> implement, for any agent.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("install", help="install the kit into a repository")
    s.add_argument("--target", default=".")
    s.add_argument("--profile")
    s.add_argument("--adapters", default="", help="comma list: claude-code,codex,opencode,deepseek-harness,pi")
    s.add_argument("--ci", choices=["github", "gitlab", "none"])
    s.add_argument("--owner", help="CODEOWNERS owner for tests and the lock, e.g. @you")
    s.add_argument("--python", help="interpreter command used by agent hooks (default: python on Windows, else python3)")
    s.add_argument("--force", action="store_true", help="overwrite files you customised")
    s.add_argument("--self", dest="self_hosted", action="store_true", help="install the kit into its own repo")
    s.set_defaults(fn=cmd_install)

    s = sub.add_parser("update", help="re-render kit files (from --kit for a newer version)")
    s.add_argument("--kit")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_update)

    s = sub.add_parser("sync", help="regenerate per-tool copies of skills and roles")
    s.add_argument("--check", action="store_true")
    s.set_defaults(fn=cmd_sync)

    s = sub.add_parser("lock", help="test-freeze lock")
    ls = s.add_subparsers(dest="lock_cmd", required=True)
    x = ls.add_parser("verify")
    x.add_argument("--staged", action="store_true", help="check the git index instead of the worktree")
    ls.add_parser("status")
    x = ls.add_parser("freeze")
    x.add_argument("paths", nargs="*")
    x.add_argument("--spec")
    x.add_argument("--all", action="store_true")
    x = ls.add_parser("unfreeze", help="HUMAN ONLY: run in your own terminal")
    x.add_argument("paths", nargs="+")
    x.add_argument("--reason", required=True)
    x = ls.add_parser("restore", help="undo changes to frozen files from git")
    x.add_argument("paths", nargs="*")
    x.add_argument("--ref", default="HEAD")
    x = ls.add_parser("audit", help="lock entries removed since BASE must be logged unfreezes")
    x.add_argument("--base", default="HEAD")
    x.add_argument("--staged", action="store_true")
    s.set_defaults(fn=cmd_lock)

    s = sub.add_parser("guard", help="pre-tool hook: payload on stdin")
    s.add_argument("--format", required=True)
    s.set_defaults(fn=cmd_guard)

    s = sub.add_parser("verify", help="end-of-turn check (lock)")
    s.add_argument("--format")
    s.set_defaults(fn=cmd_verify)

    s = sub.add_parser("status", help="<= 10 lines: specs, phases, lock, next action")
    s.add_argument("--format")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("trace", help="every requirement ID must appear in a test")
    s.add_argument("--spec")
    s.set_defaults(fn=cmd_trace)

    s = sub.add_parser("handoff", help="refresh specs/NNN/progress.md")
    s.add_argument("spec")
    s.add_argument("--note")
    s.add_argument("--next")
    s.set_defaults(fn=cmd_handoff)

    s = sub.add_parser("test", help="run tests, print a compact summary")
    s.add_argument("scope", nargs="?")
    s.set_defaults(fn=cmd_test)

    s = sub.add_parser("codemap", help="generate docs/CODEMAP.md")
    s.add_argument("--check", action="store_true")
    s.set_defaults(fn=cmd_codemap)

    s = sub.add_parser("lint-instructions", help="token budgets for instruction files")
    s.set_defaults(fn=cmd_lint)

    s = sub.add_parser("new-spec", help="create specs/NNN-slug from templates")
    s.add_argument("id")
    s.add_argument("slug")
    s.add_argument("--title")
    s.set_defaults(fn=cmd_new_spec)

    s = sub.add_parser("spec-status", help="set a spec's phase")
    s.add_argument("id")
    s.add_argument("status")
    s.set_defaults(fn=cmd_spec_status)

    s = sub.add_parser("pre-commit", help="git pre-commit checks")
    s.set_defaults(fn=cmd_pre_commit)

    s = sub.add_parser("check-commit-msg", help="git commit-msg check")
    s.add_argument("file")
    s.set_defaults(fn=cmd_commit_msg)

    s = sub.add_parser("version")
    s.set_defaults(fn=cmd_version)
    return p


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args) or 0
    except ConfigError as e:
        sys.stderr.write(f"agentkit: {e}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
