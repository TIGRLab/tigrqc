"""Interfaces to be used by other parts of the app and its blueprints.
"""
from abc import ABC, abstractmethod


# pylint: disable=too-few-public-methods
class UserInterface(ABC):
    """Defines the interface all 'user'-like classes must implement.

    This is used to prevent all user-like classes from drifting apart in
    their implementation. If a route or template or other code requires
    some attribute or method from a 'user' then it should be defined here
    and implemented for each 'user' type subclass (regular users, anonymous
    user, etc.)

    Attributes:
        id: A unique ID for the user. May be negative for pseudo-users.
        is_admin: Whether the user is allowed to access sensitive info and
            make potentially harmful changes.
    """
    @property
    @abstractmethod
    def id(self) -> int:
        """A unique identifier for the user.
        """

    @property
    @abstractmethod
    def is_admin(self) -> bool:
        """Whether to allow admin-level access to dashboard features.
        """

    @property
    @abstractmethod
    def is_active(self) -> bool:
        """Whether the 'user' is considered usable or is deactivated.
        """
