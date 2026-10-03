"""Command-line entry point (spec 000). Dispatches `models` (001), `lock ...` (002),
`spec-status` and `trace` (005), `chaos ...` (020) and `autopilot` (021)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agentkit import __doc__ as KIT_DOC
from agentkit.config import MODELS_HELP, TIER_EFFORT, TIERS, ConfigError, load_config
from agentkit.lock import LockError, OwnerCheckError

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


def cmd_lock(args) -> int:
    from agentkit import lock
    cfg = load_config()
    sub = args.lock_cmd
    if sub == "freeze":
        if not args.paths and args.spec is None and not args.all:
            print("lock freeze needs PATH..., --spec NNN or --all", file=sys.stderr)
            return 2
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
    dup = specs.duplicates(cfg, args.id)
    if dup:
        print(f"duplicate spec number {args.id}: " + ", ".join(s.dir.name for s in dup))
        return 1
    spec = specs.find_spec(cfg, args.id)
    if spec is None:
        print(f"spec {args.id} does not exist")
        return 1
    new = args.status
    if new == "frozen":
        print("`frozen` is set only by `agentkit lock freeze --spec NNN` (002)")
        return 1
    if new not in specs.PHASES and new != specs.DROPPED:
        print(f"unknown phase {new!r}; phases: {', '.join(specs.PHASES)}, {specs.DROPPED}")
        return 1
    if new == specs.DROPPED and spec.status not in ("draft", "approved", "tests-draft"):
        print(f"spec {args.id} is {spec.status}: the owner must unfreeze it before dropping it")
        return 1
    specs.set_status(spec, new)
    print(f"spec {args.id}: status {new}")
    return 0


def cmd_trace(args) -> int:
    from agentkit import trace
    cfg = load_config()
    code, lines = trace._trace_command(cfg, args.spec)
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
    inst.add_argument("--models", choices=["tool", "kit"])
    inst.set_defaults(func=cmd_install)

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

    ss = sub.add_parser("spec-status", help="set a spec's phase (005)")
    ss.add_argument("id")
    ss.add_argument("status")
    ss.set_defaults(func=cmd_spec_status)

    tr = sub.add_parser("trace", help="requirement traceability (005)")
    tr.add_argument("--spec")
    tr.set_defaults(func=cmd_trace)

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
