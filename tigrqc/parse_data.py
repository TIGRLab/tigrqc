"""This is another temporary script for prototyping my filesystem parsing
system / name parsing system.
"""
import re
import json
import yaml
# from typing import Dict, Any

from pathlib import Path

from tigrqc.models import (Timepoint, Attempt, Series, SourceDir, TimepointDir,
                           File, InvalidData, get_or_create)

# from pydantic import BaseModel, Field, field_validator


# Define 'contract' here for what a naming convention + dataset conf must
# provide (i.e. fields needed for subject-level or scan-level data creation)
#   -> Expose a 'required' versus 'optional' set of fields from the tables
#       themselves?


# class NameScheme(BaseModel):
#     """Validator for naming schemes.
#     """

# Yaml for now, accept json etc. later too.
def read_yaml(conf_path: Path):
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


def make_and_validate(config_path):
    """Fill and valid a name conf.

    Take contents of config file and create a 'name_conf' populated regex map
    """
    config = read_yaml(config_path)
    field_map = config.get('field_map', {})

    name_conf = {}
    for fname, re_str in config['fields'].items():
        # Allow users to rename groups as needed
        group_name = field_map.get(fname, fname)
        name_conf[fname] = create_field(group_name, re_str)

    for tname, re_str in config['templates'].items():
        # Allow users to rename groups as needed
        group_name = field_map.get(tname, tname)
        name_conf[tname] = create_template(group_name, re_str, name_conf)

    # Check that functions exist, scope is valid, and args are correct
    validators = {}
    for item in config.get('validation', {}):
        scope = item['scope']
        del item['scope']

        for scope_type in scope:
            # Maybe should be default dict
            validators.setdefault(scope_type, []).append(item)

    return name_conf, validators


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


def load_dataset_conf(conf_path, name_conf, validators=None):
    """Read a dataset configuration file and validate it / handle its
    regexes.
    """
    validators = validators or {}
    # Need generic file reading
    contents = read_yaml(conf_path)

    # Fix timepoint_dir paths
    contents['timepoint_dir'] = compile_path(
        contents.get('timepoint_dir', []), name_conf
    )

    if 'append_path' in contents:
        contents['append_path'] = compile_path(
            contents['append_path'], name_conf
        )

    # Collect validators by scope (the code that ultimately handles
    # this must also verify they exist, their arguments are valid, their
    # scopes are valid, etc.)
    for item in contents.get('validation', {}):
        scope = item['scope']
        del item['scope']
        for scope_type in scope:
            validators.setdefault(scope_type, []).append(item)

    contents['validation'] = validators

    compiled_entries = []
    for entry in contents.get('find', []):
        if 'append_path' in entry:
            entry['append_path'] = compile_path(
                entry['append_path'], name_conf
            )
        elif 'append_path' in contents:
            # use the top level append_path, if entry doesn't override
            entry['append_path'] = contents['append_path']
        else:
            entry['append_path'] = []

        if not isinstance(entry['pattern'], list):
            entry['pattern'] = [entry['pattern']]

        patterns = []
        for item in entry['pattern']:
            pat = item.format_map(name_conf)
            patterns.append(re.compile(pat))

        entry['pattern'] = patterns
        compiled_entries.append(entry)

    contents['find'] = compiled_entries

    # accepted_file_types = [
    #     'dataset_files',
    #     'timepoint_files',
    #     'attempt_files',
    #     'series_files'
    # ]
    # for file_type in accepted_file_types:
    #     entries = contents.get(file_type, [])
    #     items = []
    #     for file_conf in entries:
    #         if 'append_path' in file_conf:
    #             file_conf['append_path'] = compile_path(
    #                 file_conf['append_path'], name_conf
    #             )
    #         elif 'append_path' in contents:
    #             # Slot in the path from top level
    #             file_conf['append_path'] = contents['append_path']
    #         else:
    #             file_conf['append_path'] = []

    #         # pattern must be present, error handling needed
    #         # Must handle both plain pattern and list of patterns...
    #         if not isinstance(file_conf['pattern'], list):
    #             file_conf['pattern'] = [file_conf['pattern']]
    #         patterns = []
    #         for item in file_conf['pattern']:
    #             pat = item.format_map(name_conf)
    #             patterns.append(re.compile(pat))
    #         file_conf['pattern'] = patterns

    #         items.append(file_conf)

    #     contents[file_type] = items

    return contents


