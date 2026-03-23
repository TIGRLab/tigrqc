"""Configuration for the application's encryption.

!!! danger
    If an encryption key is not provided then sensitive information will be
    stored in plain text in certain columns of the database (namely those
    related to connecting to 3rd party services).

    This is probably fine for dev installations but should be avoided in
    production.

Generate an encryption key with this command:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Save the key this generates and either

- Set it as an environment variable. e.g.
  `TIGRQC_ENCRYPTION_KEY=your-generated-key`
- Store it in a file and provide the path to it. e.g.
  `TIGRQC_ENCRYPTION_KEY=/path/to/your/keyfile`

If this key is lost or changed any currently encrypted information in the
database will become permanently unreadable. It should also be protected and
kept secret.

Therefore

- Back the key up securely.
- Never commit your key to any git repository.
- If you save the key in a file, restrict permissions so only the user that
  runs the tigrqc app can read it.

"""
import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet

from tigrqc.exceptions import ConfigException

logger = logging.getLogger(__name__)


def get_key(given_key: str) -> bytes:
    """Get the user's provided key and verify it's valid.

    Args:
        given_key: The encryption key or the path to a file containing the
            encryption key.

    Returns:
        bytes:  The byte-encoded key value.

    Raises:
        ConfigException: If an invalid key is given, or an unreadable key
            file is given.
    """
    try:
        Fernet(given_key)
    except ValueError:
        logger.debug(
            '"TIGRQC_ENCRYPTION_KEY" not set to valid Fernet key. Will '
            'treat it as a key file.'
        )
        given_key = _read_from_file(given_key)
    return given_key.encode()


def _read_from_file(key_file: str) -> str:
    """Read the user's key from the given file path and verify it's valid.

    Args:
        key_file: The path to a file containing the Fernet key.

    Returns:
        bytes: The byte-encoded key value.

    Raises:
        ConfigException: When the keyfile is unreadable or contains an
            invalid Fernet key.
    """
    key_path = Path(key_file)

    if not key_path.exists():
        raise ConfigException(
            f'"TIGRQC_ENCRYPTION_KEY" given invalid path {key_file}'
        )

    try:
        given_key = key_path.read_text(encoding='utf-8').strip()
    except (OSError, UnicodeDecodeError) as e:
        raise ConfigException(
            f'"TIGRQC_ENCRYPTION_KEY" given unreadable key file - {key_file}'
        ) from e

    try:
        Fernet(given_key)
    except ValueError as e:
        raise ConfigException(
            '"TIGRQC_ENCRYPTION_KEY" given invalid encryption key.'
        ) from e

    return given_key


user_key = os.environ.get('TIGRQC_ENCRYPTION_KEY', '')

FERNEY_KEY: bytes | None = None

if user_key:
    FERNET_KEY = get_key(user_key)
else:
    logger.warning(
        '"TIGRQC_ENCRYPTION_KEY" not given. Database encryption of sensitive '
        'info is disabled. This may be a mistake if this is not a dev '
        'instance.'
    )
