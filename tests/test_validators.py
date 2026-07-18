"""Tests for validators.
"""
# pylint: disable=redefined-outer-name
import os
from pathlib import Path

import pytest
from flask import Flask

from tigrqc.validators import UserException, validate_path


@pytest.fixture
def app():
    """A basic mock app.
    """
    flask_app = Flask(__name__)
    flask_app.config['DATA_DIRS'] = []
    with flask_app.app_context():
        yield flask_app


@pytest.fixture
def allowed_dir(tmp_path):
    """A directory that users may use in their paths.
    """
    d = tmp_path / 'allowed'
    d.mkdir()
    return d


@pytest.fixture
def other_dir(tmp_path):
    """A directory that may NOT be used by user paths."""
    d = tmp_path / 'other'
    d.mkdir()
    return d


@pytest.fixture
def existing_file(allowed_dir):
    """A file that exists.
    """
    f = allowed_dir / 'file.txt'
    f.write_text('hello')
    return f


class TestValidatePath:
    """Tests for validators.validate_path
    """

    def test_app_data_dirs_used_when_no_allowed_dirs_given(
        self, app, allowed_dir, existing_file
    ):
        """The app config's DATA_DIRS should be used by default.
        """
        app.config['DATA_DIRS'] = [allowed_dir]
        result = validate_path(existing_file)
        assert result == existing_file.resolve()

    def test_paths_raise_when_no_allowed_dirs_and_no_data_dirs(
        self, app, existing_file
    ):
        """If both DATA_DIRS and allowed_dirs argument is an empty list then
        no paths can be considered valid to use.
        """
        with pytest.raises(UserException):
            validate_path(existing_file, allowed_dirs=[])

        app.config['DATA_DIRS'] = []
        with pytest.raises(UserException):
            validate_path(existing_file)

    def test_providing_allowed_dirs_overrides_config_data_dirs(
        self, app, allowed_dir, other_dir, existing_file
    ):
        """If the allowed_dirs argument is given, the config DATA_DIRS should
        be ignored.
        """
        app.config['DATA_DIRS'] = [other_dir]

        # existing_file should raise if nothing is given, since it's not
        # in 'other_dir'.
        with pytest.raises(UserException):
            validate_path(existing_file)

        # Now it should work, with explicit override.
        result = validate_path(existing_file, allowed_dirs=[allowed_dir])
        assert result == existing_file.resolve()

    def test_path_within_allowed_dir_passes(
            self, existing_file, allowed_dir
    ):
        """An existing, readable path within permitted directories should
        be considered valid.
        """
        result = validate_path(existing_file, allowed_dirs=[allowed_dir])
        assert result == existing_file.resolve()

    def test_path_outside_allowed_dirs_raises_user_exception(
            self, allowed_dir, other_dir
    ):
        """A path from anywhere outside the permitted directories is invalid.
        """
        outside_file = other_dir / 'file.txt'
        outside_file.write_text('hello')

        with pytest.raises(UserException):
            validate_path(outside_file, allowed_dirs=[allowed_dir])

    def test_validates_usable_dir_when_multiple_allowed_dirs_given(
            self, allowed_dir, other_dir
    ):
        """Exposing multiple directories to users should be possible.
        """
        f = other_dir / 'file.txt'
        f.write_text('hello')

        result = validate_path(f, allowed_dirs=[allowed_dir, other_dir])
        assert result == f.resolve()

    def test_accepts_str_user_path(self, existing_file, allowed_dir):
        """A plain string path should be possible to validate.
        """
        result = validate_path(str(existing_file), allowed_dirs=[allowed_dir])
        assert result == existing_file.resolve()

    def test_accepts_path_object_user_path(self, existing_file, allowed_dir):
        """A pathlib.Path object should be possible to validate.
        """
        result = validate_path(existing_file, allowed_dirs=[allowed_dir])
        assert result == existing_file.resolve()

    def test_allowed_dirs_accepts_str_entries(
            self, existing_file, allowed_dir
    ):
        """Allowed dirs should be accepted if given as a string.
        """
        result = validate_path(existing_file, allowed_dirs=[str(allowed_dir)])
        assert result == existing_file.resolve()

    def test_allowed_dirs_accepts_path_entries(
            self, existing_file, allowed_dir
    ):
        """Allowed dirs should be accepted if given as a pathlib.Path object.
        """
        assert isinstance(allowed_dir, Path)

        result = validate_path(existing_file, allowed_dirs=[allowed_dir])
        assert result == existing_file.resolve()

    def test_return_value_is_resolved_path_object(
            self, existing_file, allowed_dir
    ):
        """Valid paths should be returned as a resolved pathlib.Path object.
        """
        result = validate_path(existing_file, allowed_dirs=[allowed_dir])
        assert result.is_absolute()
        assert result == existing_file.resolve()

    def test_path_cant_break_containment_with_dot_segments(
            self, allowed_dir, other_dir
    ):
        """Cleverness with '..' shouldn't be able to break out of the allowed
        dirs.
        """
        secret = other_dir / 'secret.txt'
        secret.write_text("This shouldn't be accessible.")

        bad_path = allowed_dir / '..' / 'other' / 'secret.txt'
        with pytest.raises(UserException):
            validate_path(bad_path, allowed_dirs=[allowed_dir])

    def test_symlink_cant_break_containment(self, allowed_dir, other_dir):
        """Symlinks shouldn't be able to get paths from outside of the
        allowed dirs to pass the validation.
        """
        target = other_dir / 'target.txt'
        target.write_text('data')

        link = allowed_dir / 'link.txt'
        link.symlink_to(target)

        with pytest.raises(UserException):
            validate_path(link, allowed_dirs=[allowed_dir])

    def test_existing_directory_is_valid_when_existence_required(
            self, allowed_dir
    ):
        """A directory that exists should be 'valid' if existence is required.
        """
        subdir = allowed_dir / 'subdir'
        subdir.mkdir()

        result = validate_path(
            subdir, allowed_dirs=[allowed_dir], must_exist=True
        )
        assert result == subdir.resolve()

    def test_raises_when_must_exist_but_doesnt(self, allowed_dir):
        """A directory that doesn't exist should fail validation if existence
        has explicitly been required.
        """
        missing = allowed_dir / 'missing.txt'

        with pytest.raises(UserException):
            validate_path(missing, allowed_dirs=[allowed_dir], must_exist=True)

    def test_returns_path_if_existence_not_required_and_not_found(
            self, allowed_dir
    ):
        """A path should pass validation even if it doesn't exist, if existence
        wasn't required.
        """
        missing = allowed_dir / 'missing.txt'

        result = validate_path(
            missing, allowed_dirs=[allowed_dir], must_exist=False
        )
        assert result == missing.resolve()

    def test_no_read_check_performed_if_existence_not_required_and_nonexistent(
            self, allowed_dir, monkeypatch
    ):
        """Readability shouldn't be checked if the path doesn't exist and
        existence wasn't required.
        """
        missing = allowed_dir / 'missing.txt'

        def fail_access(*args, **kwargs):
            raise AssertionError(
                "os.access should not be called when path doesn't exist"
            )

        monkeypatch.setattr(os, 'access', fail_access)

        result = validate_path(
            missing,
            allowed_dirs=[allowed_dir],
            must_exist=False,
            require_read=True,
            require_write=True,
        )
        assert result == missing.resolve()

    def test_readability_not_checked_when_required_read_is_false(
            self, existing_file, allowed_dir, monkeypatch
    ):
        """required_read=False should stop from checking if path can be read.
        """
        def fake_access(path, mode):
            if mode == os.R_OK:
                raise AssertionError(
                    'read access should not be checked.'
                )
            return True

        monkeypatch.setattr(os, 'access', fake_access)

        result = validate_path(
            existing_file, allowed_dirs=[allowed_dir], require_read=False
        )
        assert result == existing_file.resolve()

    def test_raises_when_read_access_required_and_path_unreadable(
            self, existing_file, allowed_dir, monkeypatch
    ):
        """A path should fail validation if it's not readable and readability
        is explicitly required.
        """
        def fake_access(path, mode):
            if mode == os.R_OK:
                return False
            return True

        monkeypatch.setattr(os, 'access', fake_access)

        with pytest.raises(UserException):
            validate_path(
                existing_file, allowed_dirs=[allowed_dir], require_read=True
            )

    def test_readable_path_passes_when_read_access_required(
            self, existing_file, allowed_dir, monkeypatch
    ):
        """A readable path should pass validation if everything else
        is fine.
        """
        monkeypatch.setattr(os, 'access', lambda path, mode: True)

        result = validate_path(
            existing_file, allowed_dirs=[allowed_dir], require_read=True
        )
        assert result == existing_file.resolve()

    def test_write_access_not_checked_when_false(
            self, existing_file, allowed_dir, monkeypatch
    ):
        """Write access shouldn't be checked when require_write=False.
        """
        def fake_access(path, mode):
            if mode == os.W_OK:
                raise AssertionError(
                    'write access should not be checked.'
                )
            return True

        monkeypatch.setattr(os, 'access', fake_access)

        result = validate_path(
            existing_file, allowed_dirs=[allowed_dir], require_write=False
        )
        assert result == existing_file.resolve()

    def test_raises_when_write_required_and_path_not_writable(
            self, existing_file, allowed_dir, monkeypatch
    ):
        """A non-writable path should raise an exception if require_write=True
        """
        def fake_access(path, mode):
            if mode == os.W_OK:
                return False
            return True

        monkeypatch.setattr(os, 'access', fake_access)

        with pytest.raises(UserException):
            validate_path(
                existing_file, allowed_dirs=[allowed_dir], require_write=True
            )

    def test_writable_path_passes_when_write_required(
            self, existing_file, allowed_dir, monkeypatch
    ):
        """A writable path should pass validation if everything else is
        valid.
        """
        monkeypatch.setattr(os, 'access', lambda path, mode: True)

        result = validate_path(
            existing_file, allowed_dirs=[allowed_dir], require_write=True
        )
        assert result == existing_file.resolve()
