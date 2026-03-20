"""Database models and relations for projects.
"""
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tigrqc.extensions import db
from tigrqc.models.mixins import TableMixin
from tigrqc.models.types import PathType

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model
else:
    Model = db.Model


class Project(TableMixin, Model):
    """A project representing a data collection.

    Attributes:
        id: A unique, short (<=32 character), code that identifies a project.
        name: The long form name for the project. Optional, defaults to
            ``None``.
        description: An extended description of the project and the data
            it contains. Optional, defaults to ``None``.
        read_me: The contents of the project's 'README' file if one exists.
            Optional, defaults to ``None``.
        readme_path: The path to the project's 'README' on the filesystem.
            Optional, defaults to ``None``.
        is_active: Whether the project is still actively collecting data.
            Optional, defaults to ``True``.
    """
    __tablename__ = 'projects'

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(1024))
    description: Mapped[str | None] = mapped_column(Text)
    read_me: Mapped[str | None] = mapped_column(Text, deferred=True)
    readme_path: Mapped[Path | None] = mapped_column(PathType)
    is_active: Mapped[Boolean] = mapped_column(
        Boolean, default=True, nullable=False
    )

    def __repr__(self) -> str:
        return f'<Project {self.id}>'
