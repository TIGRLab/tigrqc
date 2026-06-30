"""Controls authentication access to routes.

By default all routes require the user to log in before accessing them,
unless the route has specifically been marked as 'public'.

If authentication is deliberately disabled by the user's configuration then
every route will be accessible without requiring a user to log in. When running
in this mode the anonymous user is considered to have admin-level permissions.
This mode should **never be run in production**.
"""
from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, ParamSpec, TypeVar

from flask import abort, redirect, request, session, url_for
from flask_login import AnonymousUserMixin, current_user, login_user

from tigrqc.exceptions import ConfigException, UserException
from tigrqc.interfaces import UserInterface

if TYPE_CHECKING:
    from flask import Flask
    from flask_login import LoginManager

P = ParamSpec('P')
R = TypeVar('R')


class AnonymousUser(UserInterface, AnonymousUserMixin):
    """Represent a 'user' that has not logged in.
    """
    id = -1
    is_admin = False
    is_active = False
    is_authenticated = False
    is_anonymous = True


class NoAuthAnonymousUser(UserInterface, AnonymousUserMixin):
    """Represent a 'user' when authentication is disabled.
    """
    id = -99
    is_admin = True
    is_active = True
    is_authenticated = True
    is_anonymous = False


def auth_disabled(app: Flask) -> bool:
    """Check if authentication is disabled for this app instance.

    Authentication is considered disabled when either:
        - The user has deliberately set the environment variable to disable it.
        - The app is using debug mode and no authentication methods have
            been configured.

    Raises:
        ConfigException: When no authentication methods have been defined and
            the app is running as a production instance and authentication
            hasn't been deliberately disabled.
    """
    if app.config.get('AUTH_DISABLED'):
        return True

    debug = app.config.get('DEBUG', False)
    methods_exist = bool(app.config.get('AUTH_METHODS'))

    if not debug and not methods_exist:
        raise ConfigException(
            'When running outside of debug mode at least one authentication '
            'method must be defined for the app to run safely. Alternatively '
            'authentication may be intentionally disabled (NOT RECOMMENDED).'
        )

    return debug and not methods_exist


def public_route(f):
    """A decorator that marks a route as 'public'.

    Routes that use this decorator will _not_ require the user to log in
    to access them.
    """
    f.is_public = True
    return f


def require_login_globally(app: Flask):
    """Protect every route behind a requirement to log in first.

    This should be run after all routes have been added to the app instance.

    The 'static' folder and routes marked with the 'no_login' decorator will
    be exempt. If the user has requested authentication to be disabled this
    will do nothing.
    """
    if auth_disabled(app):
        return

    @app.before_request
    def require_login():
        """Before each request ensure the user is logged in, if not public.
        """
        if request.endpoint == 'static':
            # Static files should always be accessible
            return None

        view = app.view_functions.get(request.endpoint)
        if getattr(view, 'is_public', False):
            # Views marked public with the decorator should be accessible
            return None

        if 'user_id' not in session:
            if request.accept_mimetypes.accept_json:
                # API routes should receive 401 rather than redirect
                abort(401)
            return redirect(url_for('user.login', next=request.path))

        return None


def set_anon_user(app: Flask, lm: LoginManager):
    """Add the correct AnonymousUser to the login manager.

    If authentication is enabled the AnonymousUser should have extremely
    limited access and permissions. If it's disabled the AnonymousUser needs
    global access and max permissions because it's the only user.
    """
    if not auth_disabled(app):
        lm.anonymous_user = AnonymousUser
        return

    lm.anonymous_user = NoAuthAnonymousUser

    @app.before_request
    def make_session_fresh():
        """Ensure the pseudo-user is always marked a fresh session.
        """
        login_user(NoAuthAnonymousUser(), remember=False)


def global_admin_required(func: Callable[P, R]) -> Callable[P, R]:
    """A decorator to restrict a route only to users with max permissions.

    Note that this is different from a 'project admin' which is a user who
    has elevated permissions only for a single project. This decorator
    allows route access only to users who have the highest level of global
    privilege.

    Args:
        func: The function to be wrapped.
    """
    @wraps(func)
    def global_admin_only(*args: P.args, **kwargs: P.kwargs) -> R:
        if not current_user.is_admin:
            raise UserException(
                'Permission denied - admin permissions required.'
            )
        return func(*args, **kwargs)
    return global_admin_only
