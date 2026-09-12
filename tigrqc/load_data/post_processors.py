"""Defines post-processors available to users during data import.
"""
from typing import Callable
from collections import defaultdict


def validate_bids_dir_structure(
        matches: list[dict], *, pass_sessions: bool = True
):
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


def group_by_keys(dicts, keys):
    groups = defaultdict(list)
    for d in dicts:
        group_key = tuple(d[k] for k in keys)
        groups[group_key].append(d)
    return groups


# This should probably be collected programmatically, maybe add
# decorator or something like elsewhere.
POST_PROCESSORS: dict[str, Callable] = {
    'validate_bids_dir_structure': validate_bids_dir_structure,
}
