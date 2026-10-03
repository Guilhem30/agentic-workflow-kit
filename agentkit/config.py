"""Configuration, profiles, globs and model tiers (spec 001)."""
from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_NAME = "agentkit.toml"
TIERS = ("strong", "standard", "fast")
TIER_EFFORT = {"strong": "high", "standard": "medium", "fast": "low"}

MODELS_HELP = """\
--models tool|kit decides who picks the model for each skill and subagent:
  kit   (recommended) agentkit routes by tier: the strongest model writes and audits tests
  tool  the agent tool picks, as without agentkit; no model or effort is written
Nobody types model names.
"""

PATH_DEFAULTS = {
    "specs": "specs",
    "lock": "tests.lock.json",
    "unfreeze_log": "tests.unfreeze-log.md",
    "codemap": "docs/CODEMAP.md",
    "skills": ".agents/skills",
    "roles": "roles",
}

DEFAULT_REQ_ID_REGEX = r"(?<![A-Za-z0-9])R(\d{3})[-_](\d{2})(?!\d)"

PROFILE_DEFAULTS = {
    "test_cmd": "",
    "test_cmd_windows": "",
    "test_one_cmd": "",
    "test_one_cmd_windows": "",
    "junit_report_glob": [],
    "frozen_globs": ["tests/**", "test/**"],
    "source_globs": [],
    "build_output_globs": ["**/build/**", "**/dist/**", "**/node_modules/**", "**/__pycache__/**"],
    "req_id_regex": DEFAULT_REQ_ID_REGEX,
    "output_filter_regex": "",
    "format_cmd": "",
    "lint_cmd": "",
    "ci_setup": "",
    "codemap": {"symbol_regexes": []},
}

BUILTIN_MODELS = {
    "claude-code": {"strong": "opus", "standard": "sonnet", "fast": "haiku"},
    # Unverified placeholders: 013 checks them against the Codex docs and records the date
    # in adapters/README.md (R001-18).
    "codex": {"strong": "gpt-5-codex", "standard": "gpt-5-codex", "fast": "gpt-5-codex-mini"},
}

CI_PROVIDERS = ("github", "gitlab")
CI_OS = ("linux", "windows", "macos")
MODEL_MODES = ("tool", "kit")


class ConfigError(Exception):
    """A configuration problem. The CLI reports it and exits 2."""


@dataclass
class Config:
    root: Path
    data: dict
    profile: dict
    kit_source: Path

    def path(self, key: str) -> str:
        value = self.data.get("paths", {}).get(key)
        return value if isinstance(value, str) and value else PATH_DEFAULTS[key]

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

    @property
    def adapters(self) -> list[str]:
        return list(self.data.get("kit", {}).get("adapters", []))

    @property
    def python_cmd(self) -> str:
        value = self.data.get("kit", {}).get("python")
        if value:
            return value
        return "python" if os.name == "nt" else "python3"

    @property
    def self_hosted(self) -> bool:
        return bool(self.data.get("kit", {}).get("self_hosted", False))

    def models(self, adapter: str) -> dict[str, str]:
        models = self.data.get("models", {})
        if models.get("mode", "tool") != "kit":
            return {}
        resolved = dict(BUILTIN_MODELS.get(adapter, {}))
        override = models.get(adapter)
        if isinstance(override, dict):
            for tier in TIERS:
                if isinstance(override.get(tier), str) and override[tier]:
                    resolved[tier] = override[tier]
        return {tier: resolved[tier] for tier in TIERS if tier in resolved}

    @property
    def budgets(self) -> dict:
        return dict(self.data.get("budgets", {}))

    @property
    def guard(self) -> dict:
        return dict(self.data.get("guard", {}))

    @property
    def frozen_globs(self) -> list[str]:
        return list(self.profile["frozen_globs"])

    @property
    def test_globs(self) -> list[str]:
        return list(self.profile["test_globs"])


def find_root(start: Path | None = None) -> Path | None:
    env = os.environ.get("AGENTKIT_ROOT")
    if env and (Path(env) / CONFIG_NAME).is_file():
        return Path(env).resolve()
    here = Path(start or Path.cwd()).resolve()
    for d in (here, *here.parents):
        if (d / CONFIG_NAME).is_file():
            return d
    return None


def _kit_source() -> Path:
    return Path(__file__).resolve().parent.parent


def _profile_dirs(root: Path | None) -> list[Path]:
    dirs = []
    if root is not None:
        dirs += [root / ".agentkit" / "profiles", root / "profiles"]
    dirs.append(_kit_source() / "profiles")
    return dirs


