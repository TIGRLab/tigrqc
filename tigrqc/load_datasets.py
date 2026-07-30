"""Handles the reading of datasets (regardless of type or name scheme).
"""
from dataclasses import dataclass, field
import glob
import os
import re
from abc import ABC
from pathlib import Path

from tigrqc.exceptions import TigrQcException
from tigrqc.models import InvalidDataDir

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
        'session': '^ses-{timepoint}$'
        # 'file'? Needed?

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
    }


class BidsSeries:

    def __init__(self, file_path: Path):



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


def read_raw_bids(dataset_path: Path, dataset_id: int, bc: BidsConvention):
    """A test function read in a bids dataset of raw data.
    """
    # Should maybe have handling here in case the dataset path no longer
    # exists when the read is run (like moved or archived or deleted since
    # first added to DB)

    for item in dataset_path.iterdir():
        if not item.is_dir():
            continue

        # May want to handle exceptions here
        # Site and study code validation should happen here if anywhere, to
        # avoid wasting time parsing misnamed folders.
        parsed_id = bc.parse_id(item.name)

        if not parsed_id:
            bad_subdir = InvalidDataDir(
                dataset_id=dataset_id,
                subdir=item.name
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

        parsed_dir = {}
        for nifti in item.rglob('*.nii*'):
            # parent.parent will either be sub- or ses- or a mistake
            session_id = bc.regexes['session'].match(nifti.parent.parent.name)

            if session_id:
                session = session_id.group('timepoint')
            elif nifti.parent.parent == item:
                # No ses-, valid bids and means session = 1
                session = '01'
            else:
                parsed_dir.setdefault('invalid', []).append(nifti)
                continue

            parsed_dir.setdefault(session, {}).setdefault(nifti.parent.name, []).append(nifti)

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

            modality = nifti.parent.name


            if nifti.parent.parent == item:
                # Catch instances where the optional ses- dir has been omitted
                session = '01'
            else:
                # Clean this up
                sess_id = bc.regexes['session'].match(nifti.parent.parent.name)
                if not sess_id:
                    # Parent of modality isn't the sub folder and its not a
                    # recognizable ses- folder. So... I guess block qc
                    # of niftis until it's fixed. Report the directory.
                    invalid_subdirs.add(nifti.parent.parent)




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







