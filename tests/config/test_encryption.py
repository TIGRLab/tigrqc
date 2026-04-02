"""Tests for the encryption configuration module.
"""
import importlib
import logging
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from pytest import param, raises

import tigrqc.config.encryption as enc
from tigrqc.exceptions import ConfigException

ENV_VARS = [
    'TIGRQC_ENCRYPTION_KEY',
]

INVALID_KEYS = [
    b'not-base-64',
    b'5wzt-OeRgnPWPkmVc=',  # too short (<32 bytes), but otherwise valid.
    b''
]

FILE_READ_ERRORS = [
    param(FileNotFoundError('No such file'), id='file_not_found'),
    param(PermissionError('Permission denied'), id='permission_error'),
    param(IsADirectoryError('Is a directory'), id='is_a_directory'),
    param(
        UnicodeDecodeError('utf-8', b'', 0, 1, 'Invalid byte'),
        id='unicode_decode_error'
    ),
    param(OSError('Generic I/O error'), id='oserror'),
]


class TestReadKey:
    """Tests for tigrqc.config.encryption.read_key
    """

    def test_returns_user_key_when_given_valid_key(self):
        """If the user gives a valid Fernet key, just use it.
        """
        user_key = Fernet.generate_key()
        assert enc.get_key(str(user_key, 'utf-8')) == user_key

    @pytest.mark.parametrize('invalid_key', INVALID_KEYS)
    def test_raises_config_exception_when_given_invalid_key(
            self, invalid_key
    ):
        """If the user gives a key Fernet can't use, raise ConfigException.
        """
        with raises(ConfigException):
            enc.get_key(str(invalid_key, 'utf-8'))

    def test_reads_key_when_given_a_valid_keyfile(self, make_tmp_file):
        """If the user gives a keyfile the key should be read from it.
        """
        key = Fernet.generate_key()
        key_file = make_tmp_file(str(key, 'utf-8'), 'test.key')
        assert enc.get_key(str(key_file)) == key

    def test_reads_key_strips_extra_whitespace_from_keyfile(
            self, make_tmp_file
    ):
        """If whitespace is in the keyfile it must be stripped for Fernet.
        """
        key = Fernet.generate_key()
        key_file = make_tmp_file(str(key, 'utf-8') + '      \n', 'test.key')
        assert enc.get_key(str(key_file)) == key

    @pytest.mark.parametrize('error', FILE_READ_ERRORS)
    def test_raises_config_exception_when_given_unreadable_keyfile(
            self, make_tmp_file, monkeypatch, error
    ):
        """If keyfile is given but unreadable, raise ConfigException
        """
        bad_file = make_tmp_file('hello world', 'badfile.key')
        monkeypatch.setattr(
            Path,
            'read_text',
            lambda *a, **kw: (_ for _ in ()).throw(error)
        )
        with raises(ConfigException):
            enc.get_key(str(bad_file))

    @pytest.mark.parametrize('invalid_key', INVALID_KEYS)
    def test_raises_config_exception_when_given_keyfile_with_bad_key(
            self, make_tmp_file, invalid_key
    ):
        """If given a keyfile with an invalid key, raise ConfigException
        """
        key_file = make_tmp_file(str(invalid_key, 'utf-8'), 'invalid.key')
        with raises(ConfigException):
            enc.get_key(str(key_file))


def test_user_warned_encryption_disabled_when_no_key_given(caplog, set_env):
    """Warn the user encryption is disabled when they don't give a key.
    """
    set_env(ENV_VARS, {})
    with caplog.at_level(logging.WARNING):
        importlib.reload(enc)
    assert 'disabled' in caplog.text


def test_ferney_key_is_none_when_no_key_given(set_env):
    """The app should receive FERNET_KEY = None when none has been given.
    """
    set_env(ENV_VARS, {})
    importlib.reload(enc)
    assert enc.FERNET_KEY is None


def test_fernet_key_is_set_when_env_var_is_set_correctly(set_env):
    """The app should receive the user's key via FERNET_KEY if it was given.
    """
    key = Fernet.generate_key()
    set_env(ENV_VARS, {'TIGRQC_ENCRYPTION_KEY': str(key, 'utf-8')})
    importlib.reload(enc)
    assert enc.FERNET_KEY == key
