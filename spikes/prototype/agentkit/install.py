"""`agentkit install` / `update` / `sync`.

File modes:
  once     written only when missing (agentkit.toml, lock, log)
  managed  3-way: overwritten only when the user did not modify it since the last install,
           otherwise the new version is written next to it as `<file>.agentkit-new`
  block    only the region between agentkit markers is managed (AGENTS.md, CLAUDE.md, .gitignore)
  derived  generated from neutral sources in the repo by `sync`; always overwritten, drift-checked
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
from dataclasses import dataclass, field
from pathlib import Path

from . import __version__
from .config import CONFIG_NAME, KIT_ROOT, Config, load_config, load_profile
from .util import git, is_git_repo, sha256_bytes, write_bytes

MANIFEST = ".agentkit/manifest.json"
KIT_DIRS = ("agentkit", "profiles", "workflow", "skills", "adapters", "githooks", "ci")
MD_MARKERS = ("<!-- agentkit:begin (managed by agentkit; edit outside this block) -->", "<!-- agentkit:end -->")
HASH_MARKERS = ("# agentkit:begin (managed by agentkit)", "# agentkit:end")
KNOWN_ADAPTERS = ("claude-code", "codex", "opencode", "deepseek-harness", "pi")
KNOWN_CI = ("github", "gitlab", "none")
_VAR_RX = re.compile(r"\{\{([a-z_][a-z0-9_.-]*)\}\}")


@dataclass
class Planned:
    path: str
    content: bytes
    mode: str  # once | managed | block | derived
    initial: bytes | None = None  # block mode: whole file when it does not exist yet
    markers: tuple[str, str] = MD_MARKERS
    placement: str = "bottom"  # block mode, existing file without markers: top | bottom
    executable: bool = False


@dataclass
class Report:
    written: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    drift: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        out = []
        for label, items in (
            ("written", self.written),
            ("conflict (new version saved as .agentkit-new)", self.conflicts),
            ("skipped (deleted by you)", self.skipped),
            ("removed", self.removed),
            ("drift", self.drift),
        ):
            if items:
                out.append(f"{label}: {len(items)}")
                out.extend(f"  {p}" for p in items[:40])
        out.extend(self.notes)
        return out


# -- rendering ---------------------------------------------------------------------


def render(text: str, ctx: dict) -> str:
    return _VAR_RX.sub(lambda m: str(ctx[m.group(1)]) if m.group(1) in ctx else m.group(0), text)


def context(cfg: Config) -> dict:
    prof = cfg.profile
    ctx = {
        "kit_version": __version__,
        "profile": prof.get("name", "generic"),
        "python": cfg.python_cmd,
        "launcher": ".agentkit/bin/agentkit",
        "lock": cfg.lock_rel,
        "unfreeze_log": cfg.unfreeze_log_rel,
        "specs": cfg.path("specs"),
        "codemap": cfg.path("codemap"),
        "test_cmd": prof.get("test_cmd", ""),
        "test_one_cmd": prof.get("test_one_cmd", ""),
        "req_id_example": "R001-01",
        "ci_setup": prof.get("ci_setup", "").rstrip("\n"),
        "frozen_globs": ", ".join(f"`{g}`" for g in cfg.frozen_globs),
    }
    for tier, model in cfg.models().items():
        ctx[f"model_{tier}"] = model
    return ctx


def read_src(src: Path, rel: str) -> str:
    return (src / rel).read_text(encoding="utf-8").replace("\r\n", "\n")


# -- planning ----------------------------------------------------------------------


def toml_list(items) -> str:
    return "[" + ", ".join(json.dumps(i) for i in items) + "]"


def plan_kit(cfg: Config, src: Path, ci: str = "github", owner: str = "") -> list[Planned]:
    """Files installed from the kit (install/update)."""
    ctx = context(cfg)
    out: list[Planned] = []
    tdir = "workflow/templates"
    out.append(Planned(cfg.lock_rel, b'{\n  "version": 1,\n  "algorithm": "sha256-lf",\n  "files": {}\n}\n', "once"))
    out.append(Planned(cfg.unfreeze_log_rel, read_src(src, "workflow/templates/unfreeze-log.md").encode(), "once"))
    out.append(Planned(f"{cfg.path('specs')}/README.md", render(read_src(src, f"{tdir}/specs-README.md"), ctx).encode(), "once"))
    agents_tmpl = render(read_src(src, f"{tdir}/AGENTS.md.tmpl"), ctx)
    out.append(_block_from_template("AGENTS.md", agents_tmpl, MD_MARKERS, "bottom"))
    out.append(
        Planned(
            ".gitignore",
            ".agentkit/state/\n__pycache__/\n*.agentkit-new\n".encode(),
            "block",
            markers=HASH_MARKERS,
        )
    )
    # skills: neutral sources live in the repo; kit skills are managed copies
    skills_rel = cfg.path("skills")
    for skill_dir in sorted((src / "skills").iterdir()) if (src / "skills").is_dir() else []:
        if not skill_dir.is_dir():
            continue
        for f in sorted(skill_dir.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts:
                rel = f.relative_to(src / "skills").as_posix()
                out.append(Planned(f"{skills_rel}/{rel}", render(read_src(src, f"skills/{rel}"), ctx).encode(), "managed"))
    for hook in ("pre-commit", "commit-msg"):
        out.append(Planned(f".githooks/{hook}", read_src(src, f"githooks/{hook}").encode(), "managed", executable=True))
    if ci == "github":
        out.append(Planned(".github/workflows/agentkit.yml", render(read_src(src, "ci/github-actions.yml"), ctx).encode(), "managed"))
    elif ci == "gitlab":
        out.append(Planned(".gitlab/agentkit.gitlab-ci.yml", render(read_src(src, "ci/gitlab-ci.yml"), ctx).encode(), "managed"))
    if owner:
        body = f"/{cfg.lock_rel} {owner}\n/{cfg.unfreeze_log_rel} {owner}\n/.agentkit/ {owner}\n/.githooks/ {owner}\n"
        body += "".join(f"/{g} {owner}\n" for g in cfg.frozen_globs)
        out.append(Planned(".github/CODEOWNERS", body.encode(), "block", markers=HASH_MARKERS))
    from . import adapters

    for name in cfg.adapters:
        out.extend(adapters.kit_files(name, cfg, src, ctx))
    return out


def plan_derived(cfg: Config) -> list[Planned]:
    """Per-tool copies generated from the repo's neutral sources (sync)."""
    from . import adapters

    ctx = context(cfg)
    out: list[Planned] = []
    for name in cfg.adapters:
        out.extend(adapters.derived_files(name, cfg, ctx))
    return out


