"""Handles the reading of datasets (regardless of type or name scheme).
"""
from dataclasses import dataclass, field
import glob
import json
import os
import re
from abc import ABC
from pathlib import Path

from tigrqc.exceptions import TigrQcException
from tigrqc.models import Timepoint, Attempt, Series, SourceDir, TimepointDir, File, InvalidData
from tigrqc.models import get_or_create

# To do:
#   - Implement overrides of templates + patterns (but must constrain it to
#       avoid user incident... How to be flexible without matching all or
#       none by accident?)
#   - Verify these match all intended + none of unintended per name scheme
#   - Add in interface for all required info (e.g. repeats from bids,
#       all expected files from a folder)


# When comparing against a list of site codes:
#   - Always sort the codes by length in a descending fashion (if differ in length)
#   - Join the result with re.escape(code) and the '|' operator.


# Can use re.groupdict() to get an itemized list of all groups defined
#   -> So if nested subgroups can theoretically discover if study / site exist
#       in another component
#   -> Might want to also through a group around the entire expression?
#       and have nested 'session' but not sure if necessary for my purposes yet..

# @dataclass
# class ParsedID:
#     raw: str
#     fields: dict
#     valid: bool
#     errors: list = field(default_factory=list)



class NameConvention(ABC):
    """The interface that must be implemented to make a valid name convention.
    """

    templates: dict = {}                    # Must contain a template for
                                            # each 'type' that must be parseable
                                            # e.g. subject, session, file
                                            # At a minimum should define subject
    default_patterns: dict = {}             # Default regexes to be slotted into templates

    def __init__(self, patterns: dict | None = None,
                 field_validation: dict | None = None
    ):
        patterns = patterns or {}
        field_validation = field_validation or {}
        self.validation = field_validation
        self.patterns = {**self.default_patterns, **patterns}
        self.regexes = self._compile()

    def _compile(self) -> re.Pattern:
        """Compile regexes from the given templates and patterns.
        """
        regexes = {}
        for template_type, template in self.templates.items():
            for name, item in self.patterns.items():
                token = "{" + name + "}"
                if token in template:
                    template = template.replace(token, f'(?P<{name}>{item})')

            try:
                regexes[template_type] = re.compile(template)
            except re.error as e:
                raise TigrQcException(
                    f'Invalid regex {template} constructed '
                    f'for {self.__class__.__name__} for template '
                    f'{template_type}'
                ) from e

        return regexes

    # def parse_as_id(self, item):
    #     return

    # def parse_as_session(self, item):
    #     return

    # def parse_as_file(self, item):
    #     return
    def parse_id(self, item):
        """Parse a full subject ID and do minimal study / site validation.
        Validator format is:
            {
                'studycode': ['site1', 'site2', 'site3']
            }
        Use 'any' to skip study validation and only validate site. Leave
        site list empty to skip site validation.
        """
        result = self.regexes['subject'].match(item)
        if not result:
            if 'phantom' not in self.regexes:
                # No phantoms so definitely not a match
                return None

            result = self.regexes['phantom'].match(item)
            if not result:
                # ID doesn't match basic ID format of this convention
                return None
            # ID is a phantom, so proceed

        if not self.validation:
            # No field validation required, so return parsed ID
            return result

        if 'any' in self.validation:
            # Only site validation needed.
            if result.group('site') in self.validation['any']:
                # Site is valid
                return result
            # Site failed validation
            return None

        if result.group('study') in self.validation:
            # Study is valid, now check site
            if not self.validation[result.group('study')]:
                # No site validation needed, so return parsed ID
                return result

            if result.group('site') in self.validation[result.group('study')]:
                # Site is valid also
                return result

        # Validation failed
        return None


class DatmanConvention(NameConvention):
    """A parser for the datman naming scheme.
    """
    # Naming of each type of template needs a tweak...
    templates: dict = {
        'subject': '^{study}_{site}_{subid}_{timepoint}$',
        'session': '^{study}_{site}_{subid}_{timepoint}_{session}$',
        'phantom': '^{study}_{site}_PHA_{subid}$',
        # 'file': '{study}_{site}_{subid}_{timepoint}_{repeat}_{tag}_{series}_{description}',
    }
    # This was taken from datman.scanid. There, though, we have extra bits
    # to prevent matching KCNI IDs (or phantoms). Also, it's maximally permissive...
    # Should probably be tightened to better reflect what we actually _expect_ it to be
    # in practice, like omitting the SE + MR and ensure session/timepoint are numeric
    default_patterns: dict = {
        'study': r'[^_]+',
        'site': r'[^_]+',
        'subid': r'(?!PHA)([^_]+)',
        'timepoint': r'[^_]+',
        'session': r'[^_]+',
    }
    # !!!!! The regex should maybe make session optional or something so it
    #       can handle the timepoint folders....
    #       ... or maybe just have separate 'timepoint' one when its expected.
    #       but then fall back to more specific one for instances like resources?



class KCNIConvention(NameConvention):
    """A parser for the KCNI name convention
    """
    templates = {
        'subject': '^{study}_{site}_{subid}_{timepoint}_SE{session}_{modality}$',
        'phantom': '^{study}_{site}_{type}PHA_{subid}_{modality}$',
    }
    default_patterns: dict = {
        'study': r'[A-Z]{3}[0-9]{2}',
        'site': r'[A-Z]{3}',
        'subid': r'[A-Z0-9]{4,8}',
        'timepoint': r'[0-9]{2}',
        'session': r'[0-9]{2}',
        'modality': r'[A-Z]{2,4}',
    }


class BidsConvention(NameConvention):
    """A parser for the BIDs naming scheme.
    """
    templates: dict = {
        'subject': '^sub-{subid}$',
        'session': '^ses-{timepoint}$',
        # 'file': '^sub-{subid}_ses-{timepoint}_{entities}{suffix}{ext}$'
        # 'file': '^{entities}{suffix}{ext}$',
        # 'fields': '(?P<key>[A-Za-z0-9]+)-(?P<value>[A-Za-z0-9]+)',

    # This will parse a bids file name into its key-value pairs
    # Doesn't account for the expected ordering, validation of allowed keys and vals etc.
    #   but can be used to turn a bidsy-filename into a parseable dict very quickly.
    # Also, from here you'd want to grab the modality from the folders and
    #   get the json sidecars to give you the repeat (as well as reading them in)

    #     BIDS_FILENAME_RE = re.compile(
    # r"^(?P<entities>(?:[a-zA-Z0-9]+-[a-zA-Z0-9]+)(?:_[a-zA-Z0-9]+-[a-zA-Z0-9]+)*)"
    # r"_(?P<suffix>[a-zA-Z0-9]+)"
    # r"(?P<extension>\.[a-zA-Z0-9.]+)$")
    }
    default_patterns: dict = {
        'subid': r'(?P<site>[A-Z]{3})(?P<id>[A-Z0-9]+)',
        'timepoint': r'[0-9]{2}',
        # 'entities': r'(?P<entities>(?:[A-Za-z0-9]+-[A-Za-z0-9]+_)*)',
        # 'suffix': r'(?P<suffix>[A-Za-z0-9]+)?',
        # 'ext': r'(?P<extension>\.[A-Za-z0-9.]+)?',
    }


