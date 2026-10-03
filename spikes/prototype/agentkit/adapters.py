"""Adapters: wire the neutral sources (AGENTS.md, .agents/skills, roles, the agentkit CLI)
into each agent tool. Templates live in `adapters/<name>/` of the kit."""

from __future__ import annotations

import json
from pathlib import Path

from .config import DEFAULT_MODELS, Config
from .install import HASH_MARKERS, MD_MARKERS, Planned, _block_from_template, read_src, render
from .util import dump_front_matter, parse_front_matter

PLACEHOLDER_MODELS = set(DEFAULT_MODELS.values())

# neutral capability -> tool names
CLAUDE_TOOLS = {"read": ["Read", "Grep", "Glob"], "edit": ["Edit", "Write"], "shell": ["Bash", "PowerShell"]}


# -- neutral sources ------------------------------------------------------------------


def load_roles(cfg: Config) -> list[dict]:
    """Kit roles (workflow/roles) overlaid by project roles (`[paths] roles`, default `roles/`)."""
    roles: dict[str, dict] = {}
    for d in (cfg.kit_source / "workflow" / "roles", cfg.root / cfg.path("roles")):
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            meta, body = parse_front_matter(f.read_text(encoding="utf-8").replace("\r\n", "\n"))
            if not meta.get("name"):
                continue
            roles[meta["name"]] = {"meta": meta, "body": body.strip("\n") + "\n"}
    return [roles[k] for k in sorted(roles)]


def load_skills(cfg: Config) -> list[tuple[str, Path]]:
    d = cfg.root / cfg.path("skills")
    if not d.is_dir():
        return []
    return [(s.name, s) for s in sorted(d.iterdir()) if (s / "SKILL.md").is_file()]


def _tools(meta: dict) -> list[str]:
    t = meta.get("tools", ["read"])
    return t if isinstance(t, list) else [x.strip() for x in str(t).split(",") if x.strip()]


def _model(cfg: Config, adapter: str, tier: str | None) -> str | None:
    if not tier:
        return None
    m = cfg.models(adapter).get(tier)
    return None if not m or m in PLACEHOLDER_MODELS else m


def _bool(v) -> bool:
    return str(v).strip().lower() in ("true", "yes", "on", "1")


# -- dispatch ----------------------------------------------------------------------------


def kit_files(name: str, cfg: Config, src: Path, ctx: dict) -> list[Planned]:
    return {
        "claude-code": claude_kit,
        "codex": codex_kit,
        "opencode": opencode_kit,
        "deepseek-harness": dsh_kit,
        "pi": pi_kit,
    }[name](cfg, src, ctx)


def derived_files(name: str, cfg: Config, ctx: dict) -> list[Planned]:
    fn = {
        "claude-code": claude_derived,
        "codex": codex_derived,
        "opencode": opencode_derived,
    }.get(name)
    return fn(cfg, ctx) if fn else []


def post_install_notes(name: str) -> list[str]:
    return {
        "codex": ["codex: run `/hooks` once in Codex and trust the project hooks, or they will not run"],
        "deepseek-harness": [
            "deepseek-harness: add the plugin block from .agentkit/adapters/deepseek-harness/profile.yml to your dsh profile",
        ],
        "pi": ["pi: accept project trust when Pi asks, so .pi/extensions/agentkit.ts loads"],
    }.get(name, [])


# -- Claude Code ----------------------------------------------------------------------------


def claude_kit(cfg: Config, src: Path, ctx: dict) -> list[Planned]:
    base = "adapters/claude-code"
    settings = json.loads(render(read_src(src, f"{base}/settings.json.tmpl"), ctx))
    deny = settings["permissions"]["deny"]
    for g in cfg.profile.get("build_output_globs", []):
        rule = f"Read({g})"
        if rule not in deny:
            deny.append(rule)
    out = [Planned(".claude/settings.json", (json.dumps(settings, indent=2) + "\n").encode(), "managed")]
    claude_md = render(read_src(src, f"{base}/CLAUDE.md.tmpl"), ctx)
    out.append(_block_from_template("CLAUDE.md", claude_md, MD_MARKERS, "top"))
    out.append(Planned(".gitignore", b".claude/settings.local.json\n", "block",
                       markers=("# agentkit:begin claude-code", "# agentkit:end claude-code")))
    return out


def claude_skill(cfg: Config, skill_dir: Path) -> list[tuple[str, bytes]]:
    files = []
    for f in sorted(skill_dir.rglob("*")):
        if not f.is_file() or "__pycache__" in f.parts:
            continue
        rel = f.relative_to(skill_dir).as_posix()
        data = f.read_bytes()
        if rel == "SKILL.md":
            meta, body = parse_front_matter(data.decode("utf-8").replace("\r\n", "\n"))
            extra = meta.pop("metadata", {}) or {}
            if not isinstance(extra, dict):
                extra = {}
            out = {"name": meta.get("name", skill_dir.name), "description": meta.get("description", "")}
            for k in ("license", "compatibility", "allowed-tools"):
                if k in meta:
                    out[k] = meta[k]
            if _bool(extra.get("agentkit-user-only", "false")):
                out["disable-model-invocation"] = True
            if extra.get("agentkit-args"):
                out["argument-hint"] = extra["agentkit-args"]
            model = _model(cfg, "claude-code", extra.get("agentkit-tier"))
            if model:
                out["model"] = model
            if extra.get("agentkit-effort"):
                out["effort"] = extra["agentkit-effort"]
            note = f"<!-- generated by agentkit sync from {cfg.path('skills')}/{skill_dir.name}; edit the source -->\n"
            data = (dump_front_matter(out) + note + body.lstrip("\n")).encode()
        files.append((rel, data))
    return files


