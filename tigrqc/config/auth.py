"""Configuration for user authentication.
"""
from .utils import read_boolean

AUTH_DISABLED = read_boolean('TIGRQC_DISABLE_AUTH')

# This must be filled in later when oauth, ldap etc. added
AUTH_METODS: dict[str, dict] = {}
