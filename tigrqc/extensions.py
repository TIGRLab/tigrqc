"""Create and configure all needed extensions.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.orm import DeclarativeBase

from tigrqc.access import set_anon_user
from tigrqc.encryption import FernetEncryption

if TYPE_CHECKING:
    from flask import Flask


# pylint: disable=too-few-public-methods
class Base(DeclarativeBase):
    """DeclarativeBase for flask-sqlalchemy type hints.
    """


def register_sqlite_foreign_key_enforcement(
        app: Flask, app_db: SQLAlchemy
) -> None:
    """Turn on foreign key enforcement for sqlite connections.

    By default, for some legacy reasons, sqlite databases don't actually
    pay attention to foreign key constraints. This will ensure every sqlite
    connection turns on foreign key constraints.
    """
    with app.app_context():
        if app_db.engine.dialect.name != 'sqlite':
            return

        @event.listens_for(app_db.engine, 'connect')
        def set_sqlite_foreign_keys_on(dbapi_connection, _):
            cursor = dbapi_connection.cursor()
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.close()


csrf = CSRFProtect()
db = SQLAlchemy(model_class=Base)
enc = FernetEncryption()
lm = LoginManager()


def init_extensions(app: Flask) -> None:
    """Initialize all extensions.
    """
    csrf.init_app(app)

    db.init_app(app)
    register_sqlite_foreign_key_enforcement(app, db)

    enc.init_app(app)

    set_anon_user(app, lm)
    lm.init_app(app)