# class BidsSeries:

#     def __init__(self, file_path: Path):



# Types of local data
#   - nii/json (dm or bids varieties)
#       - dm timepoint / all nii + jsons single level (bvec/bval sometimes)
#       - bids sub / bids ses / modalities / nii + jsons (bvec/bval sometimes)
#   - QC    (dm currently, should be bids later...)
#       - dm timepoint / all metrics
#   - Tech notes    (dm currently, ditto)
#       - dm session / optional subdirs / pdf

def read_dataset(
        path: Path, name_scheme: str, enforce_site: str | None = None,
) -> list:
    """Read (or re-read) a dataset from the filesystem.

    !!!!!! Update return type later.

    Take a path from the database and the declared name convention to validate
    format, and optionally allow enforcement of site codes + study codes
    if the convention uses them and valid types have been given.
    """
    # Implement for a fresh read
    # Implement for a refresh (handle removed + changed objects...)
    return


# def read_datman(
#         path: Path, data_type: str,
#         field_validation: dict[str, list[str]] | None = None
# ) -> dict[str, list]:
#     """Take a path, a data type, and a dictionary of study codes -> site codes
#         and find every valid + invalid item in the given path.

#     field_validation can be a dict of form:
#         {
#             'study_code1': ['SITE1', 'SITE2', ..., 'SITEN'],
#             ...
#             'study_codeN': ['SITEA', 'SITEB', ..., 'SITEZ']
#         }
#     And ID must match or whole thing fails, and then site must match secondarily.
#     OR it can be of the form:
#         {
#             'any': ['SITE1', ..., 'SITEN']
#         }
#     And study code validation will be skipped. Site code must match list.
#     OR to skip site code validation you can use:
#         {
#             'study_code1': [],
#             'study_code2': [],
#             ...
#             'study_codeN': []
#         }

#     Data type determines how the path contents will be parsed.
#     """


#     return


from flask_sqlalchemy import SQLAlchemy
def test_bids_load(
        db: SQLAlchemy,
        source_path: Path, bc: BidsConvention, project_id: str = 'PREDICTS',
        sourcedir_id: int = 1, site_id: str = 'CMH',
        study_code: str | None = None, site_code: str | None = None,
    ):
    # Update input args to take a source_dir, etc. rather than individual args

    for subject_dir in source_path.iterdir():
        if not subject_dir.is_dir():
            # Ignore top level non-dirs for now
            continue

        parsed_id = bc.parse_id(subject_dir.name)

        if not parsed_id:
            # Relying on parsing like this might falsely report PHA data as
            # invalid (oops). Gotta fix it.
            get_or_create(
                db.session,
                InvalidData,
                sourcedir_id=sourcedir_id,
                rel_path=subject_dir.name,
                other_fields={
                    'error_msg': 'Invalid BIDS subject ID.'
                },
            )
            continue

        # This is where code validation happens. Maybe need a 'reason' col
        # so the rejection reason can be reported here and above.
        study = parsed_id.group('study') if 'study' in parsed_id.groupdict() else ''
        site = parsed_id.group('site') if 'site' in parsed_id.groupdict() else ''
        subid = parsed_id.group('id') if 'id' in parsed_id.groupdict() else parsed_id.group('subid')

        if (study_code and study) and (study != study_code):
            # Failed study code validation. Report it.
            get_or_create(
                db.session,
                InvalidData,
                sourcedir_id=sourcedir_id,
                rel_path=subject_dir.name,
                other_fields={
                    'error_msg': (
                        f'BIDS ID contains invalid study code {study}.'
                    ),
                },
            )
            continue

        if (site_code and site) and (site != site_code):
            # Failed site code validation. Report it.
            get_or_create(
                db.session,
                InvalidData,
                sourcedir_id=sourcedir_id,
                rel_path=subject_dir.name,
                other_fields={
                    'error_msg': (
                        f'BIDS ID contains invalid site code {site}.'
                    ),
                },
            )
            continue

        if not subid:
            # No readable subid. Report it.
            get_or_create(
                db.session,
                InvalidData,
                sourcedir_id=sourcedir_id,
                rel_path=subject_dir.name,
                other_fields={
                    'error_msg': (
                        f'BIDS ID contains unreadable subid field.'
                    ),
                },
            )
            continue

        # Get session num and phantom info first.
        # Sigh. Need to account for PHA data... (match PHA string
        # in bids (?) ID +/- read it from the source dir table if they're
        # kept separate...)

        # How to report an empty timepoint dir? Ignoring seems bad.

        # All immediate dir children should either be ses-XX format OR
        # modality. Validate modalities if you can.
        children = {
            'session': [],
            'other': [],
        }
        for child in subject_dir.iterdir():
            if not child.is_dir():
                # Some files allowed in bids sub-XXXX dir, ignore
                continue
            session_id = bc.regexes['session'].match(child.name)
            if not session_id:
                children['other'].append(child)
            else:
                children['session'].append(
                    (child, session_id.group('timepoint'))
                )

        sessions = children['session']
        other = children['other']

        if sessions and other:
            # This is an error state. Report the 'other' dirs and process
            # sessions normally
            for subdir in other:
                get_or_create(
                    db.session,
                    InvalidData,
                    sourcedir_id=sourcedir_id,
                    rel_path=subdir.relative_to(source_path),
                    other_fields={
                        'error_msg': (
                            'BIDS subject dir should contain only 1) session '
                            'dirs or 2) modality dirs. Unknown directories found.'
                        ),
                    },
                )
            for sess_dir, num in sessions:
                test_bids_sess_load(db, subid, num, sess_dir, source_path)
        elif other:
            test_bids_sess_load(db, subid, '01', subject_dir, source_path)
        else:
            for sess_dir, num in sessions:
                test_bids_sess_load(db, subid, num, sess_dir, source_path)

    # Finish by removing invalid stuff that no longer exists.
    # Should probably just feed in SourceDir as arg instead of in pieces.
    clear_old_invalid_items(sourcedir_id)


def strip_suffixes(path: Path) -> str:
    """Get the basename for a file with all suffixes stripped off.
    """
    return path.name.removesuffix(''.join(path.suffixes))


def clear_old_invalid_items(source_id: int):
    """Clear out old 'InvalidData' warnings if the item no longer exists.
    """
    source_dir = SourceDir.query.filter_by(id=source_id).all()[0]
    for child in source_dir.invalid_children:
        if not child.path.exists():
            # Need error handling here
            child.delete()


