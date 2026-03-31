"""Configuration for Flask itself.
"""
import logging
import os

logger = logging.getLogger(__name__)

_DEFAULT_SECRET_KEY = 'dev-key-do-not-use-in-production!'

SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', _DEFAULT_SECRET_KEY)

if SECRET_KEY == _DEFAULT_SECRET_KEY:
    logger.warning(
        '"FLASK_SECRET_KEY" not given! The default key will be used. If this '
        'is a production instance then this is a mistake. Stop the app and '
        'set a unique secret key or user sessions and cookies will not be '
        'properly protected.'
    )
