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
# from tigrqc.models import InvalidDataDir
from tigrqc.models import get_or_create

# To do:
#   - Implement overrides of templates + patterns (but must constraint it to
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
    templates: dict = {
        'subject': '^{study}_{site}_{subid}_{timepoint}_{session}$',
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

from tigrqc.models import Timepoint, Attempt, Series, TimepointDir, File, InvalidData
def read_raw_bids(dataset_path: Path, dataset_id: int, study_id: str, bc: BidsConvention):
    """A test function read in a bids dataset of raw data.
    """
    # Should maybe have handling here in case the dataset path no longer
    # exists when the read is run (like moved or archived or deleted since
    # first added to DB)

    # Replace input args with a dataset / datadir (refs to args must update)
    # Figure out where / how to add site validation

    # Dataset path is a directory of bids folders in this case
    for item in dataset_path.iterdir():
        if not item.is_dir():
            continue

        # May want to handle exceptions here
        # Site and study code validation should happen here if anywhere, to
        # avoid wasting time parsing misnamed folders.
        parsed_id = bc.parse_id(item.name)

        if not parsed_id:
            # Update table or re-add to model
            # bad_subdir = InvalidDataDir(
            #     dataset_id=dataset_id,
            #     subdir=item.name
            # )

            # Need to update this to reflect a dataset is now a collection
            # of directories
            bad_subdir = InvalidData(
                sourcedir_id=dataset_id,
                rel_path=item.name,
            )
            # May want to handle exceptions here
            bad_subdir.save()
            continue

        # Try to make database records here
        #   info needed:
        #       - Study code if it exists (will have foreign key on study anyway)
        #       - Site if it exists. If ID doesn't include... and more than 1
        #           site exists in the project, you're screwed.
        #       - SUBID, will always exist
        #       - timepoint (bids sess) num, will always exist
        #       - session (repeat), if it exists will be in a sidecar. Otherwise set
        #           to 1. Have to read all sidecars and separate into
        #           sessions in case more than one exists at read time.
        #       - Time the folder was made or updated
        #       Further:
        #           - One record per nifti found
        #               -> type (from modality field) is this needed by the dash now?
        #               -> series number
        #               -> series description (needed?)
        #               -> date it was made / modified (?) on file system
        #               -> Date the scan was done according to scanner (?)
        #               -> The json contents
        #               -> Do we currently store bvec / bval? or do we just
        #                   grab it when we 'know' from tags that it exists?
        #                   is there a sensible way to hook it took the main record
        #                   without having to do this tag inference etc.?


        # Probably want to pull these fields out of the re object and
        # normalize so you can just grab parsed_id.study, etc. without the whole dance
        study = parsed_id.group('study') if 'study' in parsed_id.groupdict() else ''
        site = parsed_id.group('site') if 'site' in parsed_id.groupdict() else ''
        subid = parsed_id.group('id') if 'id' in parsed_id.groupdict() else parsed_id.group('subid')

        if study and study != study_id:
            # Failed study code validation, so report it.
            bad_subdir = InvalidData(
                sourcedir_id=dataset_id,
                rel_path=item.name,
            )
            # May want to handle exceptions here
            bad_subdir.save()
            continue

        # parsed_dir = {}
        # for nifti in item.rglob('*.nii*'):
        #     # parent.parent will either be sub- or ses- or a mistake
        #     session_id = bc.regexes['session'].match(nifti.parent.parent.name)

        #     if session_id:
        #         session = session_id.group('timepoint')
        #     elif nifti.parent.parent == item:
        #         # No ses-, valid bids and means session = 1
        #         session = '01'
        #     else:
        #         parsed_dir.setdefault('invalid', []).append(nifti)
        #         continue

        #     parsed_dir.setdefault(session, {}).setdefault(nifti.parent.name, []).append(nifti)

        invalid_subdirs = []
        for nifti in item.rglob('*.nii*'):
            # Do you really want to check if session / timepoint exists every
            # single time and add it or is there a better way here...
            if nifti.parent.parent in invalid_subdirs:
                # Skip items from already-known-to-be-wrong 'ses' dirs
                continue

            session_id = bc.regexes['session'].match(nifti.parent.parent.name)

            if session_id:
                session = session_id.groups('timepoint')
            elif nifti.parent.parent == item:
                # The optional ses- folder was omitted. So it's session 1
                session = '01'
            else:
                # valid bids is either:
                #       sub-X/ses-Y/modality/nifti
                #       OR sub-X/modality/nifti
                # At this point it's neither. So capture the bad parent folder
                # and ignore its contents until it's handled.
                invalid_subdirs.append(nifti.parent.parent)
                continue

            # Need somewhere to store this / translate to a 'type'
            # Or can it be abandoned if dash isn't generating things?
            # validation worth while?
            modality = nifti.parent.name






        # This is maybe a bad approach. Use above.
        for session in item.iterdir():

            if not session.is_dir():
                continue

            # This should probably be replaced with a method
            # Also, ses folders are optional when only one session exists...
            parsed_ses = bc.regexes['session'].match(session.name)

            if not parsed_ses:
                # In valid bids the subdirs should either be modality dirs
                # OR a ses- dir. If not ses and no files found... I guess
                # create an empty session and report it as empty.
                timepoint = '01'
            else:
                # Clean this up too.
                timepoint = parsed_ses.groups('timepoint') # e.g. '01'

            # Ugh. Need modality too... Maybe just have a database overridable
            # path parser. But then have to handle diff path separators.



# Dataset:
#   - Belongs to a project
#   - Has 1+ source dirs
#   - Has a type (raw data, qc metrics, pipeline data, etc.)
#   - Aggregate the invalid and valid dirs? Later.

# Source dir
#   - Has a path
#   - Has a name scheme (bids, nii, kcni)
#   - Has valid subject dirs
#   - Has invalid dirs

# Subject dir
#   - timepoint_id (what it represents)
#   - sourcedir_id (what dir it belongs to)
#   - dirname (The rel path for it within source dir)
#   - Has valid files
#   - Has invalid files

# File
#   - series_id (What it represents)
#   - subdir_id (what dir it belongs to)
#   - rel_path (the path for it within its dir)
#   - file_type (how it can be used)
#   - [future] contents? (i.e. for json and csv?)

# InvalidData
#   - sourcedir_id (The dir it belongs to)
#   - timepoint_id (Optional, if unset it's invalid at subdir level otherwise nested)
#   - rel_path (path to it within source)
#   - ignore (whether to stop reporting it)

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

        if len(children['session']) > 0 and len(children['other']) > 0:
            # Better option: Maybe parse the 'ses-' dirs and ignore the 'other'
            # and report the 'other' so they can be fixed/ignored
            #   -> This would still be invalid bids. But would prevent
            #       the problem where a previously added correct sess
            #       gets 'lost' because of a later added bad one?
            #       is this even an issue though?

            # Subject dir contains a mix of session and modality/other dirs
            # report the issue. Attach the error to the subject dir
            # since it affects multiple child dirs inside it.
            get_or_create(
                db.session,
                InvalidData,
                sourcedir_id=sourcedir_id,
                rel_path=subject_dir.name,
                other_fields={
                    'error_msg': (
                        'BIDS subject dir should contain only 1) session '
                        'dirs or 2) modality dirs. Unknown directories found.'
                    ),
                },
            )
            continue

        if len(children['other']) > 0:
            # Set default session/num == '01'
            # Make a timepoint for it.
            # Validate the modalities present in the list, if possible
            # then parse with a general 'bids session parser' func'
            continue

        for sess_dir, num in children['session']:
            timepoint, _ = get_or_create(
                db.session,
                Timepoint,
                project_id=project_id,
                site_id=site_id,
                subject_id=subid,
                num=num,
            )

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


def strip_suffixes(path: Path) -> str:
    """Get the basename for a file with all suffixes stripped off.
    """
    return path.name.removesuffix(''.join(path.suffixes))


