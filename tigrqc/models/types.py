"""Non-native types for use in database models.
"""
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import Integer, String, TypeDecorator
from sqlalchemy.engine.interfaces import Dialect

from tigrqc.extensions import enc


class EncryptedType(TypeDecorator[str]):
    """A column type that ensures values are encrypted.

    If encryption is enabled this will ensure the database only receives
    encrypted values and that values are decrypted when accessed at runtime.

    Example:
        .. code-block:: Python

            class SomeTable(Model):
                some_secret_info: Mapped[String | None] = mapped_column(
                    EncryptedType
                )
    """
    impl = String
    cache_ok = True

    @property
    def python_type(self):
        """The type the column maps to.
        """
        return str

    def process_bind_param(
            self, value: str | None, dialect: Dialect
    ) -> str | None:
        """Encrypts the value (if encryption is enabled).

        Args:
            value: The value to be stored in the database.
            dialect: The sqlalchemy dialect in use. Unused in this case.
        """
        return enc.encrypt(value) if value is not None else None

    def process_result_value(
            self, value: str | None, dialect: Dialect
    ) -> str | None:
        """Decrypts the value (if encryption is enabled).

        Args:
            value: The value to be retrieved from the database.
            dialect: The sqlalchemy dialect in use. Unused in this case.
        """
        return enc.decrypt(value) if value is not None else None

    def process_literal_param(
            self, value: str | None, dialect: Dialect
    ) -> str:
        """Required to be defined. Returns the result of process_bind_param.
        """
        result = self.process_bind_param(value, dialect)
        return result if result is not None else 'NULL'


class PathType(TypeDecorator[Path]):
    """A column type that converts between String <-> pathlib.Path.

    This column type can be used for any database column that stores a
    filesystem path so that it will be automatically made a pathlib.Path
    object at run time.

    Example:
        .. code-block:: Python

            class SomeTable(Model):
                some_path_col: Mapped[Path | None] = mapped_column(PathType)
    """
    impl = String(512)
    cache_ok = True

    @property
    def python_type(self):
        """The type the column maps to.
        """
        return Path

    def process_bind_param(
            self, value: String | Path | None, dialect: Dialect
    ) -> str | None:
        """Converts pathlib.Path -> str for the database.

        Args:
            value: The value to be stored in the database.
            dialect: The sqlalchemy dialect in use (specific to database type).
                Unused in this case.
        """
        return str(value) if value is not None else None

    def process_result_value(
            self, value: str | None, dialect: Dialect
    ) -> Path | None:
        """Converts str -> pathlib.Path for python code.

        Args:
            value: The value retrieved from the database.
            dialect: The sqlalchemy dialect in use (specific to database type).
                Unused in this case.
        """
        return Path(value) if value is not None else None

    def process_literal_param(
            self, value: String | Path | None, dialect: Dialect
    ) -> str:
        """Required to be defined. Returns result of process_bind_param.
        """
        result = self.process_bind_param(value, dialect)
        return result if result is not None else 'NULL'


class UrlType(TypeDecorator[str]):  # pylint: disable=W0223
    """A column type that ensures URL values include the scheme.

    If the column value is a URL that's missing the scheme, this column
    type will ensure its set to 'https'.

    Example:
        .. code-block:: Python

            class SomeTable(Model):
                my_url: Mapped[String | None] = mapped_column(UrlType)
    """
    impl = String
    cache_ok = True

    @property
    def python_type(self):
        """The type the column maps to.
        """
        return str

    def process_bind_param(
            self, value: str | None, dialect: Dialect
    ) -> str | None:
        """Ensures scheme is 'https' if no URL scheme is given.

        Args:
            value: The value to be stored in the database.
            dialect: The sqlalchemy dialect in use. Unused in this case.
        """
        if not value:
            return value

        if not urlparse(value).scheme:
            value = 'https://' + value

        return value


class PaddedNumType(TypeDecorator[str]):
    """A column type that stores zero padded strings as Integer (e.g. '01').

    This column type allows the code to only ever 'see' zero padded strings,
    while letting the database store the contents as plain integers.

    Example:
        .. code-block:: Python

            class SomeTable(Model):
                some_num_col: Mapped[str] = mapped_column(
                    PaddedNumType(width=2)
                )
    """
    impl = Integer
    cache_ok = True

    def __init__(self, *args, width=2, **kwargs):
        super().__init__(*args, **kwargs)
        self.width = width

    @property
    def python_type(self):
        """The type the column maps to.
        """
        return str

    def process_bind_param(
            self, value: str | int | None, dialect: Dialect
    ) -> int | None:
        """Converts the string to an int for the database.

        Args:
            value: The value to be stored in the database.
            dialect: The sqlalchemy dialect in use (specific to database type).
                Unused in this case.
        """
        return int(value) if value is not None else None

    def process_result_value(
            self, value: int | None, dialect: Dialect
    ) -> str | None:
        """Converts an integer to a zero padded string for python code.

        Args:
            value: The value retrieved from the database.
            dialect: The sqlalchemy dialect in use (specific to database type).
                Unused in this case.
        """
        return str(value).zfill(self.width) if value is not None else None

    def process_literal_param(
            self, value: str | int | None, dialect: Dialect
    ) -> str:
        """Required to be defined. Returns result of process_bind_param.
        """
        result = self.process_bind_param(value, dialect)
        return str(result) if result is not None else 'NULL'
