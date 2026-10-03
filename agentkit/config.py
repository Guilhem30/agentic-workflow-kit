"""Configuration, profiles, globs and model tiers (spec 001)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

CONFIG_NAME = "agentkit.toml"


class ConfigError(Exception):
    """A configuration problem. Commands report it and exit 2."""


@dataclass
class Config:
    root: Path
    data: dict
    profile: dict
    kit_source: Path

    def path(self, key: str) -> str:
        raise NotImplementedError("R001-06")

    @property
    def lock_rel(self) -> str:
        raise NotImplementedError("R001-06")

    @property
    def unfreeze_log_rel(self) -> str:
        raise NotImplementedError("R001-06")

    @property
    def lock_path(self) -> Path:
        raise NotImplementedError("R001-06")

    @property
    def unfreeze_log_path(self) -> Path:
        raise NotImplementedError("R001-06")

    @property
    def specs_dir(self) -> Path:
        raise NotImplementedError("R001-06")

    @property
    def state_dir(self) -> Path:
        raise NotImplementedError("R001-06")

    @property
    def adapters(self) -> list[str]:
        raise NotImplementedError("R001-05")

    @property
    def python_cmd(self) -> str:
        raise NotImplementedError("R001-07")

    @property
    def self_hosted(self) -> bool:
        raise NotImplementedError("R001-05")

    def models(self, adapter: str | None = None) -> dict[str, str]:
        raise NotImplementedError("R001-17")

    @property
    def budgets(self) -> dict:
        raise NotImplementedError("R001-05")

    @property
    def guard(self) -> dict:
        raise NotImplementedError("R001-05")

    @property
    def frozen_globs(self) -> list[str]:
        raise NotImplementedError("R001-10")

    @property
    def test_globs(self) -> list[str]:
        raise NotImplementedError("R001-10")


def find_root(start: Path | None = None) -> Path | None:
    raise NotImplementedError("R001-02")


def load_profile(name: str, root: Path | None = None) -> dict:
    raise NotImplementedError("R001-08")


def load_config(start: Path | None = None, root: Path | None = None) -> Config:
    raise NotImplementedError("R001-01")
