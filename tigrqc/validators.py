"""Validators for various forms of user input.

This may include anything from plain functions for use in views to validator
classes for use by Flask-WTForm fields.
"""
import os
from dataclasses import dataclass
from pathlib import Path

from flask import current_app
from wtforms.validators import ValidationError

from .exceptions import UserException


def validate_path(
        user_path: Path | str,
        allowed_dirs: list[Path | str] | None = None,
        must_exist: bool = True,
        require_read: bool = True,
        require_write: bool = False,
) -> Path:
    """Check if a user path is safe to use, exists, and is readable / writable.

    Args:
        user_path: The user-provided path to check for validity.
        allowed_dirs: A list of whitelisted directories. The user provided path
            must reside in one of these directories. Optional. If not
            provided the application's DATA_DIRS will be used.
        must_exist: Whether the path must already exist. If False,
            and the path doesn't exist then the options 'require_read'
            and 'require_write' will be completely ignored. Default True.
        require_read: Whether to check if the path is readable to the
            application. Default True.
        require_write: Whether to check if the path is writeable to the
            application. Default False.

    Raises:
        UserException: If any of the requirements are violated.

    Returns:
        Path: The resolved, validated path.
    """
    user_path = Path(user_path).resolve()

    if allowed_dirs:
        allowed_dirs = [Path(item).resolve() for item in allowed_dirs]
    else:
        allowed_dirs = current_app.config.get('DATA_DIRS', [])

    if not any(
        user_path.is_relative_to(allowed)
        for allowed in allowed_dirs
    ):
        raise UserException('Provided path is not from a valid directory.')

    if not user_path.exists():
        if must_exist:
            raise UserException('Provided path does not exist.')
        return user_path

    if require_read and not os.access(user_path, os.R_OK):
        raise UserException('Provided path is not readable.')

    if require_write and not os.access(user_path, os.W_OK):
        raise UserException('Provided path is not writable.')

    return user_path


@dataclass(slots=True)
class SafePath:
    """A path validator for WTForms.

    Can validate that the path given:
        1) Is within a whitelisted directory
        2) Exists
        3) Is readable or writeable
    """
    whitelist_dirs: list[Path | str] | None = None
    must_exist: bool = True
    must_read: bool = True
    must_write: bool = False

    def __call__(self, _, field):
        given_path = field.data

        if not given_path:
            # Let other validators handle non-existent input for the field.
            return

        try:
            validate_path(
                given_path,
                allowed_dirs=self.whitelist_dirs,
                must_exist=self.must_exist,
                require_read=self.must_read,
                require_write=self.must_write,
            )
        except UserException as e:
            raise ValidationError(str(e)) from e
