"""Models and relationships for XNAT integration.
"""
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from tigrqc.extensions import db
from tigrqc.models.mixins import TableMixin
from tigrqc.models.types import EncryptedType, UrlType

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model
else:
    Model = db.Model


class XnatConfig(TableMixin, Model):
    """Configuration used to access an XNAT instance.

    Attributes:
        id: Primary key.
        url: The XNAT instance url.
        username: The user to connect as.
        password: The password to log in with. Will be encrypted in the
            database if encryption is enabled.
        name_scheme: The naming convention used by default for this XNAT
            server. May be overridden.
    """
    __tablename__ = 'xnat_config'

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(UrlType, nullable=False)
    username: Mapped[str] = mapped_column(String(256), nullable=False)
    password: Mapped[str] = mapped_column(EncryptedType(512), nullable=False)
    name_scheme: Mapped[str] = mapped_column(String(64), nullable=False)

    def __repr__(self) -> str:
        return f'<XnatConfig {self.id}: ({self.url}, {self.username})>'


class ProjectXnat(TableMixin, Model):
    """A project's XNAT configuration.

    Attributes:
        id: Primary key.
        project_id: The ID of the project this configuration belongs to.
        site_id: The ID of the project's scan site that to apply this
            configuration to.
        xnat_id: The ID of the XNAT configuration for the server.
        xnat_project: The name of the project on the XNAT server.
    """
    __tablename__ = 'project_xnat'

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey('project_sites.project_id'), nullable=False
    )
    site_id: Mapped[str] = mapped_column(
        ForeignKey('project_sites.site_id'), nullable=False
    )
    xnat_id: Mapped[str] = mapped_column(
        ForeignKey('xnat_config.id'), nullable=False
    )
    xnat_project: Mapped[str] = mapped_column(String, nullable=False)

    # Unsure yet whether I want to make this unique.
    # __table_args__ = (
    #     UniqueConstraint(
    #         'project_id',
    #         'site_id',
    #         'xnat_id',
    #         'xnat_project',
    #         name='uq_project_site_xnat_xproject'
    #     )
    # )

    def __repr__(self) -> str:
        return f'<ProjectXnat {self.id}>'