def test_bids_sess_load(
        db: SQLAlchemy,
        subid: str,
        num: str,
        sess_dir: Path,
        source_path: Path,
        sourcedir_id: int = 1,
        project_id: str = 'PREDICTS',
        site_id: str = 'CMH',
):
    """Load/refresh a single bids session.
    """
    timepoint, _ = get_or_create(
        db.session,
        Timepoint,
        project_id=project_id,
        site_id=site_id,
        subject_id=subid,
        num=num,
    )

    # Func should probably just take source_dir record
    new_subdir, _ = get_or_create(
        db.session,
        TimepointDir,
        timepoint_id=timepoint.id,
        sourcedir_id=sourcedir_id,
        dirname=sess_dir.relative_to(source_path),
    )

    # Validate modality here if possible +/- save it somewhere if need
    for nifti in sess_dir.rglob('*.nii*'):
        # Update the BC to handle file names and validate sub/sess/etc.?
        # fname = bc.regexes['file'].match(nifti.name)

        # Get sidecar
        # Need error correction:
        #   No such file / unreadable file / invalid json
        json_path = nifti.parent / (strip_suffixes(nifti) + '.json')
        sidecar = json.loads(json_path.read_text())

        ##### Handle bvec / bval here if they exist
        ##### general func to take ext and get from nifti

        # Needed info from sidecar
        # Need error handling (fail if fields are missing?)
        series_num = sidecar['SeriesNumber']
        description = sidecar['SeriesDescription']
        # No fail, if missing
        repeat_num = sidecar.get('Repeat', '01')

        attempt, _ = get_or_create(
            db.session,
            Attempt,
            timepoint_id=timepoint.id,
            num=repeat_num,
        )

        series, _ = get_or_create(
            db.session,
            Series,
            attempt_id=attempt.id,
            num=series_num,
            other_fields={
                'description': description,
            },
        )

        get_or_create(
            db.session,
            File,
            subdir_id=new_subdir.id,
            rel_path=nifti.relative_to(sess_dir),
            other_fields={
                'series_id': series.id,
                'file_type': 'nifti',
            },
        )
        get_or_create(
            db.session,
            File,
            subdir_id=new_subdir.id,
            rel_path=json_path.relative_to(sess_dir),
            other_fields={
                'series_id': series.id,
                'file_type': 'json',
            },
        )


def test_dm_load(
        db: SQLAlchemy,
        source_path: Path,
        dc: DatmanConvention,
        project_id: str = 'ANDT',
        sourcedir_id: int = 2,
        site_id: str = 'CMH',
        study_code: str | None = None,
        site_code: str | None = None,
):
    """Load in a directory of datman raw data.

    Problems:
        - Code validation and tag validation not in use.
        - If the code validation is turned on / off once fully implemented
            there may end up being duplicate records / invalid state. A
            timepoint dir or item might land in both InvalidData and
            File/SourceDir/TimepointDir at the same time.
    """
    # Update input args

    for subject_dir in source_path.iterdir():
        if not subject_dir.is_dir():
            continue

        # This will do the validation itself if I want it to...
        # But maybe I need an exception if validation is enabled but failed..
        parsed_id = dc.parse_id(subject_dir.name)

        if not parsed_id:
            get_or_create(
                db.session,
                InvalidData,
                sourcedir_id=sourcedir_id,
                rel_path=subject_dir.name,
                other_fields={
                    'error_msg': 'Invalid Datman subject ID.',
                },
            )
            continue

        # This is where code validation happens. Maybe need a 'reason' col
        # so the rejection reason can be reported here and above.
        study = parsed_id.group('study') if 'study' in parsed_id.groupdict() else ''
        site = parsed_id.group('site') if 'site' in parsed_id.groupdict() else ''
        subid = parsed_id.group('id') if 'id' in parsed_id.groupdict() else parsed_id.group('subid')
        # This should probably error out if no timepoint on ID (it's invalid, but would've failed
        # by now anyway?)
        timepoint = parsed_id.group('timepoint') if 'timepoint' in parsed_id.groupdict() else '01'

        if (study_code and study) and (study != study_code):
            # Failed study code validation. Report it.
            get_or_create(
                db.session,
                InvalidData,
                sourcedir_id=sourcedir_id,
                rel_path=subject_dir.name,
                other_fields={
                    'error_msg': (
                        f'Datman ID contains invalid study code {study}.'
                    ),
                },
            )
            continue

        if (site_code and site) and (site != site_code):
            # Failed site code validation. Report it.
            get_or_create(
                db.session,
                InvalidData,
                sourcedir_id=sourcedir_id,
                rel_path=subject_dir.name,
                other_fields={
                    'error_msg': (
                        f'Datman ID contains invalid site code {site}.'
                    ),
                },
            )
            continue

        if not subid:
            # No readable subid. Report it.
            get_or_create(
                db.session,
                InvalidData,
                sourcedir_id=sourcedir_id,
                rel_path=subject_dir.name,
                other_fields={
                    'error_msg': (
                        f'Datman ID contains unreadable subid field.'
                    ),
                },
            )
            continue

        # Get session num and phantom info first.
        # Sigh. Need to account for PHA data... (match PHA string
        # in bids (?) ID +/- read it from the source dir table if they're
        # kept separate...)

        # How to report an empty timepoint dir? Ignoring seems bad.
        test_dm_sess_load(db, subid, timepoint, subject_dir, source_path)
        clear_old_invalid_items(sourcedir_id)


def test_dm_sess_load(
    db: SQLAlchemy,
    subid: str,
    num: str,
    sess_dir: Path,
    source_path: Path,
    sourcedir_id: int = 2,
    project_id: str = 'ANDT',
    site_id: str = 'CMH',
):
    """Load / refresh a single datman session.

    Issues:
        - This tries to read the 'attempt' from the json which only works from
            our post 'use-dcm2bids' jsons. Older datasets only have in file
            name.
        - This doesn't make use of our file name validation and tag validation
    """
    timepoint, _ = get_or_create(
        db.session,
        Timepoint,
        project_id=project_id,
        site_id=site_id,
        subject_id=subid,
        num=num,
    )

    # Func should probably just take source_dir record
    new_subdir, _ = get_or_create(
        db.session,
        TimepointDir,
        timepoint_id=timepoint.id,
        sourcedir_id=sourcedir_id,
        dirname=sess_dir.relative_to(source_path),
    )

    # Possibly optionally validate tags here later
    for nifti in sess_dir.rglob('*.nii*'):
        # update dc to parse file names here?

        # Get sidecar
        # Need error correction:
        #   No such file / unreadable file / invalid json
        json_path = nifti.parent / (strip_suffixes(nifti) + '.json')
        sidecar = json.loads(json_path.read_text())

        ##### Handle bvec / bval here if they exist
        ##### general func to take ext and get from nifti

        # Needed info from sidecar
        # Need error handling (fail if fields are missing?)
        series_num = sidecar['SeriesNumber']
        description = sidecar['SeriesDescription']
        # No fail, if missing
        repeat_num = sidecar.get('Repeat', '01')

        attempt, _ = get_or_create(
            db.session,
            Attempt,
            timepoint_id=timepoint.id,
            num=repeat_num,
        )

        series, _ = get_or_create(
            db.session,
            Series,
            attempt_id=attempt.id,
            num=series_num,
            other_fields={
                'description': description,
            },
        )

        get_or_create(
            db.session,
            File,
            subdir_id=new_subdir.id,
            rel_path=nifti.relative_to(sess_dir),
            other_fields={
                'series_id': series.id,
                'file_type': 'nifti',
            },
        )
        get_or_create(
            db.session,
            File,
            subdir_id=new_subdir.id,
            rel_path=json_path.relative_to(sess_dir),
            other_fields={
                'series_id': series.id,
                'file_type': 'json',
            },
        )


