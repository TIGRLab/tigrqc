"""Create and configure all needed extensions.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

from tigrqc.encryption import FernetEncryption

if TYPE_CHECKING:
    from flask import Flask


# pylint: disable=too-few-public-methods
class Base(DeclarativeBase):
    """DeclarativeBase for flask-sqlalchemy type hints.
    """


db = SQLAlchemy(model_class=Base)
enc = FernetEncryption()
lm = LoginManager()


def init_extensions(app: Flask) -> None:
    """Initialize all extensions.
    """
    db.init_app(app)
    enc.init_app(app)
    lm.init_app(app)
