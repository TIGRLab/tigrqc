"""Tests for tigrqc.interfaces
"""
from tigrqc.access import AnonymousUser, NoAuthAnonymousUser
from tigrqc.models import User


def test_user_interface_is_implemented():
    """Test that subclasses of UserInterface implement the interface.

    Should raies a TypeError if a subclass can't be instantiated.
    """
    regular_user = User()
    anon_user = AnonymousUser()
    dev_user = NoAuthAnonymousUser()
