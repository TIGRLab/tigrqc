"""Code for reading data from the file system and adding it to the database.
"""
import json
import yaml
from pathlib import Path


def read_json(file_path: Path):
    # need error handling :)
    contents = file_path.read_text(encoding='utf-8')
    return json.loads(contents)


def read_yaml(file_path: Path):
    # Need error handling :)
    contents = file_path.read_text(encoding='utf-8')
    return yaml.safe_load(contents)


# Helpers for ingesting different file formats.
FILE_READERS = {
    'json': read_json,
    'yaml': read_yaml,
}
