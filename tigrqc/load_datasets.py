"""Handles the reading of datasets (regardless of type or name scheme).
"""
import glob
import os
import re
from abc import ABC
from pathlib import Path

from tigrqc.exceptions import TigrQcException

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



class NameConvention(ABC):
    """The interface that must be implemented to make a valid name convention.
    """

    templates: dict = {}                    # Must contain a template for
                                            # each 'type' that must be parseable
                                            # e.g. subject, session, file
                                            # At a minimum should define subject
    default_patterns: dict = {}             # Default regexes to be slotted into templates

    def __init__(self, patterns: dict | None = None):
        patterns = patterns or {}
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
            print(template)
            try:
                regexes[template_type] = re.compile(template)
            except re.error as e:
                raise TigrQcException(
                    f'Invalid regex {template} constructed '
                    f'for {self.__class__.__name__} for template '
                    f'{template_type}'
                ) from e

        return regexes


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
    default_patterns: dict = {
        'study': r'[^_]+',
        'site': r'[^_]+',
        'subid': r'[^_]+',
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
        # 'file': ''

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
