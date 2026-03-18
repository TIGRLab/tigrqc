"""Non-native types for use in database models.
"""
from pathlib import Path

from sqlalchemy import String, TypeDecorator
from sqlalchemy.engine.interfaces import Dialect


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
        return result if result is not None else ''
