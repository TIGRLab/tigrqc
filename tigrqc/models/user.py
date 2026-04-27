"""Models and relationships for Users.
"""
from abc import ABCMeta
from typing import TYPE_CHECKING

from flask_login import UserMixin
from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeMeta, Mapped, mapped_column, relationship

from tigrqc.extensions import db, lm
from tigrqc.interfaces import UserInterface
from tigrqc.models.mixins import TableMixin

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model
else:
    Model = db.Model


class _UserCombinedMeta(DeclarativeMeta, ABCMeta):
    """Combine MetaClasses to prevent inheritance issues.

    Subclasses of the db.Model complain when you throw in an interface
    that inherits from ABC. This resolves the metaclass inheritance issues.
    """


# pylint: disable=too-few-public-methods
class UserModelBase(UserInterface, metaclass=_UserCombinedMeta):
    """Resolve inheritance issues for database models.

    The User model and any other user-like database model should inherit
    from this class. AnonymousUser and other non-database user-like
    objects can inherit directly from UserInterface.

    All actual shared functionality should be defined on UserInterface,
    not here. This just exists to resolve inheritance metaclass issues.
    """


class User(UserModelBase, UserMixin, TableMixin, Model):
    """An application user.

    Attributes:
        id: Primary key.
        first_name: User's first name.
        last_name: User's last name.
        email: The user's email. Optional, defaults to ``None``.
        position: The user's job position at their institution. Optional,
            defaults to ``None``.
        institution: The institution the user works at. Optional, defaults
            to ``None``.
        phone_num: The user's phone number. Optional, defaults to ``None``.
        phone_ext: The user's phone extension if needed. Optional, defaults
            to ``None``.
        is_admin: Whether the user should have admin permissions. Optional,
            defaults to ``False``.
        active_account: Whether the account is currently active. Optional,
            defaults to ``False``.
        auth_methods: Authentication methods the user can use to log in.
        is_active: Used by flask-login to determine if user is allowed to
            login.
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
    is_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    active_account: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    auth_methods: Mapped[list['UserAuth']] = relationship(
        'UserAuth', back_populates='user', cascade='all, delete-orphan'
    )

    @property
    def is_active(self) -> bool:
        return self.active_account

    def __repr__(self) -> str:
        return f'<User {self.id}: {self.first_name} {self.last_name}>'


class UserAuth(TableMixin, Model):
    """Authentication methods available for a user.

    Attributes:
        id: Primary key.
        user_id: The ID of the user that may log in using these
            credentials. Foreign Key on User.id.
        provider: The authentication provider (e.g. 'github').
        auth_id: The identifier used by the authentication provider.
        user: The user that this configuration belongs to.

    Notes:
        Unique constraints:

        - (user_id, provider) must be unique. Each user can only configure
            a specific auth method once.
        - (provider, auth_id) must be unique. The same authentication
            credentials cannot log in more than one user.
    """
    __tablename__ = 'user_auth'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey('users.id'), nullable=False
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


@lm.user_loader
def load_user(uid: str) -> User | None:
    """Tells flask-login how to load the user object.
    """
    try:
        return User.get(int(uid))
    except ValueError:
        return None
