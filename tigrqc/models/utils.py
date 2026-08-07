"""Helper functions for database operations.
"""
from typing import TYPE_CHECKING, Any

from sqlalchemy.exc import IntegrityError

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model
    from sqlalchemy.orm import Session


def get_or_create[ModelT: 'Model'](
        db_session: 'Session',
        table: type[ModelT],
        other_fields: dict[str, Any] | None = None,
        **kwargs: Any,
) -> tuple[ModelT, bool]:
    """Get an existing record or create a record if no matches are found.

    This function expects exactly _one_ record to match the given terms, if
    any records already exist. Matching more than one may lead to accidental
    duplicate records being created.

    Use keyword args to specify the columns to match. If other columns
    need to be populated when a record is created then you can provide these
    other values by giving a dictionary of column names and their intended
    contents to 'other_fields'.

    Args:
        db_session: The current flask-sqlalchemy database session (e.g.
            db.session).
        table: A database model for a table.
        other_fields: A dictionary of column-value pairs to populate if
            a new record gets added.
        **kwargs: Column name - value pairs that will be used to locate an
            existing record (and populate a new record if one doesn't exist).
            Note that if a new record must be made and it requires more
            information than was used in the search this extra information
            should be provided via other_fields.

    Returns:
        A tuple of ``(record, created)`` where:
            - record: The discovered or created database record.
            - created: A boolean indicating whether a new record had to be
                made. ``True`` means a new one was made. ``False`` means an
                existing one was found.
    """
    record = db_session.query(table).filter_by(**kwargs).one_or_none()

    if record:
        return record, False

    merged_fields = {**kwargs, **(other_fields or {})}
    record = table(**merged_fields)
    db_session.add(record)

    try:
        db_session.commit()
    except IntegrityError:
        # Something else made the record (race condition). Rollback and fetch.
        db_session.rollback()
        record = db_session.query(table).filter_by(**kwargs).one()
        return record, False

    return record, True
