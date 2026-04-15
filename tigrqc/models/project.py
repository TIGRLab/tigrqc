"""Database models and relations for projects.
"""
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import (Mapped, attribute_keyed_dict, mapped_column,
                            relationship, validates)

from tigrqc.exceptions import InvalidDataException
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
        readme: The contents of the project's 'README' file if one exists.
            Optional, defaults to ``None``.
        readme_path: The path to the project's 'README' on the filesystem.
            Optional, defaults to ``None``.
        is_active: Whether the project is still actively collecting data.
            Optional, defaults to ``True``.
        sites: Site configuration for this project.
    """
    __tablename__ = 'projects'

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(1024))
    description: Mapped[str | None] = mapped_column(Text)
    readme: Mapped[str | None] = mapped_column(Text, deferred=True)
    readme_path: Mapped[Path | None] = mapped_column(PathType)
    is_active: Mapped[Boolean] = mapped_column(
        Boolean, default=True, nullable=False
    )

    sites: Mapped[dict[str, 'ProjectSite']] = relationship(
        'ProjectSite',
        back_populates='project',
        collection_class=attribute_keyed_dict('site_id'),
        cascade='all, delete',
    )

    def __repr__(self) -> str:
        return f'<Project {self.id}>'

    @validates('id')
    def validate_project_id(self, _, pid: str) -> str:
        """Validate the given project ID.

        Args:
            pid: The possible project ID.

        Returns:
            str: The unmodified project ID if it's valid.

        Raises:
            InvalidDataException:
                - If the ID is less than 3 chars
                - If the ID is more than 32 chars
                - If the ID is not alphanumeric
        """
        if len(pid) < 3:
            raise InvalidDataException(
                f'Project ID too short (<3 chars) - {pid}'
            )

        if len(pid) > 32:
            raise InvalidDataException(
                f'Project ID too long (>32 chars) - {pid}'
            )

        if not pid.isalnum():
            raise InvalidDataException(
                f'Project ID must be alphanumeric - {pid}'
            )

        return pid


class Site(TableMixin, Model):
    """Scan collection sites.

    Attributes:
        id: A unique short (<=32 character), code that identifies the scan
            site. Primary key.
        description: A description of the scan site. Optional, defaults to
            ``None``.
        projects: Project configuration for projects that collect data from
            the given scan site.
    """
    __tablename__ = 'sites'

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    description: Mapped[str] = mapped_column(Text, deferred=True)

    projects: Mapped[dict[str, 'ProjectSite']] = relationship(
        'ProjectSite',
        back_populates='site',
        collection_class=attribute_keyed_dict('project_id'),
        cascade='all, delete',
    )

    def __repr__(self):
        return f'<Site {self.id}>'


class ProjectSite(TableMixin, Model):
    """Defines scan sites that may collect data for a project.

    This table also holds configuration values that may differ between scan
    sites even within a project.

    Attributes:
        project_id: The ID of the project that this configuration belongs to.
            Primary key, Foreign key on ``Projects.id``.
        site_id: The ID of the site that this configuration belongs to.
            Primary key, Foreign key on ``Sites.id``.
        project: The project this configuration belongs to.
        site: The scan site this configuration belongs to.
    """
    __tablename__ = 'project_sites'

    project_id: Mapped[str] = mapped_column(
        'project_id', String(32), ForeignKey('projects.id'), primary_key=True
    )
    site_id: Mapped[str] = mapped_column(
        'site_id', String(32), ForeignKey('sites.id'), primary_key=True
    )

    project: Mapped['Project'] = relationship(
        'Project', back_populates='sites'
    )
    site: Mapped['Site'] = relationship('Site', back_populates='projects')

    def __repr__(self):
        return f'<ProjectSite {self.project_id} - {self.site_id}>'