def _block_from_template(path: str, template: str, markers, placement: str) -> Planned:
    begin, end = markers
    if begin in template and end in template:
        inner = template.split(begin, 1)[1].split(end, 1)[0].strip("\n") + "\n"
    else:
        inner = template
    return Planned(path, inner.encode(), "block", initial=template.encode(), markers=markers, placement=placement)


# -- applying ----------------------------------------------------------------------


def load_manifest(root: Path) -> dict:
    p = root / MANIFEST
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"kit_version": None, "files": {}}


def save_manifest(root: Path, manifest: dict) -> None:
    manifest["files"] = dict(sorted(manifest["files"].items()))
    write_bytes(root / MANIFEST, (json.dumps(manifest, indent=2) + "\n").encode())


def _set_exec(p: Path) -> None:
    try:
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass


def _apply_block(p: Path, item: Planned) -> bytes:
    begin, end = item.markers
    inner = item.content.decode()
    block = f"{begin}\n{inner.rstrip(chr(10))}\n{end}"
    if not p.is_file():
        if item.initial is not None:
            return item.initial
        return (block + "\n").encode()
    text = p.read_text(encoding="utf-8").replace("\r\n", "\n")
    if begin in text and end in text:
        pre, rest = text.split(begin, 1)
        _, post = rest.split(end, 1)
        return (pre + block + post).encode()
    if item.placement == "top":
        return (block + "\n\n" + text.lstrip("\n")).encode()
    return (text.rstrip("\n") + "\n\n" + block + "\n").encode()


