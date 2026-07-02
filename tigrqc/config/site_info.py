"""Configuration of site-specific information.

These settings will be used to personalize the application.
"""
import logging
import os
from pathlib import Path

from tigrqc.exceptions import ConfigException

from .utils import get_pyproject_settings

logger = logging.getLogger(__name__)


def get_data_dirs(user_input: str) -> list[Path]:
    """Checks user provided dirs to ensure they exist and are read/write-able.

    Args:
        user_input: The user-provided, comma-separated, path list.
    """
    valid_paths = []
    for user_path in user_input.split(':'):
        path = Path(user_path)

        if not path.exists():
            try:
                path.mkdir(exist_ok=True)
            except OSError:
                logger.error(
                    'Path %s does not exist and cannot be made. '
                    'Path will be ignored.',
                    user_path
                )
                continue

        if not os.access(path, os.R_OK | os.W_OK):
            logger.error(
                'Path %s has incorrect permission. It must be '
                'readable and writable by the application. Path will be '
                'ignored.',
                user_path
            )
            continue

        valid_paths.append(path)

    return valid_paths


# Directories to serve data from. Users will be able to, at a minimum,
# read the contents of these dirs and every subdir within them.
DATA_DIRS = get_data_dirs(os.environ.get('TIGRQC_DATA_DIRS', ''))

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
