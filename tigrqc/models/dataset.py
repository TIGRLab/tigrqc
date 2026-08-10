"""Database models and relations for individual collections of data.

Each dataset is owned by a 'Project' and will contain files which
belong to 'Sessions'/'Subjects' also owned by the 'Project'.
"""
import enum
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import (Boolean, DateTime, Enum, ForeignKey,
                        ForeignKeyConstraint, Integer, String,
                        UniqueConstraint, func)
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.orm import (Mapped, attribute_keyed_dict, mapped_column,
                            relationship)

from tigrqc.extensions import db
from tigrqc.models.mixins import TableMixin
from tigrqc.models.types import PaddedNumType, PathType

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model

    from tigrqc.models.project import Project, ProjectSite, Site
else:
    Model = db.Model


class Dataset(TableMixin, Model):
    """A collection of input files associated with a project.

    Attributes:
        id: The unique ID for this data collection.
        # path: The path to the files on the server's file system.
    """
    __tablename__ = 'datasets'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey('projects.id', ondelete='CASCADE'),
        nullable=False
    )
    # path: Mapped[Path] = mapped_column(PathType, nullable=False)
    # name_type: Mapped[str] = mapped_column(
    #     String(12), ForeignKey('name_schemes.id'), nullable=False
    # )
    data_type: Mapped[str] = mapped_column(
        String(12), ForeignKey('dataset_types.id'), nullable=False
    )

    project: Mapped['Project'] = relationship(
        'Project', back_populates='datasets'
    )
    source_dirs: Mapped[list['SourceDir']] = relationship(
        'SourceDir',
        back_populates='dataset',
        cascade='all, delete',
        passive_deletes=True,
    )
    # Probably need to expose all source_dir invalid dirs here at some point

    def __repr__(self):
        return f'<Dataset[{self.id}] - ({self.project_id}, {self.data_type})>'


class SourceDir(TableMixin, Model):
    """An input directory of data.

    Each source dir can only ever be added once, but can be assigned to
    multiple 'datasets'.
    """
    __tablename__ = 'source_dirs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('datasets.id', ondelete='CASCADE'),
        nullable=False
    )
    path: Mapped[Path] = mapped_column(PathType, nullable=False)
    name_type: Mapped[str] = mapped_column(
        String(12),
        ForeignKey('name_schemes.id'),
        nullable=False,
    )
    date_added: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # pylint: disable=not-callable
        nullable=False,
    )
    last_update: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # pylint: disable=not-callable
        onupdate=func.now(),  # pylint: disable=not-callable
        nullable=False,
    )

    dataset: Mapped['Dataset'] = relationship(
        'Dataset',
        back_populates='source_dirs',
    )
    timepoint_dirs: Mapped[list['TimepointDir']] = relationship(
        'TimepointDir',
        back_populates='parent',
        cascade='all, delete-orphan',
        passive_deletes=True,
    )
    invalid_children: Mapped[list['InvalidData']] = relationship(
        'InvalidData',
        back_populates='parent',
        cascade='all, delete-orphan',
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint('path', name='uq_source_dir_path'),
    )

    def __repr__(self):
        return f'<SourceDir[{self.id}] - {self.path}>'


class TimepointDir(TableMixin, Model):
    """A directory containing a single timepoint from a source directory.
    """
    __tablename__ = 'timepoint_dirs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timepoint_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('timepoints.id', ondelete='CASCADE'),
        nullable=False,
    )
    sourcedir_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('source_dirs.id', ondelete='CASCADE'),
        nullable=False,
    )
    dirname: Mapped[str] = mapped_column(PathType, nullable=False)
    date_added: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # pylint: disable=not-callable
        nullable=False,
    )
    last_update: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # pylint: disable=not-callable
        onupdate=func.now(),  # pylint: disable=not-callable
        nullable=False,
    )

    timepoint: Mapped['Timepoint'] = relationship(
        'Timepoint',
        back_populates='data_dirs',
    )
    parent: Mapped['SourceDir'] = relationship(
        'SourceDir',
        back_populates='timepoint_dirs',
    )
    children: Mapped[list['File']] = relationship(
        'File',
        back_populates='parent',
        cascade='all, delete-orphan',
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint(
            'sourcedir_id',
            'dirname',
            name='uq_timepoint_dir_path',
        ),
        UniqueConstraint(
            'timepoint_id',
            'sourcedir_id',
            name='uq_timepoint_dir_timepoint_id_sourcedir_id',
        ),
    )

    def __repr__(self):
        return f'<TimepointDir[{self.id}] - {self.dirname}>'


# This probably needs to be a table with regexes (so you can auto ingest
#   .nii.gz, or *.pdf etc?) But maybe that's better handled in app.
# Complicates migrations also... Maybe it should be a table.
class FileType(str, enum.Enum):
    NIFTI = 'nifti'
    JSON = 'json'
    BVEC = 'bvec'
    BVAL = 'bval'
    TECH_NOTES = 'tech_notes'