def apply(root: Path, planned: list[Planned], manifest: dict, force: bool = False, check: bool = False,
          derived_scope: bool = False) -> Report:
    rep = Report()
    files = manifest.setdefault("files", {})
    planned_paths = set()
    for item in planned:
        planned_paths.add(item.path)
        p = root / item.path
        cur_bytes = p.read_bytes() if p.is_file() else None
        cur = sha256_bytes(cur_bytes) if cur_bytes is not None else None
        if item.mode == "once":
            if cur is None and not check:
                write_bytes(p, item.content)
                rep.written.append(item.path)
            continue
        if item.mode == "block":
            new_bytes = _apply_block(p, item)
            if cur_bytes is not None and sha256_bytes(new_bytes) == cur:
                rep.unchanged.append(item.path)
            elif check:
                rep.drift.append(item.path)
            else:
                write_bytes(p, new_bytes)
                rep.written.append(item.path)
            files[item.path] = {"sha256": sha256_bytes(item.content), "mode": "block"}
            continue
        new = sha256_bytes(item.content)
        if item.mode == "derived":
            if cur == new:
                rep.unchanged.append(item.path)
            elif check:
                rep.drift.append(item.path)
            else:
                write_bytes(p, item.content)
                rep.written.append(item.path)
            if not check:
                files[item.path] = {"sha256": new, "mode": "derived"}
            continue
        # managed
        base = files.get(item.path, {}).get("sha256")
        if cur == new:
            rep.unchanged.append(item.path)
        elif check:
            rep.drift.append(item.path)
            continue
        elif cur is None:
            if base is not None and not force:
                rep.skipped.append(item.path)
                continue
            write_bytes(p, item.content)
            rep.written.append(item.path)
        elif force or (base is not None and cur == base):
            write_bytes(p, item.content)
            rep.written.append(item.path)
        else:
            write_bytes(p.with_name(p.name + ".agentkit-new"), item.content)
            rep.conflicts.append(item.path)
            continue
        if item.executable:
            _set_exec(p)
        files[item.path] = {"sha256": new, "mode": "managed"}
    if derived_scope:
        for path, meta in list(files.items()):
            if meta.get("mode") == "derived" and path not in planned_paths:
                p = root / path
                if check:
                    if p.exists():
                        rep.drift.append(path + " (stale)")
                    continue
                if p.is_file() and sha256_bytes(p.read_bytes()) == meta["sha256"]:
                    p.unlink()
                    _prune_empty(p.parent, root)
                    rep.removed.append(path)
                del files[path]
    return rep


def _prune_empty(d: Path, root: Path) -> None:
    while d != root and d.is_dir() and not any(d.iterdir()):
        d.rmdir()
        d = d.parent


# -- kit copy ----------------------------------------------------------------------


def copy_kit(src: Path, target: Path) -> None:
    dest = target / ".agentkit"
    if src.resolve() == dest.resolve():
        return
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")
    for d in KIT_DIRS:
        if (dest / d).exists():
            shutil.rmtree(dest / d)
        if (src / d).is_dir():
            shutil.copytree(src / d, dest / d, ignore=ignore)
    write_launchers(dest)
    readme = dest / "README.md"
    readme.write_text(
        "# .agentkit\n\nInstalled copy of the agentic workflow kit (v" + __version__ + "). Do not edit: "
        "run `agentkit update --kit <path>` to upgrade. `state/` is local and git-ignored.\n",
        encoding="utf-8",
    )


LAUNCHER = '''#!/usr/bin/env python3
"""agentkit launcher: `python .agentkit/bin/agentkit <command>` (any OS)."""
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
_kit = os.path.dirname(_here)
_root = os.path.dirname(_kit)
for _candidate in (_kit, _root):
    if os.path.isfile(os.path.join(_candidate, "agentkit", "cli.py")):
        sys.path.insert(0, _candidate)
        break
os.environ["AGENTKIT_ROOT"] = _root
from agentkit.cli import main  # noqa: E402

sys.exit(main())
'''

LAUNCHER_CMD = '@echo off\r\npython "%~dp0agentkit" %*\r\n'


def write_launchers(kit_dir: Path) -> None:
    b = kit_dir / "bin"
    b.mkdir(parents=True, exist_ok=True)
    with open(b / "agentkit", "w", encoding="utf-8", newline="\n") as f:
        f.write(LAUNCHER)
    _set_exec(b / "agentkit")
    with open(b / "agentkit.cmd", "w", encoding="utf-8", newline="") as f:
        f.write(LAUNCHER_CMD)


