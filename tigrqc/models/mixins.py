"""Mixin classes for the database models.
"""

from sqlalchemy.exc import SQLAlchemyError

from tigrqc.exceptions import InvalidDataException
from tigrqc.extensions import db


class TableMixin:
    """Adds simple methods commonly needed for tables.
    """

    def save(self, err_msg: str | None = None) -> None:
        """Commit changes to the database.

        Fail gracefully if the commit cannot be performed for any reason.

        Args:
            err_msg (str, optional): An error message to use when
                reporting exceptions instead of the broad default message.

        Raises:
            InvalidDataException: If any error prevents a commit.
        """
        default_msg = 'Failed to commit to database.'
        msg = err_msg or default_msg

        db.session.add(self)
        try:
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidDataException(msg + f'Reason - {e}') from e

    def delete(self, err_msg: str | None = None) -> None:
        """Delete a record from the database.

        Fail gracefully if deletion is not possible for any reason.

        Args:
            err_msg (str, optional): An error message to use when reporting
                exceptions instead of the broad default message.

        Raises:
            InvalidDataException: If any error prevents deletion.
        """
        default_msg = 'Failed to delete record from database.'
        msg = err_msg or default_msg

        db.session.delete(self)
        try:
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            raise InvalidDataException(msg + f'Reason - {e}') from e