def collect_dirs(start_dir, path_regexes, level=0, parsed=None, children=None):
    if not path_regexes:
        # No paths required ??
        return [], []

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


def validate_bids_dir_structure(matches, pass_sessions=True):
    """Validate that the sub-directories in each subject dir matches the
    bid convention. Report ones that don't and ensure correct directory
    is used when optional session sub-dir is omitted.
    """
    subjects = group_by_keys(matches, ['subject'])

    fails = []
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
        for pattern in entry['pattern']:
            match = pattern.match(path.name)
            if match:
                parsed = match.groupdict()
                parsed['path'] = path
                parsed['label'] = entry['label']
                break
        if match:
            # Dear god... please clean this up
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


def validate_series_outputs(
        files, group_by=['fname'],
        required_labels=['raw_scan', 'sidecar'],
        share_fields=None,
):
    """Confirm that output files per series contain all expected files and attributes.

    For raw data for example, every series must produce a sidecar and nifti and
    every file must contain series number and description info.

    Anything not a 'required_type' is an optional file (because the regexes
    themselves have already filtered out others)
    """
    # Make required_labels a dict that details num expected (optionally,
    # -1 for 1+)
    share_fields = share_fields or []

    series = group_by_keys(files, group_by)

    passes = []
    fails = []
    for group, file_group in series.items():
        # Validate all required file types exist per file group
        missing_labels = []
        for label in required_labels:
            if not any(item['label'] == label for item in file_group):
                missing_labels.append(label)

        if missing_labels:
            fails.append(f'{group} missing required file types: {missing_labels}')
            continue

        if not share_fields:
            passes.extend(file_group)
            continue

        missing_fields = []
        mismatched_fields = []
        for field in share_fields:
            matches = [item for item in file_group if field in item]
            if not matches:
                missing_fields.append(field)
                continue
            value = matches[0][field]
            if len(matches) > 1:
                # This may need to be more complex if a field value can
                # be anything but a string/int/path (e.g. lists... with same
                # items in diff order...)
                if not all(item[field] == value for item in matches):
                    mismatched_fields.append(field)
                    continue

            for item in file_group:
                item[field] = value

        if missing_fields:
            fails.append(
                f'{group} - missing expected fields {missing_fields}'
            )
        if mismatched_fields:
            fails.append(
                f'{group} - contains conflicting values for some fields {mismatched_fields}'
            )

        if not missing_fields and not mismatched_fields:
            passes.extend(file_group)

    return passes, fails


# def validate_id_fields_match_expected_values(
#         items, study_conf, match_site=False, match_study=False
# ):
#     """Checks that actual observed field values match configured values.
#     """
#     # How will this handle studies that have multiple study codes with
#     # their own restricted site values... i.e. STU1_SIT1 is ok but STU1_SIT2 not
#     # even though another code in the study allows SIT2
#     passes = []
#     fails = []

#     if match_study:


