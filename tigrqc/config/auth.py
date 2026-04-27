"""Configuration for user authentication.

!!! danger
    At least one authentication method should be configured before running
    the app in production. It's a security risk to disable user authentication
    in any environment where the app is exposed to the internet or broader
    networks than just 'localhost'.

These settings change how the application applies user authentication and allow
different authentication methods to be used to 'sign in'.

Authentication will be disabled in either of these situations:

- The environment variable `TIGRQC_DISABLE_AUTH` is set to something 'truthy'.
- The app is running in debug mode and no authentication methods have been
    provided.

Otherwise the application will attempt to run with authentication enabled and
crash if it is unable to do so (for example, if auth methods are incorrectly
configured).
"""
from .utils import read_boolean

AUTH_DISABLED = read_boolean('TIGRQC_DISABLE_AUTH')

# This must be filled in later when oauth, ldap etc. added
AUTH_METODS: dict[str, dict] = {}
