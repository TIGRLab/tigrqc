"""This is another temporary script for prototyping my filesystem parsing
system / name parsing system.
"""
import re
import json
import yaml
# from typing import Dict, Any

from pathlib import Path

# from pydantic import BaseModel, Field, field_validator


# Define 'contract' here for what a naming convention + dataset conf must
# provide (i.e. fields needed for subject-level or scan-level data creation)
#   -> Expose a 'required' versus 'optional' set of fields from the tables
#       themselves?


# class NameScheme(BaseModel):
#     """Validator for naming schemes.
#     """

# Yaml for now, accept json etc. later too.
def read_name_convention(conf_path: Path):
    """Read and validate a name convention config file

    To do:
        - Support for various formats
        - error handling
        - schema validation (reusable for all formats and input sources)
        - type hints
    """
    # Need error handling
    conf_contents = conf_path.read_text(encoding='utf-8')
    # Ditto
    config = yaml.safe_load(conf_contents)
    # Validation etc.
    return config


def read_json(fname):
    return json.loads(fname.read_text(encoding='utf-8'))


def make_and_validate(name_conf):
    """Fill and valid a name conf.
    """
    return


def create_field(fname, re_str):
    """Wrap a regex in a group and make sure it can be compiled.
    """
    group = f'(?P<{fname}>{re_str})'
    try:
        re.compile(group)
    except re.error as e:
        raise Exception(f'Failed to make regex for group {fname} - {str(e)}')
    return group


def create_template(tname, re_str, name_conf):
    """Fill in templates with fields, wrap it in a group, then test it compiles.
    """
    try:
        template = re_str.format_map(name_conf)
    except KeyError as e:
        raise Exception(
            f'Template {tname} references non-existent field - {str(e)}'
        )

    group = create_field(tname, template)
    return group


# def finalize_name_conf(name_conf):
#     """Compile the regexes so they can be used for parsing file system items.
#     """
#     finalized = {}
#     for fname, re_str in name_conf.items():
#         finalized[fname] = re.compile(re_str)
#     return finalized
def compile_path(path_regexes, name_conf):
    result = []
    for dir_level in path_regexes:
        level = []
        for alt_pattern in dir_level:
            # Error handling needed for both parts
            filled = alt_pattern.format_map(name_conf)
            level.append(re.compile(filled))
        result.append(level)
    return result


def load_dataset_conf(conf_path, name_conf):
    """Read a dataset configuration file and validate it / handle its
    regexes.
    """
    # Need generic file reading
    contents = read_name_convention(conf_path)

    # Fix timepoint_dir paths
    contents['timepoint_dir'] = compile_path(
        contents['timepoint_dir'], name_conf
    )

    if 'append_path' in contents:
        contents['append_path'] = compile_path(
            contents['append_path'], name_conf
        )

    # Need conditional here if 'find' is ever optional
    items = []
    for file_conf in contents['find']:
        # 'append_path' overrides top level rather than extending it
        if 'append_path' in file_conf:
            file_conf['append_path'] = compile_path(
                file_conf['append_path'], name_conf
            )
        elif 'append_path' in contents:
            # Slot in the path from top level
            file_conf['append_path'] = contents['append_path']
        else:
            file_conf['append_path'] = []

        # pattern must be present, error handling needed
        pat = file_conf['pattern'].format_map(name_conf)
        file_conf['pattern'] = re.compile(pat)

        items.append(file_conf)

    contents['find'] = items
    return contents


def read_source_dir(source_dir, dataset_conf, name_conf):
    """Use a name_conf and a dataset_conf to read a source_directory.
    """
    # Use timepoint_dir to find usable directories / report unusable

    # Use find to locate specific files

    # Use group_by to collect files and share attributes among them when
    # needed.

    # Use validators to sort through and find seemingly-usable but actually
    # incorrect items.

    # Then from whatever is left at final pass, make database items.
    return



