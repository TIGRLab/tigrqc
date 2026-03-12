"""Functions and variables that may be needed when setting other configuration.
"""
import os


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
