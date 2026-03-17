"""Create and configure all needed extensions.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

if TYPE_CHECKING:
    from flask import Flask

    from tigrqc.models import User


# pylint: disable=too-few-public-methods
class Base(DeclarativeBase):
    """DeclarativeBase for flask-sqlalchemy type hints.
    """


db = SQLAlchemy(model_class=Base)
lm = LoginManager()


def init_extensions(app: Flask) -> None:
    """Initialize all extensions.
    """
    db.init_app(app)

    lm.init_app(app)

    @lm.user_loader
    def load_user(uid: str) -> User | None:
        # lazy import to avoid circular imports
        # pylint: disable=import-outside-toplevel
        from tigrqc.models import User
        try:
            return User.get(int(uid))
        except ValueError:
            return None
