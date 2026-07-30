"""Database models and relations for individual collections of data.

Each dataset is owned by a 'Project' and will contain files which
belong to 'Sessions'/'Subjects' also owned by the 'Project'.
"""
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tigrqc.extensions import db
from tigrqc.models.mixins import TableMixin
from tigrqc.models.types import PaddedNumType, PathType

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model

    from tigrqc.models.project import Project, Site
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
    invalid_dirs: Mapped[list['InvalidDataDir']] = relationship(
        'InvalidDataDir',
        back_populates='dataset',
        cascade='all, delete',
        passive_deletes=True,
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


class InvalidDataDir(TableMixin, Model):
    """Handles subdirs that don't conform to the expected name scheme.

    If a subdirectory exists in a dataset it _might_ be something to ignore
    or it could be misnamed subject data. This tracks these directories
    so they can be reported to users or intentionally ignored.
    """
    __tablename__ = 'invalid_dataset_dirs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('datasets.id', ondelete='CASCADE'),
        nullable=False
    )
    dirname: Mapped[str] = mapped_column(String(255), nullable=False)
    ignore: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    dataset: Mapped['Dataset'] = relationship(
        'Dataset', back_populates='invalid_dirs'
    )

# DM: STUDY, SITE, SUBID, TIMEPOINT, REPEAT
# KCNI: STUDY, SITE, SUBID, TIMEPOINT, REPEAT, MODALITY
# BIDS: (optional) SITE, SUBID, nested TIMEPOINT


class Timepoint(TableMixin, Model):
    """bids sess == our timepoint.

    Right now this only allows one study per timepoint and doesn't validate
    that the site code is one 'allowed' by the current study. Also doesn't
    allow a null site (which could be problematic for some bids data.)
    """
    __tablename__ = 'timepoints'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey('projects.id', ondelete='CASCADE'),
        nullable=False,
    )
    site_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey('sites.id', ondelete='CASCADE'),
        nullable=False,
    )
    subject_id: Mapped[str] = mapped_column(String(32), nullable=False)
    num: Mapped[str] = mapped_column(PaddedNumType(width=2), nullable=False)
    is_phantom: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    project: Mapped['Project'] = relationship(
        'Project', back_populates='timepoints'
    )
    site: Mapped['Site'] = relationship(
        'Site', back_populates='timepoints'
    )


class Attempt(TableMixin, Model):
    """Equiv to old dashboard's 'sessions' / Erin's concept of 'repeat'.

    Renamed to avoid bids convention name collision.

    If the scanner stops and restarts during a timepoint, then the 'attempt'
    increments by one.
    """
    __tablename__ = 'attempts'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timepoint_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('timepoints.id', ondelete='CASCADE'),
        nullable=False,
    )
    num: Mapped[str] = mapped_column(PaddedNumType(width=2), nullable=False)
    scan_date: Mapped[datetime] = mapped_column(DateTime(timezone=False))


class Series(TableMixin, Model):
    """Equiv to old dashboard's 'scan'. Renamed for clarity.
    """
    __tablename__ = 'series'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('attempts.id', ondelete='CASCADE'),
        nullable=False,
    )
    # Double check that this can handle series num > 2 digit
    num: Mapped[int] = mapped_column(
        PaddedNumType(2), nullable=False
    )
    # Dicom header character limit
    description: Mapped[int] = mapped_column(String(64), nullable=False)

