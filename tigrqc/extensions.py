"""Create and configure all needed extensions.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy.orm import DeclarativeBase

from tigrqc.access import set_anon_user
from tigrqc.encryption import FernetEncryption

if TYPE_CHECKING:
    from flask import Flask


# pylint: disable=too-few-public-methods
class Base(DeclarativeBase):
    """DeclarativeBase for flask-sqlalchemy type hints.
    """


csrf = CSRFProtect()
db = SQLAlchemy(model_class=Base)
enc = FernetEncryption()
lm = LoginManager()


def init_extensions(app: Flask) -> None:
    """Initialize all extensions.
    """
    csrf.init_app(app)
    db.init_app(app)
    enc.init_app(app)

    set_anon_user(app, lm)
    lm.init_app(app)
