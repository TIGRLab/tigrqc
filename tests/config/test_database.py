"""Tests for the database configuration module.
"""
from pytest import raises

from tigrqc.config import make_database_uri
from tigrqc.exceptions import ConfigException

ENV_VARS = [
    'TIGRQC_DB_URI',
    'TIGRQC_DB_USER',
    'TIGRQC_DB_PASS',
    'TIGRQC_DB_SRVR',
    'TIGRQC_DB_NAME',
    'TIGRQC_DB_PORT',
    'TIGRQC_DB_POSTGRES',
    'TIGRQC_DB_PATH',
]


class TestMakeDatabaseUri:
    """All tests for tigrqc.config.make_database_uri
    """

    def test_in_memory_sqlite_is_default_when_no_config_given(self, set_env):
        """When no settings are given, use an in-memory sqlite database."""
        set_env(ENV_VARS, {})
        assert (
            make_database_uri().render_as_string(hide_password=False) ==
            'sqlite:///:memory:'
        )

    def test_sqlite_path_is_used_when_provided_by_user(self, set_env):
        """When a path is given, make an sqlite database there."""
        set_env(ENV_VARS, {'TIGRQC_DB_PATH': '/tmp/test.db'})
        assert (
            make_database_uri().render_as_string(hide_password=False) ==
            'sqlite:////tmp/test.db'
        )

    def test_direct_uri_overrides_default_sqlite(self, set_env):
        """If a uri is given, use it instead of the sqlite default."""
        uri = 'postgresql://user:pass@server:5432/db'
        set_env(ENV_VARS, {'TIGRQC_DB_URI': uri})
        assert make_database_uri().render_as_string(hide_password=False) == uri

    def test_direct_uri_overrides_other_connection_settings(self, set_env):
        """Whole URI should override all connection settings."""
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
        set_env(ENV_VARS, env)

        assert make_database_uri().render_as_string(hide_password=False) == uri

    def test_postgres_overrides_sqlite_when_requested_with_defaults(
        self, set_env
    ):
        """Postgres should be used with all defaults when user enables it."""
        set_env(ENV_VARS, {'TIGRQC_DB_POSTGRES': 'true'})

        assert (
            make_database_uri().render_as_string(hide_password=False) ==
            'postgresql:///tigrqc'
        )

    def test_all_postgres_settings_respected(self, set_env):
        """Postgres settings given by user should all be respected."""
        env = {
            'TIGRQC_DB_USER': 'testuser',
            'TIGRQC_DB_PASS': 'secret',
            'TIGRQC_DB_SRVR': 'db.example.com',
            'TIGRQC_DB_NAME': 'testdb',
            'TIGRQC_DB_PORT': '5433',
        }
        set_env(ENV_VARS, env)

        assert (
            make_database_uri().render_as_string(hide_password=False)
            == 'postgresql://testuser:secret@db.example.com:5433/testdb'
        )

    def test_reports_when_non_integer_port_used(self, set_env):
        """Postgres port should always be an int."""
        env = {
            'TIGRQC_DB_PORT': 'someString'
        }
        set_env(ENV_VARS, env)
        with raises(ConfigException):
            make_database_uri()