def _read_toml(path: Path) -> dict:
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except UnicodeDecodeError:
        raise ConfigError(f"{path}: not valid UTF-8") from None
    except OSError as exc:
        raise ConfigError(f"{path}: cannot be read ({exc.strerror or exc})") from None
    except tomllib.TOMLDecodeError as exc:
        msg = str(exc)
        m = re.search(r"line (\d+), column (\d+)", msg)
        where = f"line {m.group(1)}, column {m.group(2)}" if m else "unknown position"
        raise ConfigError(f"{path}: invalid TOML at {where}: {msg}") from None


def load_profile(name: str, root: Path | None = None) -> dict:
    dirs = _profile_dirs(root)
    for d in dirs:
        candidate = d / f"{name}.toml"
        if candidate.is_file():
            return _read_toml(candidate)
    searched = ", ".join(d.as_posix() for d in dirs)
    raise ConfigError(f"profile {name!r} not found; searched: {searched}")


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = {**out[key], **value}
        else:
            out[key] = value
    return out


def _check_ci(data: dict) -> None:
    ci = data.get("ci")
    if ci is None:
        return
    if not isinstance(ci, dict):
        raise ConfigError("ci: must be a table")
    providers = ci.get("providers", [])
    if not isinstance(providers, list) or any(p not in CI_PROVIDERS for p in providers):
        raise ConfigError(f"ci.providers: each entry must be one of {', '.join(CI_PROVIDERS)}")
    oses = ci.get("os", [])
    if not isinstance(oses, list) or any(o not in CI_OS for o in oses):
        raise ConfigError(f"ci.os: each entry must be one of {', '.join(CI_OS)}")
    tags = ci.get("gitlab_tags", {})
    if not isinstance(tags, dict) or any(k not in CI_OS or not isinstance(v, str)
                                         for k, v in tags.items()):
        raise ConfigError(f"ci.gitlab_tags: keys must be among {', '.join(CI_OS)}, values strings")


def _check_tables(data: dict) -> None:
    """Wrong-typed settings exit 2 naming the dotted key instead of failing later."""
    for key in ("kit", "paths", "profile"):
        if key in data and not isinstance(data[key], dict):
            raise ConfigError(f"{key}: must be a table")
    kit = data.get("kit", {})
    adapters = kit.get("adapters", [])
    if not isinstance(adapters, list) or not all(isinstance(a, str) for a in adapters):
        raise ConfigError("kit.adapters: must be a list of strings")
    if "profile" in kit and not isinstance(kit["profile"], str):
        raise ConfigError("kit.profile: must be a string")
    paths = data.get("paths", {})
    for name, value in paths.items():
        if not isinstance(value, str):
            raise ConfigError(f"paths.{name}: must be a string")
    codemap = data.get("profile", {}).get("codemap")
    if codemap is not None and not isinstance(codemap, dict):
        raise ConfigError("profile.codemap: must be a table")


def _check_models(data: dict) -> None:
    models = data.get("models", {})
    if not isinstance(models, dict):
        raise ConfigError("models: must be a table")
    if models.get("mode", "tool") not in MODEL_MODES:
        raise ConfigError(f"models.mode: must be \"tool\" or \"kit\", got {models.get('mode')!r}")


def _check_regex(profile: dict) -> None:
    value = profile.get("req_id_regex")
    try:
        rx = re.compile(value)
    except (re.error, TypeError) as exc:
        raise ConfigError(f"profile.req_id_regex: does not compile: {exc}") from None
    if rx.groups < 2:
        raise ConfigError("profile.req_id_regex: needs at least two capture groups "
                          "(spec number, requirement number)")


def load_config(start: Path | None = None, root: Path | None = None) -> Config:
    if root is None:
        root = find_root(start)
        if root is None:
            raise ConfigError(f"no {CONFIG_NAME} found here or above; run `agentkit install` "
                              "to set up this repository")
    root = Path(root).resolve()
    config_file = root / CONFIG_NAME
    if not config_file.is_file():
        raise ConfigError(f"no {CONFIG_NAME} in {root}; run `agentkit install`")
    data = _read_toml(config_file)
    _check_tables(data)
    _check_ci(data)
    _check_models(data)
    kit = data.get("kit", {})
    name = kit.get("profile") or "generic"
    raw = load_profile(name, root)
    merged = _merge(PROFILE_DEFAULTS, raw)
    overrides = data.get("profile", {})
    if isinstance(overrides, dict):
        merged = _merge(merged, overrides)
    if "test_globs" not in raw and "test_globs" not in overrides:
        merged["test_globs"] = list(merged["frozen_globs"])
    if not isinstance(merged.get("codemap") or {}, dict):
        raise ConfigError(f"profile {name!r}: codemap must be a table")
    merged["codemap"] = _merge(PROFILE_DEFAULTS["codemap"], merged.get("codemap") or {})
    _check_regex(merged)
    return Config(root=root, data=data, profile=merged, kit_source=_kit_source())
