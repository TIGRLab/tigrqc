"""Tests for the database configuration module.
"""
from pytest import MonkeyPatch, raises

from tigrqc.config import make_database_uri
from tigrqc.exceptions import ConfigException


def set_env(monkeypatch: MonkeyPatch, env: dict) -> None:
    """Clear all relevant environment variables and set test values."""

    keys = [
        'TIGRQC_DB_URI',
        'TIGRQC_DB_USER',
        'TIGRQC_DB_PASS',
        'TIGRQC_DB_SRVR',
        'TIGRQC_DB_NAME',
        'TIGRQC_DB_PORT',
        'TIGRQC_DB_POSTGRES',
        'TIGRQC_DB_PATH',
    ]

    for key in keys:
        monkeypatch.delenv(key, raising=False)

    for key, value in env.items():
        monkeypatch.setenv(key, value)


def test_sqlite_in_memory_is_default_when_no_config_given(
        monkeypatch: MonkeyPatch
) -> None:
    """If no env vars are set, sqlite in-memory DB should be used."""
    set_env(monkeypatch, {})
    assert (
        make_database_uri().render_as_string(hide_password=False) ==
        'sqlite:///:memory:'
    )


def test_sqlite_path_is_used_when_provided_by_user(
        monkeypatch: MonkeyPatch
) -> None:
    """Custom sqlite path should be respected."""
    set_env(monkeypatch, {'TIGRQC_DB_PATH': '/tmp/test.db'})
    assert (
        make_database_uri().render_as_string(hide_password=False) ==
        'sqlite:////tmp/test.db'
    )


def test_direct_uri_overrides_default_sqlite(monkeypatch: MonkeyPatch) -> None:
    """If full DB uri is given, it must be used instead of sqlite default."""
    uri = 'postgresql://user:pass@server:5432/db'
    set_env(monkeypatch, {'TIGRQC_DB_URI': uri})
    assert make_database_uri().render_as_string(hide_password=False) == uri


def test_direct_uri_overrides_other_connection_settings(
        monkeypatch: MonkeyPatch
) -> None:
    """Direct URI should be used even when other connection settings given."""
    uri = 'mysql://user:pass@server:5432/db'
    env = {
        'TIGRQC_DB_URI': uri,
        'TIGRQC_DB_USER': 'myuser',
        'TIGRQC_DB_PASS': 'mypass',
        'TIGRQC_DB_SRVR': 'localhost',
        'TIGRQC_DB_NAME': 'test_db',
        'TIGRQC_DB_PORT': '9999',
        'TIGRQC_DB_POSTGRES': 'True'
    }
    set_env(monkeypatch, env)

    assert make_database_uri().render_as_string(hide_password=False) == uri


def test_postgres_overrides_sqlite_when_requested_with_defaults(
        monkeypatch: MonkeyPatch
) -> None:
    """Postgres should be used with all defaults when user enables it."""
    set_env(monkeypatch, {'TIGRQC_DB_POSTGRES': 'true'})

    assert (
        make_database_uri().render_as_string(hide_password=False) ==
        'postgresql:///tigrqc'
    )


def test_all_postgres_settings_respected(monkeypatch: MonkeyPatch) -> None:
    """Postgres settings given by user should all be toggleable."""
    env = {
        'TIGRQC_DB_USER': 'testuser',
        'TIGRQC_DB_PASS': 'secret',
        'TIGRQC_DB_SRVR': 'db.example.com',
        'TIGRQC_DB_NAME': 'testdb',
        'TIGRQC_DB_PORT': '5433',
    }
    set_env(monkeypatch, env)

    assert (
        make_database_uri().render_as_string(hide_password=False)
        == 'postgresql://testuser:secret@db.example.com:5433/testdb'
    )


def test_reports_non_integer_port(monkeypatch: MonkeyPatch) -> None:
    """Postgres port should be an int.
    """
    env = {
        'TIGRQC_DB_PORT': 'someString'
    }
    set_env(monkeypatch, env)
    with raises(ConfigException):
        make_database_uri()