def read_source_dir(source_path, name_conf_path, dataset_conf_path):
    """Read all data from a directory and create/update database records.
    """
    # Placeholder until I'm ready to start populating the DB
    results = {
        'fails': []
    }

    # Prep naming convention info (this final object should be the
    # input once past prototype phase, i.e. do this elsewhere/load from db)
    name_conf, validators = make_and_validate(name_conf_path)
    # This should handle validators also. Must have dict with scoping...
    # Also need to figure out how to validate the input args to validators.
    dataset_conf = load_dataset_conf(dataset_conf_path, name_conf, validators)

    ####################################
    # Get dataset-wide files first.
    found, fails = collect_files(source_path, dataset_conf['dataset_files'])
    # Run validators, if any apply
    dataset_validators = dataset_conf.get('validation', {}).get('dataset', [])
    for entry in dataset_validators:
        func = VALIDATORS[entry['use']]
        found, validator_fails = func(
            found,
            **entry.get('args', {})
        )
        fails.extend(validator_fails)

    results['dataset_files'] = found
    results['dataset_fails'] = fails

    ###################################
    # Retrieve timepoint dirs
    # How to defer dir record creation when more info is required from found
    # files?
    timepoint_dirs, tp_dir_fails = collect_dirs(
        source_path, dataset_conf['timepoint_dir']
    )

    # Run timepoint post processors (?)

    # Run timepoint validators here, if any
    # By this point all validator function names must have been checked
    # to avoid typos etc.
    # Must skip this when no timepoints required yet (or at all...)
    tp_validators = dataset_conf.get('validation', {}).get('timepoint', [])
    for entry in tp_validators:
        func = VALIDATORS[entry['use']]
        # Args may be optional...
        # Enable configurable error messages?
        timepoint_dirs, validator_fails = func(
            timepoint_dirs,
            **entry['args']
        )
        tp_dir_fails.extend(validator_fails)

    results['timepoint_dirs'] = timepoint_dirs
    results['timepoint_dirs_fails'] = tp_dir_fails

    ####################################
    # Retrieve timepoint files

    # Sort items by whether they should be nested in timepoint_dir or not
    tp_entries, stray_entries = sort_file_entries(
        dataset_conf.get('timepoint_files', []),
        dataset_conf.get('timepoint_dirs', [])
    )
    tp_validators = dataset_conf.get('validation', []).get('timepoint', [])

    tp_strays, tp_stray_fails = collect_files(source_path, stray_entries)
    # Validation goes here
    results['tp_strays'] = tp_strays
    results['tp_stray_fails'] = tp_stray_fails

    # This won't group files by timepoint_dir currently? Maybe change
    # collect_files to embed parent (in addition to making paths relative)
    tp_files = []
    tp_file_fails = []
    for timepoint in timepoint_dirs:
        found, f_fails = collect_files(timepoint['path'], tp_entries)
        tp_files.extend(found)
        tp_file_fails.extend(f_fails)
    # Validation goes here
    results['tp_files'] = tp_files
    results['tp_file_fails'] = tp_file_fails

    # Add timepoints to database here, unless conf says to 'defer'

    # Find all items as requested
    # use the database record here? (what about defer...)
    files = []
    file_fails = []
    for timepoint in timepoint_dirs:
        found, f_fails = collect_files(timepoint['path'], dataset_conf['find'])
        files.extend(found)
        file_fails.extend(f_fails)

    # Run series post processors (e.g. field sharing...)

    # Run series validators
    series_validators = dataset_conf.get('validation', {}).get('series', [])
    for entry in series_validators:
        func = VALIDATORS[entry['use']]
        files, validator_fails = func(
            files,
            **entry['args']
        )
        file_fails.extend(validator_fails)

    # Run lookups (i.e. matching secondary data to primary)

    # Add deferred timepoint entries to database

    # Add series to database

    return timepoint_dirs, files, tp_fails, file_fails


def validate_id_fields_match_expected_values(items, check_site=False, check_study=False):
    """Placeholder until I'm ready to deal with this.
    """
    return items, []


def validate_all_human_or_all_phantom_data(items):
    """Placeholder
    """
    return items, []


def validator_placeholder(items):
    print(f'Validator ran on {len(items)} objects.')
    return items, []


VALIDATORS = {
    'validate_id_fields_match_expected_values': validate_id_fields_match_expected_values,
    'validate_bids_dir_structure': validate_bids_dir_structure,
    'validate_series_outputs': validate_series_outputs,
    'validate_all_human_or_all_phantom_data': validate_all_human_or_all_phantom_data,
    'validator_placeholder': validator_placeholder
}


def sort_file_entries(entries, dir_conf):
    """Separate entries that should be stored in a timepoint_dir from 'stray'
    entries that can reside anywhere but still definitely hook to a specific
    timepoint/attempt/series.
    """
    if not dir_conf:
        # If the user didn't configure timepoint_dir it's safe to assume
        # all files are 'stray'
        return [], entries

    tp_entries = []
    stray_entries = []
    for item in entries:
        if item.get('ignore_tp_dir', False):
            stray_entries.append(item)
        else:
            tp_entries.append(item)
    return tp_entries, stray_entries


