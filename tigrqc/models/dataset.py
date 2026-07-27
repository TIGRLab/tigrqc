"""Database models and relations for individual collections of data.

Each dataset is owned by a 'Project' and will contain files which
belong to 'Sessions'/'Subjects' also owned by the 'Project'.
"""
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tigrqc.extensions import db
from tigrqc.models.mixins import TableMixin
from tigrqc.models.types import PathType

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model

    from tigrqc.models.project import Project
else:
    Model = db.Model


class Dataset(TableMixin, Model):
    """A collection of input files associated with a project.

    Attributes:
        id: The unique ID for this data collection.
        path: The path to the files on the server's file system.
    """
    __tablename__ = 'datasets'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey('projects.id', ondelete='CASCADE'),
        nullable=False
    )
    path: Mapped[Path] = mapped_column(PathType, nullable=False)
    name_type: Mapped[str] = mapped_column(
        String(12), ForeignKey('name_schemes.id'), nullable=False
    )
    data_type: Mapped[str] = mapped_column(
        String(12), ForeignKey('dataset_types.id'), nullable=False
    )

    project: Mapped['Project'] = relationship(
        'Project', back_populates='datasets'
    )


# This is a place-holder until I actually add the name-convention management
# classes.
class NameScheme(TableMixin, Model):
    """Lists valid naming conventions that data collections can use.
    """
    __tablename__ = 'name_schemes'
    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    description: Mapped[str] = mapped_column(String(60))


# Also a placeholder
class DatasetType(TableMixin, Model):
    """The category a dataset falls into. Changes how it's displayed, etc.
    """
    __tablename__ = 'dataset_types'
    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    description: Mapped[str] = mapped_column(String(60))