# This might need to be reworked... raw niftis are special and json data
# has to be read and stored differently also.
class File(TableMixin, Model):
    """An input file read from a source directory.
    """
    __tablename__ = 'files'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subdir_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('timepoint_dirs.id', ondelete='CASCADE'),
        nullable=False,
    )
    series_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('series.id', ondelete='CASCADE'),
        nullable=False,
    )
    date_added: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # pylint: disable=not-callable
        nullable=False,
    )
    rel_path: Mapped[str] = mapped_column(PathType, nullable=False)
    file_type: Mapped[str] = mapped_column(
        Enum(
            FileType,
            name='file_type_enum',
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False
    )
    # Might need additional columns for file attributes (dir-, etc.)...
    # size (bytes)?
    # checksum?

    parent: Mapped['TimepointDir'] = relationship(
        'TimepointDir',
        back_populates='children',
    )
    series: Mapped['Series'] = relationship(
        'Series',
        back_populates='files',
    )

    # I think I need another constraint here to avoid more than one nifti
    # for a single series (i.e. duplicates copies...) but don't want to
    # accidentally mess up echoes
    __table_args__ = (
        UniqueConstraint('subdir_id', 'rel_path', name='uq_file_path'),
    )

    def __repr__(self):
        return (
            f'<File[{self.id}] - (Series[{self.series_id}], '
            f'{self.file_type})>'
        )


class InvalidData(TableMixin, Model):
    """Manages all items (file/dir) found within a subject source dir.

    Items are considered invalid if they don't find the expected name / org
    scheme for the source directory.
    """
    __tablename__ = 'invalid_data'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sourcedir_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('source_dirs.id', ondelete='CASCADE'),
        nullable=False,
    )
    # Null if malformed dir in 'subject' level. Otherwise will
    # always link to a session if it's a contained file that's invalid.
    timepoint_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('timepoints.id', ondelete='CASCADE'),
        nullable=True,
    )
    date_added: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # pylint: disable=not-callable
        nullable=False,
    )
    rel_path: Mapped[str] = mapped_column(PathType, nullable=False)
    # Might want to expand this to three states (to reflect 'unseen' state)
    # may also want to add a field to insert a reason why ignore (with auto
    # ignores getting a standard message)
    ignore: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    error_msg: Mapped[str] = mapped_column(
        String(256),
        nullable=True,
    )

    parent: Mapped['SourceDir'] = relationship(
        'SourceDir',
        back_populates='invalid_children',
    )
    timepoint: Mapped['Timepoint'] = relationship(
        'Timepoint',
        back_populates='invalid_contents',
    )

    __table_args__ = (
        UniqueConstraint(
            'sourcedir_id', 'rel_path', name='uq_invalid_data_path',
        ),
    )

    @property
    def path(self):
        """The full path to the invalid directory.
        """
        return self.parent.path / self.rel_path

    def __repr__(self):
        return f'<InvalidData[{self.id}] - {self.rel_path}>'


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
        nullable=False,
    )
    site_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    subject_id: Mapped[str] = mapped_column(String(32), nullable=False)
    num: Mapped[str] = mapped_column(PaddedNumType(width=2), nullable=False)
    is_phantom: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    project_site: Mapped['ProjectSite'] = relationship(
        'ProjectSite',
        back_populates='timepoints',
    )
    project: AssociationProxy['Project'] = association_proxy(
        'project_site', 'project'
    )
    site: AssociationProxy['Site'] = association_proxy(
        'project_site', 'site'
    )
    attempts: Mapped[dict[str, 'Attempt']] = relationship(
        'Attempt',
        back_populates='parent',
        collection_class=attribute_keyed_dict('num'),
        cascade='all, delete-orphan',
        passive_deletes=True,
    )
    data_dirs: Mapped[list['TimepointDir']] = relationship(
        'TimepointDir',
        back_populates='timepoint',
        cascade='all, delete-orphan',
        passive_deletes=True,
    )
    invalid_contents: Mapped[list['InvalidData']] = relationship(
        'InvalidData',
        back_populates='timepoint',
        cascade='all, delete-orphan',
        passive_deletes=True,
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ['project_id', 'site_id'],
            ['project_sites.project_id', 'project_sites.site_id'],
            name='fk_timepoint_on_project_site',
            ondelete='CASCADE',
        ),
        UniqueConstraint(
            'subject_id',
            'num',
            name='uq_timepoint_subject_id_num',
        ),
        UniqueConstraint(
            'project_id',
            'site_id',
            'subject_id',
            'num',
            name='uq_timepoint_project_site_subject_num',
        )
    )

    def __repr__(self):
        if self.is_phantom:
            return f'<Timepoint[{self.id}] - PHA - {self.subject_id}>'
        return f'<Timepoint[{self.id}] - ({self.subject_id}, {self.num})>'


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
    # Not readily available from sidecars
    scan_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    parent: Mapped['Timepoint'] = relationship(
        'Timepoint',
        back_populates='attempts',
    )
    scans: Mapped[list['Series']] = relationship(
        'Series',
        back_populates='parent',
        cascade='all, delete',
        passive_deletes=True,
        order_by='Series.num',
    )

    __table_args__ = (
        UniqueConstraint(
            'timepoint_id',
            'num',
            name='uq_attempt_timepoint_num',
        ),
    )

    def __repr__(self):
        return f'<Attempt[{self.id}] - {self.num}>'


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
    num: Mapped[int] = mapped_column(
        PaddedNumType(width=2), nullable=False
    )
    description: Mapped[int] = mapped_column(String(64), nullable=False)

    parent: Mapped['Attempt'] = relationship(
        'Attempt',
        back_populates='scans',
    )
    files: Mapped[list['File']] = relationship(
        'File',
        back_populates='series',
        cascade='all, delete-orphan',
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint(
            'attempt_id',
            'num',
            name='uq_attempt_series_num',
        ),
    )

    def __repr__(self):
        return f'<Series[{self.id}] - {self.num}: {self.description}>'