# Dataset
#   - id
#   - Project that owns it
#   - collection of source dirs
#   - 'use':
#       - raw
#           - Reads sidecars
#           - Gets full path to niftis for viewing in papaya
#       - QC
#           - Images / csvs / etc.
#           - Images can optionally be grouped together
#           - Each image / image group / metric file attached to a real series
#           - Metric files optionally get read in
#           - Optional titles per image / group
#           - Optional display ordering
#           - Optional sign off header.
#       - Tech notes
#           - Just display the file per timepoint
#   - Name convention
#      - Dictates how to reconstruct the ID / display the ID

# Rough specs
datman_raw_source = {
    'paths': {
        'timepoint': '{root_path}/({subject}_{timepoint}|{phantom})',
        'contents': '{file_regexes}',
    },
    'file_regexes': {
        '{fname}.nii*': 'raw_scan',
        '{fname}.json': 'sidecar',
        '{fname}.bvec': 'bvec',
        '{fname}.bval': 'bval',
    },
    'validates': {
        # Keys with empty list if only validating study
        # '*' with list of site codes if only validating site
        # otherwise key: [site1, site2] etc. per valid study code.
        'study': {},
        # Keys with empty list if only ensuring tag is recognizable
        # Tag with series descr regex if matching tag to specific series
        'tags': {},
    }
}

bids_raw_source = {
    'paths': {
        'timepoint': '{root_path}/({subject}|{phantom})',
        'contents': '[{timepoint}/]{modality}/{file_regexes}',
    },
    'file_regexes': {
        '{fname}.nii*': 'raw_scan',
        '{fname}.json': 'sidecar',
        '{fname}.bvec': 'bvec',
        '{fname}.bval': 'bval',
    },
    'validates': {
        # Same as above
        'study': {},
        # More complicated than tag matching...right?
        'modality': {},
    }
}

bids_paths = {
    'timepoint_dir': [
        '({subject}|{phantom})',
        '[{timepoint}]',
    ],
    'files': [
        '{modality}',
        '{file_regexes}'
    ],
}

dm_paths = {
    'timepoint_dir': [
        '({timepoint}|{phantom})',
    ],
    'files': [
        '{file_regexes}',
    ],
}

file_regexes = {
    '*.nii*': 'raw_scan',
    '*.json': 'sidecar',
    '*.bvec': 'bvec',
    '*.bval': 'bval',
}
validates = {}


class TestDatman(NameConvention):
    """Testing new directory parsing.
    """
    templates: dict = {
        # 'subject': '{project}_{site}_{subid}',
        'timepoint': '{project}_{site}_{subid}_{tnum}',
        'phantom': '{study}_{site}_PHA_{subid}',
        'fname': '{timepoint|phantom}_{attempt}_{tag}_{snum}_{description}'
    }

    default_patterns: dict = {
        'project': r'[^_]+',
        'site': r'[^_]+',
        'subid': r'(?!PHA)([^_]+)',
        'tnum': r'[^_]+',
        'attempt': r'[^_]+',
    }


class TestBids(NameConvention):
    """Testing new directory parsing.
    """
    templates: dict = {
        'subject': 'sub-{subid}',
        # This might be the wrong approach, maybe subid pattern should change
        'phantom': 'sub-PHA{subid}',
        'timepoint': 'ses-{tp_num}',
        'modality': '{mod}',
        'fname': 'sub-{subid}_ses-{tp_num}_{entities}{suffix}',
    }

    default_patterns: dict = {
        'subid': r'(?P<site>[A-Z]{3})(?P<id>[A-Z0-9]+)',
        'tp_num': r'[0-9]{2}',
        'mod': f'[a-z]+',
        'entities': r'(?:[A-Za-z0-9]+-[A-Za-z0-9]+_)*',
        'suffix': r'[A-Za-z0-9]+',
    }


def make_path_regex(path_templates, name_convention):
    """Take a path template and make it into a path regex
    """
    result = []
    for dir_template in path_templates:
        subdir = dir_template.format_map(name_convention.regexes)
        result.append(subdir)
    return result


def get_timepoint_dirs(source_dir, path_regex, name_convention):
    """Take a source dir, get the timepoint paths + info.
    """


    return

# datman_regexes = {
#     'subject_id': (
#         "(?P<full_id>(?P<med_id>(?P<short_id>(?P<study>[^_]+)_"
#         "(?P<site>[^_]+)_"
#         "(?P<subject>[^_]+))(?<!PHA)_"
#         "(?P<timepoint>[^_]+))_"
#         "(?!MR)(?!SE)(?P<session>[^_]+))"
#     ),
#     'phantom_id': (
#         "(?P<id>(?P<study>[^_]+)_"
#         "(?P<site>[^_]+)_"
#         "(?P<subject>PHA_(?P<type>[A-Z]{3})(?P<num>[0-9]{4,6}))"
#         "(?P<timepoint>)(?P<session>))"
#     )
# }


# Raw data:
#   - Main directory needs at a minimum
#       - Phantom support!
#       - For invalid data:
#           - source dir ID
#           - rel_path (of the invalid dir within source)
#           - error message explaining issue
#       - For valid timepoint dirs:
#           -> project ID and site ID have to come from regexes OR source conf
#           - subid
#           - timepoint num
#           - timepoint dir obj (which takes timepoint.id, source dir ID, rel dir within source path)
#               - timepoint.id
#               - source dir ID
#               - rel path within source_path

#  - For each timepoint/session dir in main directory:
#       - For invalid data:
#           - source dir ID
#           - rel_path
#           - timepoint.id
#           - error message
#       - For valid data
#           - Pair of nifti + json (fail if either missing)
#           - series num
#           - series description
#           - repeat / attempt or '01'
#           - rel_path to the file relative to timepoint dir
#           - file type (or extension? or both?)


# Take path templates
#   populate them with regexes that have been constructed from name convention
#   templates
#   then re compile
#   so re.compile delayed until needed (? maybe retain the strings for reuse
#   need to compile early to catch issues)

def _load_patterns(templates, patterns):
    loaded = {}
    for template_type, template in templates.items():
        for name, item in patterns.items():
            token = '{' + name + '}'
            if token in template:
                template = template.replace(token, f'(?P<{name}>{item})')

        try:
            re.compile(template)
        except re.error as e:
            print(f'unreable template rendered: {template}')
            continue
        loaded[template_type] = template
    return loaded


def _make_path_regexes(templates, name_patterns):
    if not isinstance(templates, list):
        templates = [templates]

    path_regexes = []
    for dir_template in templates:
        continue


# The language
# patterns are traditional regexes
# templates are compositions of patterns/regexes
#   - Are applied to 'items': a single dir level or file
#   - Can be lists

