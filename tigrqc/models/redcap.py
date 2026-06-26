"""Database models and relations for REDCap and its records.
"""
import enum
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import ForeignKey, UniqueConstraint

from tigrqc.extensions import db
from tigrqc.models.mixins import TableMixin
from tigrqc.models.types import UrlType

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model
else:
    Model = db.Model


class RedcapProject(TableMixin, Model):
    """Config to allow API access to a REDCap project.

    Each URL / Token pair must be unique.

    Attributes:
        id: A unique identifier for a single project configuration.
            Primary key.
        nickname: A short, unique, meaningful nickname to identify the
            project. Does not have to match the project name on the server.
        url: The api url to retrieve the project's data from.
        token: A token with read access to the project's data.
    """

    __tablename__ = 'redcap_project'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nickname: Mapped[String] = mapped_column(String(64), nullable=False)
    url: Mapped[String] = mapped_column(UrlType, nullable=False)
    token: Mapped[String] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        UniqueConstraint(nickname),
        UniqueConstraint(url, token),
    )

    def __repr__(self):
        return f'<RedcapProject {self.id} - {self.nickname}>'


class RedcapType(enum.Enum):
    """Allowed 'types' each REDCap collection may represent.
    """
    TECH_NOTES = 'tech_notes'
    SCAN_COMPLETED = 'scan_completed'


class RedcapCollection(TableMixin, Model):
    """A collection of redcap records pulled from a redcap project.

    Attributes:
        id: A unique identifier for the collection. Primary key.
        redcap_project: The redcap project configuration used to pull
            the records. Foreign key on ``RedcapProject.id``.
        type: The 'type' of collection. Determines how it will be
            used. Must be one a value defined by ``RedcapType``.
        project_id: The ID of the project this collection belongs to.
            Foreign key on ``Project.id``
        fields: A list of field names to pull from redcap for every
            record in the collection. The field names must match
            redcap exactly.
    """
    __tablename__ = 'redcap_collection'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    redcap_project: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('redcap_project.id'),
        nullable=False,
    )
    type: Mapped[String] = mapped_column(Enum(RedcapType), nullable=False)
    project_id: Mapped[String] = mapped_column(
        String(32),
        ForeignKey('projects.id'),
        nullable=False
    )
    fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint('redcap_project', 'type', 'project_id'),
    )

    def __repr__(self):
        return f'<RedcapCollection {self.id}>'
