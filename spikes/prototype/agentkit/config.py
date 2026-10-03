"""Load `agentkit.toml` and the language profile it names."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import __version__

CONFIG_NAME = "agentkit.toml"
KIT_PACKAGE_DIR = Path(__file__).resolve().parent
KIT_ROOT = KIT_PACKAGE_DIR.parent

DEFAULT_PATHS = {
    "specs": "specs",
    "lock": "tests.lock.json",
    "unfreeze_log": "tests.unfreeze-log.md",
    "codemap": "docs/CODEMAP.md",
    "skills": ".agents/skills",
    "roles": "roles",
}

DEFAULT_MODELS = {"strong": "strong", "standard": "standard", "fast": "fast"}

# Per-adapter defaults; `[models.<adapter>]` in agentkit.toml overrides them.
ADAPTER_MODEL_DEFAULTS = {
    "claude-code": {"strong": "opus", "standard": "sonnet", "fast": "haiku"},
}

DEFAULT_BUDGETS = {
    "agents_md_lines": 150,
    "claude_md_lines": 40,
    "skill_md_lines": 500,
    "skill_description_chars": 200,
    "rule_md_lines": 80,
    "duplicate_min_lines": 3,
    "always_loaded_tokens": 3000,
}

DEFAULT_PROFILE = {
    "name": "generic",
    "test_cmd": "",
    "test_cmd_windows": "",
    "test_one_cmd": "",
    "test_one_cmd_windows": "",
    "junit_report_glob": [],
    "output_filter_regex": r"(?i)(error|fail|assert)",
    "error_line_regex": r"(?i)(error|exception)",
    "frozen_globs": ["tests/**", "test/**"],
    "test_globs": [],
    "source_globs": [],
    "build_output_globs": ["**/build/**", "**/dist/**", "**/node_modules/**", "**/__pycache__/**"],
    "req_id_regex": r"\bR(\d{3})[-_](\d{2,3})\b",
    "format_cmd": "",
    "lint_cmd": "",
    "ci_setup": "",
    "codemap": {"symbol_regexes": []},
}

# Guard defaults (protected paths beyond the frozen set).
GUARD_DENY = [".agentkit/**", "agentkit.toml"]
GUARD_ASK = [
    ".claude/settings.json",
    ".codex/hooks.json",
    ".codex/config.toml",
    ".opencode/plugins/**",
    "opencode.json",
    ".pi/**",
    ".githooks/**",
    ".github/workflows/**",
    ".gitlab-ci.yml",
    "CODEOWNERS",
    ".github/CODEOWNERS",
]
GUARD_STATE_ALLOW = [".agentkit/state/**"]


class ConfigError(Exception):
    pass


@dataclass
class Config:
    root: Path
    data: dict
    profile: dict
    kit_source: Path = field(default=KIT_ROOT)

    # -- paths -------------------------------------------------------------
    def path(self, key: str) -> str:
        return self.data.get("paths", {}).get(key, DEFAULT_PATHS[key])

    @property
    def lock_rel(self) -> str:
        return self.path("lock")

    @property
    def unfreeze_log_rel(self) -> str:
        return self.path("unfreeze_log")

    @property
    def lock_path(self) -> Path:
        return self.root / self.lock_rel

    @property
    def unfreeze_log_path(self) -> Path:
        return self.root / self.unfreeze_log_rel

    @property
    def specs_dir(self) -> Path:
        return self.root / self.path("specs")

    @property
    def state_dir(self) -> Path:
        return self.root / ".agentkit" / "state"

    # -- kit settings ------------------------------------------------------
    @property
    def kit(self) -> dict:
        return self.data.get("kit", {})

    @property
    def adapters(self) -> list[str]:
        return list(self.kit.get("adapters", []))

    @property
    def python_cmd(self) -> str:
        return self.kit.get("python") or ("python" if os.name == "nt" else "python3")

    @property
    def self_hosted(self) -> bool:
        """The kit repo installs itself: the package lives at the repo root, not in .agentkit/."""
        return bool(self.kit.get("self_hosted", False))

    def models(self, adapter: str | None = None) -> dict:
        """Tier -> model string. Generic `[models]` first, then the adapter's own defaults/table,
        because a generic model name rarely works inside a vendor-specific tool."""
        m = dict(DEFAULT_MODELS)
        raw = self.data.get("models", {})
        m.update({k: v for k, v in raw.items() if isinstance(v, str)})
        m.update(ADAPTER_MODEL_DEFAULTS.get(adapter or "", {}))
        if adapter and isinstance(raw.get(adapter), dict):
            m.update(raw[adapter])
        return m

    @property
    def budgets(self) -> dict:
        b = dict(DEFAULT_BUDGETS)
        b.update(self.data.get("budgets", {}))
        return b

    @property
    def guard(self) -> dict:
        g = self.data.get("guard", {})
        return {
            "deny_globs": GUARD_DENY + [self.lock_rel, self.unfreeze_log_rel] + list(g.get("deny_globs", [])),
            "ask_globs": GUARD_ASK + list(g.get("ask_globs", [])),
            "allow_globs": GUARD_STATE_ALLOW + list(g.get("allow_globs", [])),
            "deny_build_output_reads": bool(g.get("deny_build_output_reads", True)),
        }

    # -- profile -----------------------------------------------------------
    @property
    def frozen_globs(self) -> list[str]:
        return list(self.profile["frozen_globs"])

    @property
    def test_globs(self) -> list[str]:
        return list(self.profile.get("test_globs") or self.profile["frozen_globs"])


def find_root(start: Path | None = None) -> Path | None:
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / CONFIG_NAME).is_file():
            return candidate
    return None


def profile_search_dirs(root: Path | None) -> list[Path]:
    dirs = []
    if root is not None:
        dirs.append(root / ".agentkit" / "profiles")
        dirs.append(root / "profiles")
    dirs.append(KIT_ROOT / "profiles")
    return dirs


def load_profile(name: str, root: Path | None = None) -> dict:
    for d in profile_search_dirs(root):
        f = d / f"{name}.toml"
        if f.is_file():
            with open(f, "rb") as fh:
                raw = tomllib.load(fh)
            return merge_profile(DEFAULT_PROFILE, raw)
    raise ConfigError(f"profile '{name}' not found (looked in: {', '.join(str(d) for d in profile_search_dirs(root))})")


def merge_profile(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            merged = dict(out[k])
            merged.update(v)
            out[k] = merged
        else:
            out[k] = v
    return out


def load_config(start: Path | None = None, root: Path | None = None) -> Config:
    root = root or find_root(start)
    if root is None:
        raise ConfigError(f"no {CONFIG_NAME} found from {start or Path.cwd()} upwards; run `agentkit install` first")
    with open(root / CONFIG_NAME, "rb") as fh:
        data = tomllib.load(fh)
    name = data.get("kit", {}).get("profile", "generic")
    profile = merge_profile(load_profile(name, root), data.get("profile", {}))
    source = root if data.get("kit", {}).get("self_hosted") else root / ".agentkit"
    if not (source / "agentkit").is_dir():
        source = KIT_ROOT
    return Config(root=root, data=data, profile=profile, kit_source=source)


def kit_version() -> str:
    return __version__
