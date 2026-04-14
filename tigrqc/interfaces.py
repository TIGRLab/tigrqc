"""Interfaces to be used by other parts of the app and its blueprints.
"""
from abc import ABC


# pylint: disable=too-few-public-methods
class BaseUser(ABC):
    """Defines the interface all 'user'-like classes must implement.

    Currently this interface is trivial, but as we port more functionality
    over it will be necessary to avoid bugs caused by 'user'-like classes
    drifting apart in their implementations.

    Attributes:
        is_admin: Whether the user is allowed to access sensitive info and
            make potentially harmful changes.
    """
    is_admin: bool
