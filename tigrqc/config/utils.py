"""Functions and variables that may be needed when setting other configuration.
"""
import os
import tomllib
from pathlib import Path

from tigrqc.exceptions import ConfigException


def read_boolean(var_name: str, default: bool = False) -> bool:
    """Read an environment variable and return a boolean value.

    Args:
        var_name (str): The name of an environment variable to check
        default (bool, optional): The default value to return when the
            variable was not set.

    Returns:
        bool
    """
    result = os.environ.get(var_name, '').lower()

    if result == '':
        return default

    truthy = {
        '1',
        'true',
        'on',
        'yes'
    }
    return result in truthy


def get_pyproject_settings() -> dict:
    """Get the contents of the pyproject.toml file.

    Returns:
        dict: A dictionary containing pyproject.toml's settings.
    """
    toml = Path(__file__).parent.parent.parent / 'pyproject.toml'

    try:
        with toml.open('rb') as fh:
            contents = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ConfigException('Cannot read pyproject.toml') from e

    return contents