# Naming convention determines how the files are organized...
# but individual datasets can have different organization so separate the
# 'locating the data' part, so its in the naming convention part
# and separate the 'what data to pull' part because it's specific to the
# dataset.

dm_patterns = {
    'project': r'(?P<project>[^_]+)',
    'site': r'(?P<site>[^_]+)',
    'subid': r'(?!PHA)(?P<timepoint>[^_]+)',
    'pha_subid': r'(?P<timepoint>(?P<pha_type>[A-Z]{3})(?P<id>[0-9]{4,8}))',
    'tp_num': r'(?P<tp_num>[^_]+)',
    'attempt': r'(?!MR)(?!SE)(?P<attempt>[^_]+)',
    'tag': r'(?P<tag>[^_]+)',
    'series': r'(?P<series>[^_]+)',
    'description': r'(?P<description>[^_]+)',
}

dm_templates = {
    'short_id': '{project}_{site}_{subid}',
    'med_id': '{project}_{site}_{subid}_{tp_num}',
    'long_id': '{project}_{site}_{subid}_{tp_num}_{attempt}',
    'phantom': '{project}_{site}(?P<pha>_PHA_){pha_subid}',
}

dm_path_templates = {
    'timepoint_dir': [
        ['^{med_id}$', '^{phantom}$'],
    ],
    'fname': '{long_id}_{tag}_{series}_{description}',
    'phantom_fname': '{phantom}_{tag}_{series}_{description}',
}

bids_patterns = {
    'subid': r'(?P<site>[A-Z]{3})(?P<id>[A-Z0-9]+)',
    'pha_subid': r'(?P<site>(?!PHA)[A-Z]{3})(?P<pha>PHA)(?P<id>[A-Z0-9]+)',
    'tp_num': r'(?P<tp_num>[0-9]{2})',
    'data_type': r'(?P<data_type>[a-z]*)',
    'entities': r'(?:[A-Za-z0-9]+-[A-Za-z0-9]+_)*',
    'suffix': r'(?P<suffix>[A-Za-z0-9]+)',
}

bids_templates = {
    'subject': 'sub-{subid}',
    'session': 'ses-{tp_num}',
    'phantom': 'sub-{pha_subid}',
    'fname': 'sub-{subid}_ses-{tp_num}_{entities}{suffix}',
    'phantom_fname': 'sub-{pha_subid}_ses-{tp_num}_{entities}{suffix}',
}

# data type sets tp_num = '' to catch instances where the sub- contents
# mix a real session and modality dirs
# Path templates entries per dir:
#   (might be a good idea to mark certain templates path, id, file? rather
#    than separate columns)
#   uniform_children (all must match one but not others and no mix)
#       - Plain bool means fail all if mixed
#       - mixed_pass: index, means pass all that match that regex when mixed.
#               fail others.
#   regexes (list of one or more)
#
# For files that come in sets
#   - Optional 'fields' in the the fname that must match to restrict
#   - regexes: a list of 1+ path template to match (how to label them in db though?)
#   - required: all (find whole set or error), False (find or don't, who cares),
#               partial (find at least one... how to mark?)
bids_path_templates = {
    'timepoint_dir': [
        '^{subject}$',
        ['^{session}$', '^{data_type}$'],
    ]
}

better_bids_path_templates = {
    'timepoint_dir': [
        {
            'patterns': ['^{subject}$'],
            'child_settings': {
                'require_uniform': True,
                # The pattern that passes when not uniform.
                'pass_pattern': 0,
            }
        },
        {
            'patterns': ['^{session}$', '^{data_type}$'],
        }
    ]
}


test_templates = {
    'timepoint_dir': {
        'type': 'dir',
        'patterns': [
            {
                'type': 'dir',
                'patterns': [
                    '^{subject}$',
                ],
                'child_settings': {
                    'require_uniform': True,
                    # pass_pattern only allowed if 'require_unform' = True,
                    # optional. If not given all fail if not matching same.
                    'pass_pattern': 0,
                },
            },
            {
                'type': 'dir',
                'patterns': [
                    '^{session}$',
                    '^{data_type}$',
                ],
            }
        ],
    },
}


# Most plain, but valid. Assumed to be a dir unless told otherwise
test1 = {
    'timepoint_dir': '^{subject}$',
}

# Alts, but still valid and no other metadata. Also assumed to be dirs.
test2 = {
    'timepoint_dir': [
        '^{session}$',
        '^{data_type}$',
    ],
}

# Non-dir but simple
test3 = {
    'timepoint_dir': {
        'type': 'file',
        'patterns': r'[a-zA-Z]*.nii.gz',
    }
}

# Parent level is fully expressed, patterns are not regular.
test4 = {
    'timepoint_dir': {
        'type': 'dir',
        'patterns': [
            '^{session}$',
            '^{data_type}$',
        ],
    }
}

# Fully expressed at every level. Just must fill and compile.
# For a single directory level, patterns can be joined together or
# separated into other entries if they have their own config? No, just
# keep it regular. Sigh.
valid_bids_paths = {
    'timepoint_dir': {
        'type': 'dir',
        # Each directory level should be a list even if of one item. Sigh.
        'path': [
            [
                {
                    'type': 'dir',
                    'pattern': '^{subject}$',
                    'child_settings': {
                        'require_uniform': True,
                        # pass_pattern only allowed if 'require_unform' = True,
                        # optional. If not given all fail if not matching same.
                        'pass_pattern': 0,
                    },
                }
            ],
            [
                {
                    'type': 'dir',
                    'pattern': '^{session}$',
                },
                {
                    'type': 'dir',
                    'pattern': '^{data_type}$',
                    'use_parent': True,
                }
            ],
        ]
    },
    'raw_data': {
        'type': 'file',
        'path': [
            [
                {
                    'type': 'dir',
                    'pattern': '^{data_type}$',
                }
            ]
        ],
        # Add option to report dirs or non-matching files as errors.
        'items': [
            {
                # Add require_uniform? to account for multiple regexes?

                # This is mandatory. For plain files nothing else needed?
                # e.g. a qc metric.
                'patterns': [
                    '^(?P<fname>{fname}).(?P<ext>.*)',
                    '^(?P<fname>{phantom_fname}).(?P<ext>.*)',
                ],
                # This is optional, if the files that match the above must
                # be 'grouped', e.g. the pieces of a series.
                # How to format output though? Has to be consistent.
                'group_by': ['fname'],
                'group_items': [
                    {
                        # Keys from the above regex to match to identify
                        'match': {
                            'ext': 'nii.gz',
                        },
                        # A group missing this is wrong
                        'required': True,
                        # How to tag it in the DB
                        'role': 'raw_scan',
                    },
                    {
                        'match': {
                            'ext': 'json',
                        },
                        'required': True,
                        'role': 'sidecar',
                        'format': 'json',
                        'read_vals': [
                            {
                                'key': 'SeriesNumber',
                                'store': 'series',
                                'require': True,
                            },
                            {
                                'key': 'SeriesDescription',
                                'store': 'description',
                                'require': True,
                            },
                            {
                                'key': 'Repeat',
                                'store': 'attempt',
                                'default': '01',
                            },
                        ]
                    },
                    {
                        'match': {
                            'ext': 'bvec',
                        },
                        'required': False,
                        'role': 'bvec',
                    },
                    {
                        'match': {
                            'ext': 'bval',
                        },
                        'required': False,
                        'role': 'bval',
                    }
                ]
            }
        ]
    },
}