def collect_dirs(start_dir, path_regexes, level=0, parsed=None, children=None):
    children = children or start_dir.iterdir()
    regexes = path_regexes[level]
    parsed = parsed or {}
    matches = []
    fails = []

    for subdir in children:
        if not subdir.is_dir():
            # Might want to optionally report non-dirs at this point as errors.
            continue

        match = None
        for alt_pattern in regexes:
            m = alt_pattern.match(subdir.name)
            if m:
                match = m
                break

        if match is None:
            fails.append(f'{subdir} invalid path format.')
            continue

        merged_fields = {**parsed, **match.groupdict()}

        if level == (len(path_regexes) - 1):
            merged_fields['path'] = subdir
            matches.append(merged_fields)
        else:
            subdir_matches, subdir_fails = collect_dirs(
                subdir,
                path_regexes,
                level + 1,
                merged_fields,
            )
            matches.extend(subdir_matches)
            fails.extend(subdir_fails)

    return matches, fails


def validate_bids_dir_structure(matches, fails, pass_sessions=True):
    """Validate that the sub-directories in each subject dir matches the
    bid convention. Report ones that don't and ensure correct directory
    is used when optional session sub-dir is omitted.
    """
    subjects = group_by_keys(matches, ['subject'])

    matches = []
    for subject in subjects:
        subdirs = subjects[subject]
        # Make sure 'data_type' dirs are only found if ses-XX dirs omitted
        # Also, ensure parent dir is used if ses-XX dir wasn't used.
        sessions = []
        data_types = []
        for subdir in subdirs:
            if 'session' in subdir:
                sessions.append(subdir)
            else:
                data_types.append(subdir)

        if sessions and data_types:
            if not pass_sessions:
                subject = sessions[0]['path'].parent
                fails.append(
                    'Invalid BIDS structure: Subject contains a mix of '
                    f'session dirs and data type dirs - {subject}'
                )
            matches.extend(sessions)
            for entry in data_types:
                fails.append(
                    'Invalid bids format: Datatype folder found alongside '
                    f'session dir(s) - {entry["path"]}'
                )
        elif sessions:
            matches.extend(sessions)
        elif data_types:
            # Only take the first one, and change its path to the parent dir
            entry = data_types[0]
            del entry['data_type']
            entry['path'] = entry['path'].parent
            matches.append(entry)
    return matches, fails


from collections import defaultdict
def group_by_keys(dicts, keys):
    groups = defaultdict(list)
    for d in dicts:
        group_key = tuple(d[k] for k in keys)
        groups[group_key].append(d)
    return groups


def collect_files(start_path, find_conf):
    """Collect every item in 'find'.
    """
    files = []
    fails = []

    for path in start_path.rglob('*'):
        if not path.is_file():
            continue

        dir_parts = path.relative_to(start_path).parts[:-1]

        result = _parse_file(path, dir_parts, find_conf)

        if result:
            files.append(result)
        else:
            fails.append(
                f'Unrecognized file - {path}'
            )

    return files, fails


def _parse_file(path, dir_parts, find_conf):
    parsed = None
    for entry in find_conf:
        match = entry['pattern'].match(path.name)
        if match:
            parsed = match.groupdict()
            parsed['path'] = path
            parsed['label'] = entry['label']
            break

    # This file doesn't match any expected file type
    if not parsed:
        return None

    append_path = entry.get('append_path')
    if append_path:
        # sub-path must match too
        if len(dir_parts) != len(append_path):
            return None

        for part, alternatives in zip(dir_parts, append_path):
            subdir_match = None
            for alt in alternatives:
                m = alt.match(part)
                if m:
                    subdir_match = m
                    break

            if not subdir_match:
                return None

            parsed = {**parsed, **subdir_match.groupdict()}

    load_conf = entry.get('load_vals')
    if not load_conf:
        return parsed

    if load_conf['format'] == 'json':
        # At this point the path is relative. Should probably have an absolute
        # and confirmed safe path (source dirs are confirmed to be safe so
        # maybe fine as long as not relative)
        contents = read_json(path)
    else:
        # Other formats go here, unrecognize should be an error.
        contents = {}

    # Need to declare required or optional values to read...
    # Also need to report failure here somehow.
    for file_key, store_key in load_conf['values'].items():
        value = contents.get(file_key)
        parsed[store_key] = value

    return parsed
