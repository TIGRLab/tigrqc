"""Fixtures for tests of tigrqc.config
"""
from pathlib import Path

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


@fixture
def make_tmp_file(tmp_path):
    """Create a tmp file with the specified contents and return the path.
    """
    def _make_tmp(contents: str, fname: str) -> Path:
        path = tmp_path / fname
        path.write_text(contents)
        return path
    return _make_tmp
