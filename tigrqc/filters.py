"""Jinja filters that may be used in templates.
"""
from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from flask import Flask

_filters: list[Callable] = []


def jinja_filter[F: Callable](func: F) -> F:
    """Decorator to register a function as a jinja filter.

    The name of the function will be used as the filter's name in templates.
    """
    _filters.append(func)
    return func


@jinja_filter
def make_id(item: str) -> str:
    """Create a 32 char MD5 hash ID for a string.
    """
    return hashlib.md5(item.encode()).hexdigest()


def register_jinja_filters(app: Flask) -> None:
    """Register all Jinja filters on the given app instance.
    """
    for item in _filters:
        app.jinja_env.filters[item.__name__] = item
