"""Code to manage the application's encryption.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from cryptography.fernet import Fernet

if TYPE_CHECKING:
    from flask import Flask


class FernetEncryption:
    """Handle the encryption key provided to the application.
    """

    def __init__(self):
        self._fernet = None

    def init_app(self, app: Flask) -> None:
        """Create the fernet object here in Flask plugin style.

        Args:
            app: The flask app instance to manage encryption for.
        """
        key = app.config.get('FERNET_KEY')
        if key:
            self._fernet = Fernet(key)
        # Good practice to remove the key after Fernet obj made.
        app.config.pop('FERNET_KEY')

    def is_enabled(self) -> bool:
        """Whether encryption is enabled.
        """
        return self._fernet is not None

    def encrypt(self, value: str) -> str:
        """Encrypt the given value with the application's key.

        Args:
            value: The value to be encrypted.

        Returns:
            str: The encrypted value. If encryption is not enabled the
                original value will be returned unmodified.
        """
        if not self.is_enabled():
            return value

        return self._fernet.encrypt(value.encode('utf-8')).decode('utf-8')

    def decrypt(self, value: str) -> str:
        """Decrypt a value with the application's key.

        Args:
            value: The value to be decrypted.

        Returns:
            str: The decrypted string. If encryption is not enabled the
                original value will be returned unmodified.
        """
        if not self.is_enabled():
            return value

        return self._fernet.decrypt(value.encode('utf-8')).decode('utf-8')