# -- config file -------------------------------------------------------------------


def render_config(src: Path, profile: str, adapters: list[str], ci: str, python: str, self_hosted: bool) -> str:
    text = read_src(src, "workflow/templates/agentkit.toml.tmpl")
    return render(
        text,
        {
            "kit_version": __version__,
            "profile": profile,
            "adapters": toml_list(adapters),
            "ci": ci,
            "python": python,
            "self_hosted": "true" if self_hosted else "false",
        },
    )


def _update_config_list(path: Path, key: str, values: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    new, n = re.subn(rf"(?m)^{key}\s*=\s*\[[^\]]*\]", f"{key} = {toml_list(values)}", text, count=1)
    if n:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(new)


def default_python() -> str:
    return "python" if os.name == "nt" else "python3"


# -- entry points --------------------------------------------------------------------


def install(target: Path, profile: str | None = None, adapters: list[str] | None = None, ci: str | None = None,
            owner: str = "", python: str | None = None, src: Path = KIT_ROOT, force: bool = False,
            self_hosted: bool = False, configure_git: bool = True) -> Report:
    target = target.resolve()
    if not target.is_dir():
        raise SystemExit(f"target directory does not exist: {target}")
    for a in adapters or []:
        if a not in KNOWN_ADAPTERS:
            raise SystemExit(f"unknown adapter {a}; expected one of {', '.join(KNOWN_ADAPTERS)}")
    if ci and ci not in KNOWN_CI:
        raise SystemExit(f"unknown --ci {ci}; expected one of {', '.join(KNOWN_CI)}")
    if self_hosted and src.resolve() != target:
        raise SystemExit("--self only makes sense when installing the kit into its own repository")
    cfg_path = target / CONFIG_NAME
    if cfg_path.is_file():
        cfg = load_config(root=target)
        if adapters:
            merged = list(dict.fromkeys(cfg.adapters + adapters))
            if merged != cfg.adapters:
                _update_config_list(cfg_path, "adapters", merged)
        cfg = load_config(root=target)
        ci = ci or cfg.kit.get("ci", "github")
    else:
        profile = profile or "generic"
        load_profile(profile, None)  # validate early
        text = render_config(src, profile, adapters or [], ci or "github", python or default_python(), self_hosted)
        write_bytes(cfg_path, text.encode())
        cfg = load_config(root=target)
        ci = ci or "github"
    if "deepseek-harness" in cfg.adapters and "codex" not in cfg.adapters:
        _update_config_list(cfg_path, "adapters", cfg.adapters + ["codex"])
        cfg = load_config(root=target)
    if not cfg.self_hosted:
        copy_kit(src, target)
        cfg = load_config(root=target)
    else:
        write_launchers(target / ".agentkit")
    manifest = load_manifest(target)
    rep = apply(target, plan_kit(cfg, src, ci=ci, owner=owner), manifest, force=force)
    drep = apply(target, plan_derived(cfg), manifest, force=force, derived_scope=True)
    rep.written += drep.written
    rep.removed += drep.removed
    manifest["kit_version"] = __version__
    save_manifest(target, manifest)
    if configure_git and is_git_repo(target):
        git(target, "config", "core.hooksPath", ".githooks")
        rep.notes.append("git: core.hooksPath -> .githooks")
    elif configure_git:
        rep.notes.append("not a git repository: run `git init` then `git config core.hooksPath .githooks`")
    from . import adapters as adapters_mod

    for name in cfg.adapters:
        rep.notes.extend(adapters_mod.post_install_notes(name))
    return rep


def update(root: Path, src: Path, force: bool = False) -> Report:
    cfg = load_config(root=root)
    return install(root, src=src, force=force, self_hosted=cfg.self_hosted)


def sync(cfg: Config, check: bool = False) -> Report:
    manifest = load_manifest(cfg.root)
    rep = apply(cfg.root, plan_derived(cfg), manifest, check=check, derived_scope=True)
    if not check:
        save_manifest(cfg.root, manifest)
    return rep
