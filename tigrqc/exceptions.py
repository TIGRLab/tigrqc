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


class UserException(TigrQcException):
    """Raised from user errors when messages must be relayed to them.
    """
    def __init__(self, err_msg, level='warning', redirect=None):
        self.message = err_msg
        self.level = level
        self.redirect = redirect
        super().__init__(err_msg)


class FileReadException(TigrQcException):
    """Raised when an attempt to read from or parse a file fails.
    """