valid_datman_paths = {
    'timepoint_dir': {
        'type': 'dir',
        'patterns': [
            [
                {
                    'type': 'dir',
                    'pattern': '^{med_id}$',
                },
                {
                    'type': 'dir',
                    'pattern': '^{phantom}$',
                }
            ]
        ]
    },
    # This is bids specific right now.
    'raw_data': {
        'type': 'file',
        # Change patterns at this level to 'paths'
        # maybe drop the type and change 'items' to files. So the diff
        # between a dir and a file is dir always has 'paths' and files always
        # has 'files' and you take items accordingly. (What about dirs that
        # may source info from files? Sigh. Use type if present to override assumption)
        'patterns': [
            {
                'type': 'dir',
                'pattern': '^{data_type}$',
            }
        ],
        'items': {
            'nifti': {
                'patterns': [
                    '^{fname}.nii*',
                    '^{phantom_fname}.nii*',
                ],
                # Don't mix phantom and non-phantom data for datman.
                'require_uniform': True,
                # Expect a json for every nifti.
                'require': ['sidecar'],
            },
            'sidecar': {
                'patterns': [
                    '^{fname}.json',
                    '^{phantom_fname}.json',
                ],
                'require_uniform': True,
                'require': ['nifti'],
            },
            'bvec': {
                'patterns': [
                    '^{fname}.bvec',
                    '^{phantom_fname}.bvec',
                ],
                'require_uniform': True,
            },
            'bval': {
                'patterns': [
                    '^{fname}.bval',
                    '^{phantom_fname}.bval',
                ],
                'require_uniform': True,
            },
        },
        # Contrast this with a 'read_file' option which loads in the
        # whole file and populates the File table as told.
        'read_from_file': [
            {
                'from': 'sidecar',
                'format': 'json',
                'items': [
                    # Make require optional.. if no default is true unless told
                    # otherwise
                    {
                        'fills_template': 'series',
                        'key': 'SeriesNumber',
                        'require': True,
                    },
                    {
                        'fills_template': 'description',
                        'key': 'SeriesDescription',
                        'require': True,
                    },
                    {
                        'fills_template': 'attempt',
                        'key': 'Repeat',
                        'Default': '01',
                    },
                ]
            }
        ]
    },
}

atoms = {
    'subid': r'(?P<subid>(?P<site>[A-Z]{3})(?P<id>[A-Z0-9]+))',
    'tp_num': r'(?P<tp_num>[0-9]{2})',
    'data_type': r'(?P<data_type>[a-z]*)',
    'bad_regex': r'(?P<field>[a-z]*',
}
complex_components = {
    'subject': 'sub-{subid}',
    'session': 'ses-{tp_num}',
    'should_fail': 'sub-{other}{subid}',
}


old_raw_conf = {
    # This is bids specific right now.
    'raw_data': {
        'type': 'file',
        # Change patterns at this level to 'paths'
        # maybe drop the type and change 'items' to files. So the diff
        # between a dir and a file is dir always has 'paths' and files always
        # has 'files' and you take items accordingly. (What about dirs that
        # may source info from files? Sigh. Use type if present to override assumption)
        'path': [
            [
                {
                    'type': 'dir',
                    'pattern': '^{data_type}$',
                }
            ]
        ],
        'items': {
            'nifti': {
                'patterns': [
                    '^{fname}.nii*',
                    '^{phantom_fname}.nii*',
                ],
                # Don't mix phantom and non-phantom data for datman.
                'require_uniform': True,
                # Expect a json for every nifti.
                'require': ['sidecar'],
            },
            'sidecar': {
                'patterns': [
                    '^{fname}.json',
                    '^{phantom_fname}.json',
                ],
                'require_uniform': True,
                'require': ['nifti'],
            },
            'bvec': {
                'patterns': [
                    '^{fname}.bvec',
                    '^{phantom_fname}.bvec',
                ],
                'require_uniform': True,
            },
            'bval': {
                'patterns': [
                    '^{fname}.bval',
                    '^{phantom_fname}.bval',
                ],
                'require_uniform': True,
            },
        },
        # Contrast this with a 'read_file' option which loads in the
        # whole file and populates the File table as told.
        'read_from_file': [
            {
                'from': 'sidecar',
                'format': 'json',
                'items': [
                    # Make require optional.. if no default is true unless told
                    # otherwise
                    {
                        'fills_template': 'series',
                        'key': 'SeriesNumber',
                        'require': True,
                    },
                    {
                        'fills_template': 'description',
                        'key': 'SeriesDescription',
                        'require': True,
                    },
                    {
                        'fills_template': 'attempt',
                        'key': 'Repeat',
                        'Default': '01',
                    },
                ]
            }
        ]
    },
}

alt_bids_conf = {
    'path': [
        [
            {
                'type': 'dir',
                'pattern': '^{data_type}$',
            }
        ]
    ],
    'items': [
        {
            'role': 'raw_scan',
            'patterns': [
                '^(?P<fname>{fname}).nii*',
                '^(?P<fname>{phantom_fname}).nii*',
            ],
        },
        {
            'role': 'sidecar',
            'patterns': [
                '^(?P<fname>{fname}).json$',
                '^(?P<fname>{phantom_fname}).json$',
            ],
        },
        {
            'role': 'bvec',
            'patterns': [
                '^(?P<fname>{fname}).bvec$',
                '^(?P<fname>{phantom_fname}).bvec$',
            ],
        },
        {
            'role': 'bval',
            'patterns': [
                '^(?P<fname>{fname}).bval$',
                '^(?P<fname>{phantom_fname}).bval$',
            ],
        },
    ],
    'groups': [
        {
            'group_by': [
                'fname',
            ],
            'expected_members': [
                {
                    'role': 'raw_scan',
                    'num': 1,
                    'required': True,
                },
                {
                    'role': 'sidecar',
                    'num': 1,
                    'required': True,
                },
                {
                    'role': 'bval',
                    'num': 1,
                    'required': False,
                },
                {
                    'role': 'bval',
                    'num': 1,
                    'required': False,
                }
            ],
            'shared_vals': {
                'read_from': 'sidecar',
                'format': 'json',
                'values': [
                    {
                        'key': 'SeriesNumber',
                        'store': 'series',
                        'required': True,
                    },
                    {
                        'key': 'SeriesDescription',
                        'store': 'description',
                        'required': True,
                    },
                    {
                        'key': 'Repeat',
                        'store': 'attempt',
                        'default': '01',
                        'required': False,
                    }
                ]
            }
        }
    ],
}

# Ok so components are raw regex pieces key:vals
# and also ID format fields key:vals