def claude_derived(cfg: Config, ctx: dict) -> list[Planned]:
    out = []
    for name, d in load_skills(cfg):
        for rel, data in claude_skill(cfg, d):
            out.append(Planned(f".claude/skills/{name}/{rel}", data, "derived"))
    for role in load_roles(cfg):
        meta = role["meta"]
        tools = []
        for cap in _tools(meta):
            tools.extend(CLAUDE_TOOLS.get(cap, []))
        fm = {"name": meta["name"], "description": meta.get("description", "")}
        if tools:
            fm["tools"] = ", ".join(tools)
        model = _model(cfg, "claude-code", meta.get("tier"))
        if model:
            fm["model"] = model
        if meta.get("effort"):
            fm["effort"] = meta["effort"]
        text = dump_front_matter(fm) + "<!-- generated by agentkit sync from roles; edit the role source -->\n\n" + role["body"]
        out.append(Planned(f".claude/agents/{meta['name']}.md", text.encode(), "derived"))
    return out


# -- Codex CLI -------------------------------------------------------------------------------


def codex_kit(cfg: Config, src: Path, ctx: dict) -> list[Planned]:
    base = "adapters/codex"
    return [
        Planned(".codex/hooks.json", render(read_src(src, f"{base}/hooks.json.tmpl"), ctx).encode(), "managed"),
        Planned(".codex/config.toml", render(read_src(src, f"{base}/config.toml.tmpl"), ctx).encode(), "managed"),
    ]


def _toml_str(s: str) -> str:
    if "'''" not in s:
        return "'''\n" + s + "'''"
    return json.dumps(s)


def codex_derived(cfg: Config, ctx: dict) -> list[Planned]:
    out = []
    effort_map = {"low": "low", "medium": "medium", "high": "high", "xhigh": "high", "max": "high"}
    for role in load_roles(cfg):
        meta = role["meta"]
        name = meta["name"].replace("-", "_")
        caps = _tools(meta)
        lines = [
            "# generated by agentkit sync from roles; edit the role source",
            f"name = {json.dumps(name)}",
            f"description = {json.dumps(meta.get('description', ''))}",
        ]
        model = _model(cfg, "codex", meta.get("tier"))
        if model:
            lines.append(f"model = {json.dumps(model)}")
        if meta.get("effort"):
            lines.append(f"model_reasoning_effort = {json.dumps(effort_map.get(meta['effort'], 'medium'))}")
        sandbox = "workspace-write" if ("edit" in caps or "shell" in caps) else "read-only"
        lines.append(f"sandbox_mode = {json.dumps(sandbox)}")
        lines.append("developer_instructions = " + _toml_str(role["body"]))
        out.append(Planned(f".codex/agents/{name}.toml", ("\n".join(lines) + "\n").encode(), "derived"))
    return out


# -- OpenCode --------------------------------------------------------------------------------


def opencode_kit(cfg: Config, src: Path, ctx: dict) -> list[Planned]:
    base = "adapters/opencode"
    return [
        Planned(".opencode/plugins/agentkit.ts", render(read_src(src, f"{base}/agentkit.ts.tmpl"), ctx).encode(), "managed"),
        Planned("opencode.json", render(read_src(src, f"{base}/opencode.json.tmpl"), ctx).encode(), "managed"),
    ]


def opencode_derived(cfg: Config, ctx: dict) -> list[Planned]:
    # Skills: OpenCode reads .agents/skills natively, no copy needed.
    out = []
    for role in load_roles(cfg):
        meta = role["meta"]
        caps = _tools(meta)
        lines = ["---", f"description: {json.dumps(meta.get('description', ''))}", "mode: subagent"]
        model = _model(cfg, "opencode", meta.get("tier"))
        if model:
            lines.append(f"model: {model}")
        perms = {"edit": "allow" if "edit" in caps else "deny", "bash": "allow" if "shell" in caps else "deny"}
        lines.append("permission:")
        lines.extend(f"  {k}: {v}" for k, v in perms.items())
        lines.append("---")
        text = "\n".join(lines) + "\n<!-- generated by agentkit sync from roles; edit the role source -->\n\n" + role["body"]
        out.append(Planned(f".opencode/agents/{meta['name']}.md", text.encode(), "derived"))
    return out


# -- DeepSeek Harness ---------------------------------------------------------------------------


def dsh_kit(cfg: Config, src: Path, ctx: dict) -> list[Planned]:
    # Reuses .codex/hooks.json through the dsh-hooks-codex bridge (codex adapter is required).
    # The profile snippet ships in .agentkit/adapters/deepseek-harness/profile.yml.
    return []


# -- Pi --------------------------------------------------------------------------------------------


def pi_kit(cfg: Config, src: Path, ctx: dict) -> list[Planned]:
    base = "adapters/pi"
    return [Planned(".pi/extensions/agentkit.ts", render(read_src(src, f"{base}/agentkit.ts.tmpl"), ctx).encode(), "managed")]


__all__ = ["kit_files", "derived_files", "post_install_notes", "load_roles", "load_skills", "HASH_MARKERS"]
