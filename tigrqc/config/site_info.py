"""Configuration of site-specific information.

These settings do not affect the functionality of the application but will
be injected into the templates to personalize the website.
"""
import os

from tigrqc.exceptions import ConfigException

from .utils import get_pyproject_settings

# The 'brand' for the navbar
BRAND = os.environ.get('TIGRQC_BRAND', 'TIGRQC')

# The name of the file in the static folder that contains the logo
LOGO = os.environ.get('TIGRQC_LOGO', 'logo.png')

# The email to provide for support requests.
SUPPORT_EMAIL = os.environ.get('TIGRQC_SUPPORT_EMAIL', '')

# A link to provide for application or quality control related help docs.
# If unset, tigrqc's own official docs page will be used. If this can't be
# found, will fall back to linking to the home page.
HELP_DOCS = os.environ.get('TIGRQC_HELP_DOCS', '')

if HELP_DOCS == '':
    try:
        settings = get_pyproject_settings()
    except ConfigException:
        settings = {}

    HELP_DOCS = settings.get('project', {}).get('urls', {}).get(
        'Homepage', '/'
    )
