"""Hook formats: Claude-shaped hooks and the plugin protocol (spec 004)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Response:
    stdout: str = ""
    stderr: str = ""
    code: int = 0


class HookFormat:
    """Claude-shaped hook payloads and responses (R004-10 to R004-12, R004-16, R004-17)."""

    def __init__(self, name: str, supports_ask: bool = True):
        self.name = name
        self.supports_ask = supports_ask

    def parse(self, payload: dict):
        raise NotImplementedError("R004-03")

    def pre_response(self, decision) -> Response:
        raise NotImplementedError("R004-10")

    def stop_response(self, payload: dict, problems: list[str]) -> Response:
        raise NotImplementedError("R004-16")

    def session_response(self, text: str) -> Response:
        raise NotImplementedError("R004-20")


class PluginFormat(HookFormat):
    """The plugin protocol of our OpenCode and Pi plugins (R004-13, R004-14, R004-18)."""

    def parse(self, payload: dict):
        raise NotImplementedError("R004-13")

    def pre_response(self, decision) -> Response:
        raise NotImplementedError("R004-13")

    def stop_response(self, payload: dict, problems: list[str]) -> Response:
        raise NotImplementedError("R004-18")

    def session_response(self, text: str) -> Response:
        raise NotImplementedError("R004-20")
