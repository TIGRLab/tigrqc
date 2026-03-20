"""Configuration for the application's encryption.

If an encryption key is not given plain text passwords and other sensitive
information will be saved directly in the database. This may be fine for dev
installations but should be avoided in production.

Note that the user must ensure their key never changes once it is set, or the
encrypted fields in the database will end up in an unreadable state.
"""
import logging
import os
from pathlib import Path

from tigrqc.exceptions import ConfigException

logger = logging.getLogger(__name__)


def read_key(given_key: str) -> bytes:
    """Read the encryption key from the provided file.

    Args:
        given_key: The encryption key or the path to a file containing the
            encryption key.

    Returns:
        bytes:  The byte-encoded key value.

    Raises:
        ConfigException: When an encryption key file is given but unreadable.
    """
    key_path = Path(given_key)

    if not key_path.exists():
        logger.debug(
            '"TIGRQC_ENCRYPTION_KEY" is not an existing path. The value '
            'itself is assumed to be a key.'
        )
        return given_key.encode()

    try:
        key = key_path.read_text(encoding='utf-8').strip()
    except OSError as e:
        raise ConfigException(
            f"Can't read the encryption key file - {e}"
        ) from e

    return key.encode()


user_key = os.environ.get('TIGRQC_ENCRYPTION_KEY', '')

FERNEY_KEY: bytes | None = None

if user_key:
    FERNET_KEY = read_key(user_key)
else:
    logger.warning(
        '"TIGRQC_ENCRYPTION_KEY" not given. Database encryption of sensitive '
        'info is disabled. This may be a mistake if this is not a dev '
        'instance.'
    )