def make_parseable(entry_list, timepoint_dir=None):
    """Take a list of file entries and make them parseable.
    """
    timepoint_dir = timepoint_dir or []
    sub_entries = []
    parseable = []
    for entry in entry_list:
        scope = entry.get('scope', 'series')
        is_stray = entry.get('stray_file', False)
        if scope == 'dataset' or is_stray or not timepoint_dir:
            dir_path = entry.get('append_path', [])
            parseable.append((dir_path, entry))
        else:
            sub_entries.append((entry.get('append_path'), entry))

    if timepoint_dir:
        *fake_append_path, fake_pattern = timepoint_dir
        tp_dir = {
            'append_path': fake_append_path,
            'pattern': fake_pattern,
            'sub_entries': sub_entries
        }
        parseable.append((fake_append_path, tp_dir))
    return parseable


def make_tree(parseable_nodes):
    files = {}
    dirs = {}

    for path, entry in parseable_nodes:
        # If the exact same path/file regex applies to more than 1 entry it's
        # an exception.
        if path == []:
            if 'sub_entries' in entry:
                # This is a timepoint dir, recursively set up its children.
                for alt_pattern in entry['pattern']:
                    node = make_tree(entry['sub_entries'])
                    node['tp_dir'] = True
                    files[alt_pattern] = node
            else:
                for regex in entry['pattern']:
                    if regex in files:
                        # This should be an exception and caught earlier.
                        print(f'Duplicate file pattern given: {regex}')
                        continue
                    files[regex] = entry
        else:
            # Gather every directory entry first before you recurse, to
            # catch redundancies up front.
            current_dir, *remaining = path
            for alt_pattern in current_dir:
                dirs.setdefault(alt_pattern, []).append((remaining, entry))

    final_dirs = {}
    for regex, entry in dirs.items():
        node = make_tree(entry)
        final_dirs[regex] = node

    return {'items': files, 'dirs': final_dirs}

# def create_nested_paths(find_items):
#     """Take a list of tuples (append_path, entry) and create recursive
#     entries for them.
#     """
#     dir_level = {}
#     recurse = []
#     for entry in find_items:
#         if entry[0] == []:
#             for pattern in entry[1]['patterns']:


# from dataclasses import dataclass, field

# @dataclass
# class TreeNode:
#     # File entries that may match at this level.
#     files: list
#     # Subdirectories that may be further traversed
#     children: list
#     # if this is a timepoint_dir, then this will be a second set of configuration
#     # entries that may be nested within it.
#     sub_entries: list
#     # The regex pattern for a directory level. Only root node may be None.
#     regex: re.Pattern = None

# @dataclass
# class FileMatch:
#     path: Path
#     match_entry: dict
#     path_fields: dict

# class TreeNode:
#     """Turn configuration into a properly nested directory tree.
#     """
#     # file_entries = list of tuple(regex, entry)
#     # children = list of TreeNode
#     # save_dir = False -> True if it's a timepoint_dir. Stop traversal when
#     #   found. It's 'leafy'.


def parse_tree_source(source_path, conf_tree, collected=None):
    """Use a tree version of the conf to identify correct and incorrect dir
    items.
    """
    collected = collected or {}
    found = {
        'tp_dirs': [],
        'files': [],
    }
    # This should be optional to gather.
    fails = []

    for item in source_path.iterdir():
        entry = None
        for item_regex in conf_tree['items']:
            match = item_regex.match(item.name)
            if match:
                entry = match.groupdict()
                entry['path'] = item
                entry['conf'] = conf_tree['items'][item_regex]
                break

        if entry:
            all_vals = {**collected, **entry}
            # Found a match to a terminal item.
            if entry['conf'].get('tp_dir', False):
                found['tp_dirs'].append(all_vals)
            else:
                found['files'].append(all_vals)
            continue

        # No terminal item matched. If the item is not a dir, this is an error.
        if not item.is_dir():
            fails.append(f"Unknown file found - {item}")
            continue

        match = None
        for dir_regex in conf_tree['dirs']:
            m = dir_regex.match(item.name)
            if m:
                match = m
                entry = {**collected, **match.groupdict()}
                conf = conf_tree['dirs'][dir_regex]
                break

        if not match:
            fails.append(f"Unknown directory found - {item}")
            continue

        # Collect files recursively from this directory
        subdir_results, subdir_fails = parse_tree_source(item, conf, entry)
        found['tp_dirs'].extend(subdir_results['tp_dirs'])
        found['files'].extend(subdir_results['files'])
        fails.extend(subdir_fails)

    return found, fails