def assemble_atoms(simple, complex_components):
    """Take elementary components, fill them if needed, validate they compile.
    """
    validated_atoms = {}
    failures = {}
    for key, value in simple.items():
        try:
            # Make sure it compiles for now, but keep plain string.
            re.compile(value)
        except re.error as e:
            failures[key] = f'Component is an invalid regex - {str(e)}'
        else:
            validated_atoms[key] = value

    validated_complex = {}
    for key, value in complex_components.items():
        try:
            filled = value.format_map(validated_atoms)
        except KeyError as e:
            failures[key] = (
                f'Referenced non-existent component {str(e)}. '
                'The required component may have failed validation or may be '
                'undefined.'
            )
            continue

        try:
            re.compile(filled)
        except re.error as e:
            failures[key] = f'Component is an invalid regex - {str(e)}'
        else:
            validated_complex[key] = filled

    result = {**validated_atoms, **validated_complex}
    return result, failures


def compile_path_regexes(valid_conf, components):
    for key, path_settings in valid_conf.items():
        for dir_level in path_settings['patterns']:
            # Honestly each level should be allowed to be a singular string...
            # But maybe not worth it. Just let users provide it that way and
            # normalize it.

            for alternate in dir_level:
                # Might want to change the regex name at this level since
                # should only be one per 'alternate'. Singular.
                path_template = alternate['pattern']


                # The fact that this is valid should have been checked when it
                # got added to the database. Recheck any time the name convention
                # or data type templates / atoms are modified.
                path_template = path_template.format_map(components)

                # Ditto this. Everything should be _known_ to compile before
                # it ever gets used by the app.
                result = re.compile(path_template)
                alternate['pattern'] = result

    return valid_conf


def compile_regexes(valid_conf, components):
    """Slot components into patterns and compile within complex configuration
    """
    errors = {}
    # Used for dir and file entries. Populate the patterns.
    for key, settings in valid_conf.items():
        block_errors = []
        # Might want to require every entry to define 'path' even if empty list
        if 'path' in settings:
            for dir_level in settings['path']:
                for alt_pattern in dir_level:
                    # Is it worth checking this here? or have each key
                    # searched for and reported at database entry?
                    path_template = alt_pattern['pattern']
                    try:
                        path_template = path_template.format_map(components)
                    except KeyError as e:
                        block_errors.append(
                            'Path pattern references unknown config '
                            f'component {str(e)}'
                        )
                        continue
                    try:
                        result = re.compile(path_template)
                    except re.error as e:
                        block_errors.append(
                            f'Invalid regex {path_template} - {str(e)}'
                        )
                        continue
                    alt_pattern['pattern'] = result

        if 'items' in settings:
            for ftype, fsettings in settings['items'].items():
                # Should be plural or singular for both 'types' of config...
                filled_patterns = []
                for item in fsettings['patterns']:
                    try:
                        filled = item.format_map(components)
                    except KeyError as e:
                        block_errors.append(
                            f'{ftype} pattern references unknown config '
                            f'component {str(e)}'
                        )
                        continue
                    try:
                        result = re.compile(filled)
                    except re.error as e:
                        block_errors.append(
                            f'{ftype} invalid regex {filled} - {str(e)}'
                        )
                        continue
                    filled_patterns.append(result)
                fsettings['patterns'] = filled_patterns

        errors[key] = block_errors

    return valid_conf, errors


# def make_template_entry(entry, components, etype='dir'):
#     child_settings = child_settings or {}

#     if isinstance(entry, str):
#         entry = {
#             'type': etype,
#             'patterns': [entry]
#         }

#     if isinstance(entry, list):
#         entry = {
#             'type': etype,
#             'patterns': entry,
#         }

#     for item in entry:
#         # Need some error handling here?
#         # Make sure adequate reporting when template references nonexistent
#         # component or full thing can't compile.
#         entry['patterns'].append(re.compile(item.format_map(components)))
#     return entry


# def handle_template(template, patterns):
#     """Merge a single entry in a set of templates.

#     Template may be:
#         - A string that may contain python regular expressions or placeholders
#             for pre-existing regex 'patterns' to be inserted into.
#         - A list that represents a series of directories to traverse. One
#             entry per directory expected to be travelled. Each entry may be:
#             - A string containing python regular expressions, plain characters
#                 or placeholders for pre-existing regex 'patterns' to be
#                 inserted into.
#             - A nested list, which contains alternate templates to match
#                 a directory against, when multiple patterns may be accepted.
#     """
#     if isinstance(template, str):
#         return template.format_map(patterns)

#     directory_templates = []
#     for dir_level in template:
#         if isinstance(dir_level, str):
#             directory_templates.append(dir_level.format_map(patterns))
#             continue

#         alternates = []
#         for alt in dir_level:
#             alternates.append(alt.format_map(patterns))

#         directory_templates.append(alternates)

#     return directory_templates


# def fill_templates(templates, patterns):
#     """This will expose if any template reference a pattern that doesn't exist.
#     """
#     filled = {}
#     for key, template in templates.items():
#         filled[key] = handle_template(template, patterns)
#     return filled


# def testing_templates(reg_templates, path_templates, patterns):
#     filled_reg = fill_templates(reg_templates, patterns)
#     new_patterns = {**filled_reg, **patterns}
#     filled_paths = fill_templates(path_templates, new_patterns)
#     return filled_reg, filled_paths


# def compile_regexes(templates):
#     """Compile the final templates into something usable.

#     This will expose if any template is an invalid RE. Could maybe wrap
#     this into the handle_templates function so final regexes get compiled
#     but intermediate do not.
#     """
#     regexes = {}
#     for key, template in templates.items():
#         if isinstance(template, str):
#             regexes[key] = re.compile(template)
#             continue
#         dir_regexes = []
#         for dir_level in template:
#             if isinstance(dir_level, str):
#                 dir_regexes.append(re.compile(dir_level))
#                 continue
#             alts = []
#             for alternate in dir_level:
#                 alts.append(re.compile(alternate))
#             dir_regexes.append(alts)
#         regexes[key] = dir_regexes
#     return regexes


# def is_valid_dirname(dirname, dir_regexes):
#     """Take a single directory name, and an re.Pattern or list of alt re.Pattern
#     and return True if this current directory matches.
#     """
#     if isinstance(dir_regexes, re.Pattern):
#         return bool(dir_regexes.match(dirname))

#     for alternate in dir_regexes:
#         if alternate.match(dirname):
#             return True

#     return False


# def collect_timepoints(source_dir, dir_regexes, level=0, parsed=None, children=None):
#     """Recursively collect correctly named timepoint paths.
#     """
#     parsed = parsed or {}
#     matches = []
#     failed = []
#     # Used to restrict a search area if some children pass
#     children = children or source_dir.iterdir()

#     regexes = dir_regexes[level]
#     # Can remove this check if you normalize every dir level into a list
#     # at the database level.
#     if isinstance(regexes, re.Pattern):
#         regexes = [regexes]

#     for item in children:
#         if not item.is_dir():
#             continue

