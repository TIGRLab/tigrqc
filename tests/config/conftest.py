"""Fixtures for tests of tigrqc.config
"""
from pytest import MonkeyPatch, fixture


@fixture
def set_env(monkeypatch: MonkeyPatch):
    """Clear all relevant env vars and set vars as needed.
    """
    def _set(clear: list[str], add: dict[str, str]):
        for key in clear:
            monkeypatch.delenv(key, raising=False)
        for key, value in add.items():
            monkeypatch.setenv(key, value)
    return _set
