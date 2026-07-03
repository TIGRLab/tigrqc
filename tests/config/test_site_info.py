"""Tests for the site_info configuration module
"""
from pathlib import Path
from unittest.mock import patch

from tigrqc.config.site_info import get_data_dirs


class TestGetDataDirs:
    """Tests for tigrqc.config.site_info.get_data_dirs
    """
    def test_empty_string_returns_empty_list(self):
        """An empty string should be equivalent to no paths being given.
        """
        assert get_data_dirs('') == []

    def test_ignores_files(self, tmp_path):
        """If the user includes a file in the path list it should be ignored.
        """
        file_path = tmp_path / 'config.yaml'
        file_path.write_text('contents')

        result = get_data_dirs(str(file_path))

        assert result == []

    def test_paths_are_resolved(self, tmp_path):
        """Ensure outputed paths are resolved.
        """
        path = tmp_path / 'subdir'
        path.mkdir()

        result = get_data_dirs(str(path / '..' / 'subdir'))

        assert result == [path]

    def test_returns_directory_if_exists_and_read_and_write_possible(
            self, tmp_path
    ):
        """A directory that is read/write-able and exists should be included.
        """
        result = get_data_dirs(str(tmp_path))
        assert result == [tmp_path.resolve()]

    def test_ignores_directory_without_read_or_write_permission(
            self, tmp_path
    ):
        """A directory that can't be read or written should be ignored.
        """
        with patch('tigrqc.config.site_info.os.access', return_value=False):
            result = get_data_dirs(str(tmp_path))

        assert result == []

    def test_creates_nonexistent_directory(self, tmp_path):
        """If a path that doesn't exist it should be made.
        """
        new_dir = tmp_path / 'new_dir'

        result = get_data_dirs(str(new_dir))

        assert new_dir.exists()
        assert result == [new_dir.resolve()]

    def test_ignores_directory_that_cannot_be_created(self, tmp_path):
        """Ignore a directory that doesn't exist and can't be made
        """
        missing = tmp_path / 'uncreatable'

        with patch.object(Path, 'mkdir', side_effect=OSError):
            result = get_data_dirs(str(missing))

        assert result == []

    def test_handles_multiple_directories(self, tmp_path):
        """Multiple colon-separated paths should be accepted.
        """
        dir1 = tmp_path / 'dir1'
        dir2 = tmp_path / 'dir2'
        dir3 = tmp_path / 'dir3'

        result = get_data_dirs(f'{dir1}:{dir2}:{dir3}')

        assert len(result) == 3
        for item in [dir1, dir2, dir2]:
            assert item.resolve() in result

    def test_returns_only_valid_directories_when_mixed(self, tmp_path):
        """If some dirs are usable and some aren't only include usable.
        """
        good = tmp_path / 'good'
        bad = tmp_path / 'bad'

        good.mkdir()

        def mock_access(path, _):
            return path == good

        with patch(
                'tigrqc.config.site_info.os.access', side_effect=mock_access
        ):
            result = get_data_dirs(f'{good}:{bad}')

        assert result == [good.resolve()]

    def test_duplicate_paths_only_included_once(self, tmp_path):
        """If the same path is present repeatedly, only one instance is used.
        """
        result = get_data_dirs(f'{tmp_path}:{tmp_path}')

        assert result == [tmp_path.resolve()]

    def test_ignores_relative_paths(self, tmp_path, monkeypatch):
        """For security reasons relative paths should be ignored.
        """
        monkeypatch.chdir(tmp_path)

        relative = Path('relative_dir')
        relative.mkdir()

        result = get_data_dirs('relative_dir')

        assert result == []
