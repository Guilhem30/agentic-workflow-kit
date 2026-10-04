"""Command-line entry point (spec 000). Dispatches `models` (001), `lock ...` (002),
`new-spec`, `spec-status` and `trace` (005), `status` and `handoff` (006), `test` (007), `codemap` (008), `lint-instructions` (009), `chaos ...` (020) and `autopilot` (021).
`install`, `update` and `sync` (010) and `pre-commit` and `check-commit-msg` (018) are stubs."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agentkit import __doc__ as KIT_DOC
from agentkit.config import MODELS_HELP, TIER_EFFORT, TIERS, ConfigError, load_config
from agentkit.lock import LockError, OwnerCheckError

HOOK_FORMATS = ("claude", "codex", "dsh", "opencode", "pi")  # spec 004

VERSION = "0.0.0"


class UsageError(Exception):
    """A usage problem found after parsing; exit 2."""


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # exit 2 with usage on stderr, as argparse does
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(2)


def _abs(paths: list[str]) -> list[str]:
    """The CLI resolves path arguments against the current directory (002 Conventions)."""
    return [str((Path.cwd() / p)) if not Path(p).is_absolute() else p for p in paths]


# commands --------------------------------------------------------------------------------

def cmd_version(args) -> int:
    print(f"agentkit {VERSION}")
    return 0


def cmd_models(args) -> int:
    cfg = load_config()
    mode = cfg.data.get("models", {}).get("mode", "tool")
    for adapter in cfg.adapters:
        print(f"{adapter}: mode {mode}")
        models = cfg.models(adapter)
        for tier in TIERS:
            if tier in models:
                print(f"  {tier}: {models[tier]} (effort {TIER_EFFORT[tier]})")
            else:
                print(f"  {tier}: decided by the tool")
    return 0


def cmd_install(args) -> int:
    if not args.models:
        print("install needs --models tool|kit:", file=sys.stderr)
        print(MODELS_HELP, file=sys.stderr, end="")
        return 2
    raise NotImplementedError("R010-01")


def cmd_update(args) -> int:
    raise NotImplementedError("R010-17")


def cmd_sync(args) -> int:
    raise NotImplementedError("R010-18")


def cmd_pre_commit(args) -> int:
    raise NotImplementedError("R018-03")


def cmd_check_commit_msg(args) -> int:
    raise NotImplementedError("R018-06")


def cmd_lock(args) -> int:
    from agentkit import lock
    cfg = load_config()
    sub = args.lock_cmd
    if sub == "freeze":
        if not args.paths and args.spec is None and not args.all:
            print("lock freeze needs PATH..., --spec NNN or --all", file=sys.stderr)
            return 2
        if args.spec is not None:
            from agentkit import chaos
            refusal = chaos._agent_gate_refusal(cfg, args.spec, "frozen")
            if refusal:
                print(refusal[1], file=sys.stderr)
                return refusal[0]
        result = lock.freeze(cfg, paths=_abs(args.paths) if args.paths else None,
                             spec=args.spec, all_candidates=args.all, force=args.force)
        if result.errors:
            print("freeze refused; nothing written:")
            for err in result.errors:
                print(f"  {err}")
            print("hint: fix the paths above, or ask the owner about files already frozen")
            return 1
        print(f"frozen: {len(result.added)} added, {len(result.unchanged)} unchanged")
        for rel in result.added:
            print(f"  + {rel}")
        if args.spec is not None:
            print(f"spec {args.spec}: status frozen")
        return 0
    if sub == "verify":
        violations = lock.verify(cfg, staged=args.staged)
        if violations:
            print(f"lock: VIOLATED ({len(violations)} file(s))")
            for v in violations:
                print(f"  {v.kind} {v.path}")
            print("hint: restore with `agentkit lock restore`, or ask the owner to unfreeze")
            return 1
        total = len(lock.load_lock(cfg)["files"])
        print(f"lock: OK ({total} frozen file(s))")
        return 0
    if sub == "status":
        st = lock.status(cfg)
        parts = ", ".join(f"{k or 'no spec'}: {v}" for k, v in
                          sorted(st["by_spec"].items(), key=lambda kv: (kv[0] is None, kv[0] or "")))
        print(f"frozen: {st['frozen']} file(s)" + (f" ({parts})" if parts else ""))
        if st["violations"]:
            print(f"verify: VIOLATED ({len(st['violations'])} file(s))")
            for v in st["violations"]:
                print(f"  {v.kind} {v.path}")
            print("hint: restore with `agentkit lock restore`, or ask the owner to unfreeze")
        else:
            print("verify: OK")
        cands = st["unfrozen_candidates"]
        print(f"not yet frozen: {len(cands)} candidate(s)")
        for rel in cands[:20]:
            print(f"  {rel}")
        if len(cands) > 20:
            print(f"  ... {len(cands) - 20} more")
        return 1 if st["violations"] else 0
    if sub == "unfreeze":
        removed = lock.unfreeze(cfg, _abs(args.paths), args.reason or "")
        print(f"unfrozen: {len(removed)} file(s)")
        for rel in removed:
            print(f"  - {rel}")
        return 0
    if sub == "restore":
        restored, failed = lock.restore(cfg, paths=_abs(args.paths) if args.paths else None,
                                        ref=args.ref)
        for rel in restored:
            print(f"restored {rel}")
        for rel in failed:
            print(f"not restored {rel}")
        if failed:
            print("hint: ask the owner")
            return 1
        if not restored:
            print("nothing to restore")
        return 0
    if sub == "audit":
        problems = lock.audit(cfg, base=args.base, staged=args.staged)
        for p in problems:
            print(f"audit: {p}")
        if problems:
            print("hint: restore the frozen files and the log from git, or ask the owner")
            return 1
        print("audit: OK")
        return 0
    raise UsageError("lock needs a subcommand")


def cmd_spec_status(args) -> int:
    from agentkit import specs
    cfg = load_config()
    dup = specs._duplicates(cfg, args.id)
    if dup:
        print(f"duplicate spec number {args.id}: " + ", ".join(s.dir.name for s in dup))
        return 1
    spec = specs.find_spec(cfg, args.id)
    if spec is None:
        print(f"spec {args.id} does not exist")
        return 1
    if not spec.spec_md.is_file():
        print(f"spec {args.id}: {spec.dir.name}/spec.md does not exist")
        return 1
    new = args.status
    if spec.status == specs.DROPPED:
        print(f"spec {args.id} is dropped, a terminal phase: its status no longer changes")
        return 1
    if new == "frozen":
        print("`frozen` is set only by `agentkit lock freeze --spec NNN` (002)")
        return 1
    if new not in specs.PHASES and new != specs.DROPPED:
        print(f"unknown phase {new!r}; phases: {', '.join(specs.PHASES)}, {specs.DROPPED}")
        return 1
    if new == specs.DROPPED and spec.status not in ("draft", "approved", "tests-draft"):
        if spec.status in specs.PHASES:
            print(f"spec {args.id} is {spec.status}: the owner must unfreeze it before dropping it")
        else:
            print(f"spec {args.id} has the unknown status {spec.status!r}; fix spec.md first")
        return 1
    if new in ("approved", "tests-approved", "done"):
        from agentkit import chaos
        refusal = chaos._agent_gate_refusal(cfg, args.id, new)
        if refusal:
            print(refusal[1], file=sys.stderr)
            return refusal[0]
    specs.set_status(spec, new)
    print(f"spec {args.id}: status {new}")
    return 0


def cmd_new_spec(args) -> int:
    from agentkit import specs
    if len(args.words) > 2:
        raise UsageError("new-spec takes [NNN] slug")
    spec_id, slug = (None, args.words[0]) if len(args.words) == 1 else args.words
    cfg = load_config()
    try:
        folder = specs.new_spec(cfg, spec_id, slug, args.title or "")
    except ValueError as exc:
        print(exc)
        return 1
    print(f"spec {folder.name[:3]}: created {folder.relative_to(cfg.root).as_posix()}/")
    return 0


def cmd_trace(args) -> int:
    from agentkit import trace
    cfg = load_config()
    code, lines = trace._trace_command(cfg, args.spec)
    for line in lines:
        print(line)
    return code


_GUARD_ALLOWING = "agentkit guard error (allowing): "
_VERIFY_HINT = "hint: restore with `agentkit lock restore`, or ask the owner to unfreeze"


def _read_payload() -> tuple[dict, str | None]:
    """One JSON object from stdin, as UTF-8 (R004-02). A bad payload gives ({}, why)."""
    try:
        stream = getattr(sys.stdin, "buffer", None)
        raw = stream.read() if stream is not None else sys.stdin.read().encode("utf-8")
        text = raw.decode("utf-8-sig")
    except (OSError, ValueError, AttributeError) as exc:
        return {}, f"cannot read the hook payload ({exc})"
    if not text.strip():
        return {}, "empty hook payload"
    try:
        payload = json.loads(text)
    except (ValueError, RecursionError) as exc:
        return {}, f"the hook payload is not JSON ({exc})"
    if not isinstance(payload, dict):
        return {}, f"the hook payload is not a JSON object (got {type(payload).__name__})"
    return payload, None


def _emit(response, stderr: bool = True) -> int:
    """Print a hook Response with LF endings (R000-07). `stderr=False` when the guard has
    already printed the message itself (003 degraded mode)."""
    if stderr and response.stderr:
        sys.stderr.write(response.stderr)
        sys.stderr.flush()
    if response.stdout:
        buffer = getattr(sys.stdout, "buffer", None)
        if buffer is not None:
            sys.stdout.flush()
            buffer.write(response.stdout.encode("utf-8"))
            buffer.flush()
        else:
            sys.stdout.write(response.stdout)
            sys.stdout.flush()
    return response.code


def cmd_guard(args) -> int:
    from agentkit import guard
    from agentkit.payloads import get_format
    fmt = get_format(args.format)
    payload, problem = _read_payload()
    cwd = None
    if problem is None:
        try:
            actions, cwd = fmt.parse(payload)
        except Exception as exc:  # noqa: BLE001 - a payload we cannot read is allowed (R003-31)
            problem = f"cannot read the hook payload ({type(exc).__name__}: {exc})"
    if problem is not None:
        decision = guard.Decision(guard.ALLOW, [_GUARD_ALLOWING + problem], degraded=True)
        return _emit(fmt.pre_response(decision))
    start = Path(cwd) if cwd and Path(cwd).is_dir() else None
    try:
        cfg = load_config(start)
    except ConfigError:
        cfg = None  # 003 runs degraded
    decision = guard.evaluate(cfg, actions, cwd=cwd)
    # A degraded allow has already printed its warning (R003-31).
    return _emit(fmt.pre_response(decision), stderr=not decision.degraded)


def _verify_problems(lock) -> list[str]:
    """Each violated file, plus the hint (R004-15)."""
    problems = [f"{v.kind} {v.path}" for v in lock.verify(load_config())]
    if problems:
        problems.append(_VERIFY_HINT)
    return problems


def cmd_verify(args) -> int:
    from agentkit import lock
    payload = {}
    fmt = None
    if args.format is not None:
        from agentkit.payloads import get_format
        fmt = get_format(args.format)
        payload, _ = _read_payload()
    if fmt is not None:
        # A hook must get its JSON and exit 0 (R004-16): errors become problems.
        try:
            problems = _verify_problems(lock)
        except (ConfigError, LockError) as exc:
            problems = [f"agentkit: {exc}"]
        return _emit(fmt.stop_response(payload, problems))
    problems = _verify_problems(lock)
    for line in problems or ["verify: OK"]:
        print(line)
    return 1 if problems else 0


def cmd_status(args) -> int:
    from agentkit import status
    if args.format is not None:
        from agentkit.payloads import get_format
        fmt = get_format(args.format)
        _read_payload()
        try:
            text = "\n".join(status.status_lines(load_config()))
        except (ConfigError, LockError) as exc:  # a session start must not fail (R004-20)
            text = f"agentkit: {exc}"
        return _emit(fmt.session_response(text))
    for line in status.status_lines(load_config()):
        print(line)
    return 0


def cmd_handoff(args) -> int:
    from agentkit import handoff
    return handoff._cli(load_config(), args)


def cmd_codemap(args) -> int:
    from agentkit import codemap
    return codemap._cli(load_config(), args.check)


def cmd_lint_instructions(args) -> int:
    from agentkit import lint_instructions
    return lint_instructions._cli(load_config())


def cmd_test(args) -> int:
    from agentkit import runtests
    code, lines = runtests.run_tests(load_config(), args.scope)
    for line in lines:
        print(line)
    return code


def cmd_chaos(args) -> int:
    from agentkit import chaos
    return chaos._cli(args)


def cmd_autopilot(args) -> int:
    from agentkit import autopilot
    return autopilot._cli(args)


# parser ----------------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog="agentkit", description=KIT_DOC)
    sub = p.add_subparsers(dest="command", parser_class=_Parser)

    sub.add_parser("version", help="print the version").set_defaults(func=cmd_version)
    sub.add_parser("models", help="show model routing (001)").set_defaults(func=cmd_models)

    inst = sub.add_parser("install", help="install or update agentkit in this repository (010)",
                          epilog=MODELS_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    inst.add_argument("--target")
    inst.add_argument("--profile")
    inst.add_argument("--adapters")
    inst.add_argument("--ci")
    inst.add_argument("--ci-os")
    inst.add_argument("--models", choices=["tool", "kit"])
    inst.add_argument("--owner", default="")
    inst.add_argument("--python")
    inst.add_argument("--force", action="store_true")
    inst.add_argument("--self", dest="self_hosted", action="store_true")
    inst.set_defaults(func=cmd_install)

    up = sub.add_parser("update", help="update the installed kit files (010)")
    up.add_argument("--kit")
    up.add_argument("--force", action="store_true")
    up.set_defaults(func=cmd_update)

    sy = sub.add_parser("sync", help="regenerate the derived adapter files (010)")
    sy.add_argument("--check", action="store_true")
    sy.set_defaults(func=cmd_sync)

    lk = sub.add_parser("lock", help="test-freeze lock (002)")
    lsub = lk.add_subparsers(dest="lock_cmd", parser_class=_Parser)
    fr = lsub.add_parser("freeze")
    fr.add_argument("paths", nargs="*")
    fr.add_argument("--spec")
    fr.add_argument("--all", action="store_true")
    fr.add_argument("--force", action="store_true")
    vf = lsub.add_parser("verify")
    vf.add_argument("--staged", action="store_true")
    lsub.add_parser("status")
    uf = lsub.add_parser("unfreeze")
    uf.add_argument("paths", nargs="+")
    uf.add_argument("--reason")
    rs = lsub.add_parser("restore")
    rs.add_argument("paths", nargs="*")
    rs.add_argument("--ref", default="HEAD")
    au = lsub.add_parser("audit")
    au.add_argument("--base", default="HEAD")
    au.add_argument("--staged", action="store_true")
    lk.set_defaults(func=cmd_lock)

    ns = sub.add_parser("new-spec", help="create a draft spec from the templates (005)")
    ns.add_argument("words", nargs="+", metavar="[NNN] slug")
    ns.add_argument("--title")
    ns.set_defaults(func=cmd_new_spec)

    ss = sub.add_parser("spec-status", help="set a spec's phase (005)")
    ss.add_argument("id")
    ss.add_argument("status")
    ss.set_defaults(func=cmd_spec_status)

    tr = sub.add_parser("trace", help="requirement traceability (005)")
    tr.add_argument("--spec")
    tr.set_defaults(func=cmd_trace)

    gd = sub.add_parser("guard", help="pre-tool hook: judge one tool call (003, 004)")
    gd.add_argument("--format", required=True, choices=HOOK_FORMATS)
    gd.set_defaults(func=cmd_guard)

    ve = sub.add_parser("verify", help="end-of-turn hook: lock verify (004)")
    ve.add_argument("--format", choices=HOOK_FORMATS)
    ve.set_defaults(func=cmd_verify)

    st = sub.add_parser("status", help="short session summary (006)")
    st.add_argument("--format", choices=HOOK_FORMATS)
    st.set_defaults(func=cmd_status)

    ho = sub.add_parser("handoff", help="write the resume snapshot to progress.md (006)")
    ho.add_argument("id")
    ho.add_argument("--note", default="")
    ho.add_argument("--next", dest="next_step", default="")
    ho.set_defaults(func=cmd_handoff)

    cm = sub.add_parser("codemap", help="write docs/CODEMAP.md (008)")
    cm.add_argument("--check", action="store_true")
    cm.set_defaults(func=cmd_codemap)

    li = sub.add_parser("lint-instructions", help="check instruction token budgets (009)")
    li.set_defaults(func=cmd_lint_instructions)

    te = sub.add_parser("test", help="run the tests, print a compact summary (007)")
    te.add_argument("scope", nargs="?")
    te.set_defaults(func=cmd_test)

    ch = sub.add_parser("chaos", help="chaos mode: agent-approved gates (020)")
    csub = ch.add_subparsers(dest="chaos_cmd", parser_class=_Parser)
    ap = csub.add_parser("approve")
    ap.add_argument("id")
    ap.add_argument("gate")
    ap.add_argument("--review")
    cu = csub.add_parser("unfreeze")
    cu.add_argument("paths", nargs="+")
    cu.add_argument("--reason")
    cu.add_argument("--auditor-review")
    cu.add_argument("--impl-review")
    cc = csub.add_parser("clear")
    cc.add_argument("seqs", nargs="*")
    cc.add_argument("--all", action="store_true")
    cc.add_argument("--note")
    cl = csub.add_parser("log")
    cl.add_argument("--spec")
    cl.add_argument("--last", type=int, default=20)
    cl.add_argument("--open", action="store_true")
    ca = csub.add_parser("audit")
    ca.add_argument("--base", default="HEAD")
    ca.add_argument("--staged", action="store_true")
    ch.set_defaults(func=cmd_chaos)

    pc = sub.add_parser("pre-commit", help="the git pre-commit checks (018)")
    pc.set_defaults(func=cmd_pre_commit)

    cmsg = sub.add_parser("check-commit-msg", help="check a commit message file (018)")
    cmsg.add_argument("file")
    cmsg.set_defaults(func=cmd_check_commit_msg)

    at = sub.add_parser("autopilot", help="the next /autopilot step (021)", add_help=False)
    at.add_argument("ids", nargs="*")
    at.set_defaults(func=cmd_autopilot)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except ConfigError as exc:
        print(f"agentkit: {exc}", file=sys.stderr)
        return 2
    except OwnerCheckError as exc:
        print(f"agentkit: {exc}", file=sys.stderr)
        return 2
    except LockError as exc:
        print(f"agentkit: {exc}", file=sys.stderr)
        return 1
    except UsageError as exc:
        print(f"agentkit: {exc}", file=sys.stderr)
        return 2
