"""Tests for tigrqc/access.py
"""
from pytest import raises

from tigrqc.access import auth_disabled
from tigrqc.exceptions import ConfigException


def set_config(app, debug=False, user_disable=False, auth_methods=None,
               add_methods=False):
    """Shortcut to modify app.config for tests.
    """
    if add_methods:
        auth_methods = {
            'OAUTH': {'something': 'goes here'}
        }
    app.config['AUTH_DISABLED'] = user_disable
    app.config['DEBUG'] = debug
    app.config['AUTH_METHODS'] = auth_methods
    return app


class TestAuthDisabled:
    """Tests for tigrqc.access.auth_disabled
    """

    def test_returns_true_when_user_config_uses_disable_flag(self, app):
        """Should be true whenever the direct flag is used.
        """
        set_config(app, user_disable=True)
        assert auth_disabled(app) is True

    def test_auth_disabled_flag_skips_overrides_other_settings(self, app):
        """The direct flag should override all other auth config.
        """
        set_config(app, debug=False, user_disable=True, add_methods=True)
        assert auth_disabled(app) is True

    def test_auth_enabled_when_production_and_methods_exist(self, app):
        """False when running as production and 1+ auth method defined.
        """
        set_config(app, debug=False, add_methods=True)
        assert auth_disabled(app) is False

    def test_exception_raised_when_prod_and_no_methods_defined(self, app):
        """Should crash if production and no auth methods found.
        """
        set_config(app, debug=False, add_methods=False)
        with raises(ConfigException, match='outside of debug mode'):
            auth_disabled(app)

    def test_auth_enabled_in_debug_mode_if_auth_methods_exist(self, app):
        """Debug mode doesn't automatically disable if auth configured.
        """
        set_config(app, debug=True, add_methods=True)
        assert auth_disabled(app) is False

    def test_auth_disabled_in_debug_mode_if_no_auth_config(self, app):
        """Auth should automatically turn off if debugging and not configured.
        """
        set_config(app, debug=True)
        assert auth_disabled(app) is True
