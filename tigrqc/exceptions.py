"""Exceptions that may be raised by the application.
"""


class TigrQcException(Exception):
    """A base exception class for every TIGRQC exception to inherit from.
    """


class ConfigException(TigrQcException):
    """Raised when the user has provided invalid configuration values.
    """


class InvalidDataException(TigrQcException):
    """Raised when attempting to commit invalid data to the database.
    """
