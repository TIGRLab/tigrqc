"""Tests for tigrqc.models.project.py
"""
import pytest

from tigrqc.exceptions import InvalidDataException
from tigrqc.models import Project

VALID_IDS = [
    'someProject',
    'abc123',
    'ABC123',
    'AbC',
    '123',
]

INVALID_IDS = [
    'ab',
    '2',
    '@bc$',
    'some-Project',
    'some project',
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
]


class TestProjectIdValidator:
    """Tests that the Project model validates project IDs.
    """

    @pytest.mark.parametrize('valid_id', VALID_IDS)
    def test_accepts_valid_ids(self, valid_id):
        """Accept alphanumeric IDs >=3 chars and <=32 chars.
        """
        project = Project(id=valid_id)
        assert project.id == valid_id

    @pytest.mark.parametrize('invalid_id', INVALID_IDS)
    def test_exception_when_incorrect_length_or_non_alphanumeric(
            self, invalid_id
    ):
        """Refuse non-alphanumeric IDs and those too short / too long.
        """
        with pytest.raises(InvalidDataException):
            Project(id=invalid_id)

    def test_exception_when_valid_id_changed_to_invalid(self):
        """Reject ID changes that add non-alphanumeric chars or invalid length.
        """
        project = Project(id='SPN30')
        assert project.id == 'SPN30'

        with pytest.raises(InvalidDataException):
            project.id = '30'

        with pytest.raises(InvalidDataException):
            project.id = '@@@'