#         # Match gets re match result but now also need 'entry'
#         # you get it incidentally because of the break but that's
#         # kind of hacky.
#         match = None
#         attempt_errors = []
#         for entry in regexes:
#             m = entry['pattern'].match(item.name)
#             if m:
#                 match = m
#                 break
#             attempt_errors.append(entry)

#         if match is None:
#             failure = FailedMatch(
#                 item,
#                 f'Failed to match regexes during traversal. {str(attempt_errors)}'
#             )
#             failed.append(failure)
#             continue

#         new_groups = match.groupdict()
#         conflict = None
#         for field, value in new_groups.items():
#             if field in parsed and parsed[field] != value:
#                 conflict = (field, parsed[field], value)
#                 break

#         if conflict:
#             field, old_value, new_value = conflict
#             reason = (
#                 f'{item.name} matched regex {str(match)} but field {field} '
#                 f'mismatches a previously found value: old - {old_value} ',
#                 f'new: {new_value}.'
#             )
#             failed.append(
#                 FailedMatch(item, reason)
#             )
#             continue

#         merged = {**parsed, **new_groups}
#         if level == (len(dir_regexes) - 1):
#             matches.append({**merged, 'path': item})
#         else:
#             subdir_matches, subdir_fails = collect_timepoints(
#                 item,
#                 dir_regexes,
#                 level + 1,
#                 merged,
#             )
#             matches.extend(subdir_matches)
#             failed.extend(subdir_fails)

#     return matches, failed


from typing import NamedTuple
class FailedMatch(NamedTuple):
    path: Path
    reason: str

# 'raw' datasets spec for templates:
#   required path_templates:
#       - 'timepoint_dir'
#           - full path to a singular timepoint of data.
#           - Required to yield: timepoint
#           - Optionally yields: project, site, tp_num
#       - 'files'
#           - A pair of raw nifti + json sidecar for each series.


def collect_paths(source_dir, path_regexes, level=0, parsed=None,
                  parent_reqs=None):
    """parent_reqs are inherited from the parent dir. Include things like
    uniform matching (and which matches to allow through, if any, if that fails)
    """
    parsed = parsed or {}
    final_matches = []

    regexes = path_regexes[level]

    matches = {}
    failures = []
    for subdir in source_dir.iterdir():
        if not subdir.is_dir():
            continue

        # Take first match only.
        # Inform user to order their regexes from most restrictive to
        # least.
        match = None
        attempt_errors = []
        for idx, entry in enumerate(regexes):
            m = entry['pattern'].match(subdir.name)
            if m:
                match = m
                matches.setdefault(idx, []).append((subdir, entry, match))
                break
            attempt_errors.append(entry)

        if match is None:
            failure = FailedMatch(
                subdir,
                f'Failed to match regexes during traversal.'
            )
            failures.append(failure)

        # Need to get parsed + verify no mismatches before you recurse

    # Massively needs a clean up.
    if parent_reqs:
        if (
            'require_uniform' in parent_reqs and parent_reqs['require_uniform']
            and len(matches) > 1
            ):

            if 'pass_pattern' in parent_reqs and parent_reqs['pass_pattern'] is not None:
                pass_idx = parent_reqs['pass_pattern']
            else:
                pass_idx = -1

            for idx in list(matches.keys()):
                if idx != pass_idx:
                    for group in matches[idx]:
                        # Update this to take a custom error message fed
                        # in by the parent dir's settings.
                        failures.append(
                            FailedMatch(
                                group[0],
                                f'All directories must match same regex, or be of type {pass_idx}'
                            )
                        )
                    del matches[idx]

    # This must be seriously cleaned up...
    for idx in list(matches.keys()):
        ## If use_parent is given, every dir at that level _must_ provide
        ## the same info. Also, require_uniform must be set by the parent
        ## Can't use one without the other. Must validate this at db add.
        if any([group[1].get('use_parent', False) for group in matches[idx]]):
            group = matches[idx][0]
            matches[idx] = [(source_dir, group[1], group[2])]


    # possibly flatten this now that the indexes aren't needed
    for idx, groups in matches.items():
        for group in groups:
            subdir, entry, match = group

            new_groups = match.groupdict()
            conflict = None
            for field, value in new_groups.items():
                if field in parsed and parsed[field] != value:
                    conflict = (field, parsed[field], value)
                    break

            if conflict:
                field, old_value, new_value = conflict
                reason = (
                    f'{subdir.name} matched regex {str(match)} but field {field} '
                    f'mismatches a previously found value: old - {old_value} ',
                    f'new: {new_value}.'
                )
                failures.append(
                    FailedMatch(subdir, reason)
                )
                continue

            merged = {**parsed, **new_groups}
            if level == (len(path_regexes) - 1):
                final_matches.append({**merged, 'path': subdir})
            else:
                child_settings = entry.get('child_settings', None)
                subdir_matches, subdir_fails = collect_paths(
                    subdir, path_regexes, level + 1, merged,
                    parent_reqs=child_settings
                )
                final_matches.extend(subdir_matches)
                failures.extend(subdir_fails)

    return final_matches, failures


def collect_files(source_dir, regexes):
    # Require:
    #   - series num
    #   - series description
    #   - file type / role (????)

    # Optional:
    #   - Repeat num / attempt num
    results = []
    failures = []

    # Check and complain if 'items' not in config?

    if 'path' in regexes:
        found, errors = collect_paths(source_dir, regexes['path'])
        failures.extend(errors)
        source_dir = found
    else:
        source_dir = [{
            'path': source_dir
        }]

    for file_conf in regexes['items']:
        collected = []
        for entry in source_dir:
            for item in entry['path'].iterdir():
                # Add option to report dirs if they shouldnt exist
                if item.is_dir():
                    continue

                match = None
                for pattern in file_conf['patterns']:
                    m = pattern.match(item.name)
                    if m:
                        match = m
                        break

                if not match:
                    # Report error here
                    continue

                parsed = match.groupdict()
                parsed['path'] = item
                collected.append(parsed)

        if 'group_by' in file_conf:
            # Raise an exception here if 'group_items' is not also defined.
            grouped = group_by_keys(collected, file_conf['group_by'])
            for key, group in grouped.items():
                parsed_group = {}
                for group_conf in file_conf['group_items']:
                    match = None
                    for item in group:
                        if is_match(group_conf['match'], item):
                            match = item
                            break
                    if not match:
                        if 'required' in group_conf and group_conf['required']:
                            # report error
                            print(f"Missing a match for {group_conf}")
                        continue

                    match['path']
                    parsed_group.setdefault(group_conf['role'], []).append(match)




    return results, failures


from collections import defaultdict
def group_by_keys(dicts, keys):
    groups = defaultdict(list)
    for d in dicts:
        group_key = tuple(d[k] for k in keys)
        groups[group_key].append(d)
    return groups


def is_match(expected, actual):
    # This should maybe be expanded later to allow regexes.. but then
    # this complicates the match dict format doesnt it.
    return all(actual[k] == expected[k] for k in expected)
