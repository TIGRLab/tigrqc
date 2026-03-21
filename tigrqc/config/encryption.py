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
