"""Create and configure all needed extensions.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from flask_sqlalchemy import SQLAlchemy

if TYPE_CHECKING:
    from flask import Flask

db = SQLAlchemy()


def init_extensions(app: Flask) -> None:
    """Initialize all extensions.
    """
    db.init_app(app)
