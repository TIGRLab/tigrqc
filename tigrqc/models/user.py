"""Models and relationships for Users.
"""
from typing import TYPE_CHECKING

from flask_login import UserMixin
from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tigrqc.extensions import db
from tigrqc.models.mixins import TableMixin

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model
else:
    Model = db.Model


class User(UserMixin, TableMixin, Model):
    """An application user.
    """
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_name: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str | None] = mapped_column(String(256))
    position: Mapped[str | None] = mapped_column(String(64))
    institution: Mapped[str | None] = mapped_column(String(128))
    phone_num: Mapped[str | None] = mapped_column(String(20))
    phone_ext: Mapped[str | None] = mapped_column(String(10))
    is_admin: Mapped[bool | None] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=False)

    auth_methods: Mapped[list['UserAuth']] = relationship(
        'UserAuth', back_populates='user', cascade='all, delete-orphan'
    )

    def __repr__(self) -> str:
        return f'<User {self.id}: {self.first_name} {self.last_name}>'


class UserAuth(TableMixin, Model):
    """Authentication methods available for a user.
    """
    __tablename__ = 'user_auth'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id'), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    auth_id: Mapped[str] = mapped_column(String(256), nullable=False)

    user: Mapped['User'] = relationship('User', back_populates='auth_methods')

    __table_args__ = (
        UniqueConstraint('user_id', 'provider', name='uq_user_provider'),
        UniqueConstraint('provider', 'auth_id', name='uq_provider_auth'),
    )

    def __repr__(self) -> str:
        return f'<UserAuth {self.id}: ({self.user_id}, {self.provider})>'
