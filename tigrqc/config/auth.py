"""Configuration for user authentication.

!!! danger
    At least one authentication method should be configured before running
    the app in production. It's a security risk to disable user authentication
    in any environment where the app is exposed to the internet or broader
    networks than just 'localhost'.

These settings change how the application applies user authentication and allow
different authentication methods to be used to 'sign in'.

When running the application in debug mode without any authentication methods
configured note that user authentication will be automatically disabled and the
'anonymous user' will have full admin access to the application.
"""
from .utils import read_boolean

AUTH_DISABLED = read_boolean('TIGRQC_DISABLE_AUTH')

# This must be filled in later when oauth, ldap etc. added
AUTH_METODS: dict[str, dict] = {}
