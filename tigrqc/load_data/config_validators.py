"""Validators for user provided configuration used during data import.
"""
import inspect
import re
from string import Formatter
from typing import Annotated, Any, Callable, Literal, Self

from pydantic import (BaseModel, BeforeValidator, ConfigDict, Field,
                      PrivateAttr, ValidationError, ValidationInfo,
                      create_model, field_validator, model_validator)
from pydantic_core import InitErrorDetails, PydanticCustomError

from .parsers import FILE_READERS
from .post_processors import POST_PROCESSORS

FileTypes = Literal[tuple(FILE_READERS.keys())]  # type: ignore[valid-type]
ScopeTypes = Literal['dataset', 'timepoint', 'attempt', 'series']
PostProcessorTypes = Literal[  # type: ignore[valid-type]
    tuple(POST_PROCESSORS.keys())
]


class StrictBaseModel(BaseModel):
    """Prevent unknown fields/typos and allow custom error creation.
    """
    # Catches user-typos
    model_config = ConfigDict(extra='forbid')

    @staticmethod
    def make_custom_error(
        err_type: str, err_msg: str, user_input: Any,
        ctx: dict[str, Any] | None = None,
        loc: tuple[int | str, ...] | None = None,
    ) -> InitErrorDetails:
        """Create a custom pydantic error that can be raised later.

        This makes it possible to 'accumulate' errors during validation and
        report all of them rather than stopping and raising on the first
        validation failure.

        Args:
            err_type: A machine readable, short, error name.
            err_msg: The error message to present to the user.
            user_input: The user input that caused the error.
            ctx: The extra values used to construct the error
                message. Can be slotted into the error string if it contains
                f-string slots. Optional.
            loc: The 'location' where the error occurred. Optional.
        """
        loc = loc or tuple()
        ctx = ctx or {}

        custom = PydanticCustomError(
            err_type,
            err_msg,
            ctx,
        )
        return InitErrorDetails(
            type=custom, input=user_input, loc=loc, ctx=ctx
        )


class PostProcessorConfig(StrictBaseModel):
    """Configuration for a post processor that will be run on input data.
    """
    use: PostProcessorTypes  # type: ignore[valid-type]
    scope: ScopeTypes = 'series'
    args: dict[str, Any] = Field(default_factory=dict)

    @property
    def function(self):
        """Expose the actual post-processor function.
        """
        return POST_PROCESSORS[self.use]

    @model_validator(mode='after')
    def check_kwargs(self):
        """Ensure user's given args are appropriate for the chosen function.
        """
        USER_ARG_VALIDATORS[self.use](**self.args)
        return self


def build_kwargs_validator(func: Callable) -> type[BaseModel]:
    """Construct a pydantic model for a post processor function's kwargs.

    This gets built once when the app starts, then can be used to validate
    intended function kwargs like:

        USER_ARG_VALIDATORS[func_name](**user_args)

    Args:
        func: The function to construct a validator for.

    Returns:
        A pydantic BaseModel capable of validating keyword-only arguments.
    """
    sig = inspect.signature(func)
    kwargs = {}

    for name, param in sig.parameters.items():
        if param.kind != inspect.Parameter.KEYWORD_ONLY:
            # Only allow users to provide keyword only inputs.
            # This might be changed later to 'only args with defaults' or
            # something simular once interface is more solidly defined.
            continue

        if param.annotation is inspect.Parameter.empty:
            annotation: Any = object
        else:
            annotation = param.annotation

        if param.default is inspect.Parameter.empty:
            default: Any = ...
        else:
            default = param.default

        kwargs[name] = (annotation, default)

    model_config = ConfigDict(extra='forbid')
    validator = create_model(
        f'KwargsModel_{func.__name__}',
        __config__=model_config,
        **kwargs
    )  # type: ignore[call-overload]

    return validator


# Used to check that user-provided args are valid for the function they want.
USER_ARG_VALIDATORS = {
    name: build_kwargs_validator(func)
    for name, func in POST_PROCESSORS.items()
}


class NameScheme(StrictBaseModel):
    """A user defined name scheme for datasets.
    """
    field_map: dict[str, str] = Field(default_factory=dict)
    fields: dict[str, str]
    templates: dict[str, str]
    post_processors: list[PostProcessorConfig] = Field(default_factory=list)

    _scheme: dict[str, str] = PrivateAttr()

    @staticmethod
    def create_field(fname: str, re_str: str) -> tuple[str, str | None]:
        """Wrap a regex in a group and report compile errors that may exist.

        Args:
            fname: The intended name for the field. Will be used as the name
                for the regex group.
            re_str: The regex that represents this field.

        Returns:
            A regex group string and an error message if any compile or other
            issues exist.
        """
        group = f'(?P<{fname}>{re_str})'
        error = None
        try:
            re.compile(group)
        except re.error as e:
            if 'redefinition' in e.msg:
                error = (
                    f'"{fname}" invalid regex: Duplicate fields exist - '
                    f'{str(e)}'
                )
            elif 'nothing to repeat' in e.msg:
                error = (
                    f'"{fname}" invalid regex: When using quantifiers like *, '
                    f'+, ?, you must specify the pattern to repeat - {str(e)}'
                )
            else:
                error = (
                    f'"{fname}" invalid regex: cannot compile - {str(e)}'
                )

        return group, error

    @staticmethod
    def create_template(
        tname: str, re_str: str, fields: dict[str, str]
    ) -> tuple[str | None, str | None]:
        """Fill in template and report compile errors that may exist.

        Args:
            tname: The intended name for the template. Will be used as the
                name of a regex group containing this regex.
            re_str: The regex that makes up this template. May contain
                f-string slots for other fields or templates to be inserted
                into.
            fields: A dictionary containing already defined fields (and
                already created templates) that may be used to populate
                this template.

        Returns:
            A tuple containing:
                - The final template, if it can be fully populated. Or None
                    if it references a non-existent field.
                - An error message if any issues were encountered, or None.
        """
        try:
            template = re_str.format_map(fields)
        except KeyError as e:
            # Return error message instead of raising so errors can be
            # accumulated.
            return (
                None,
                f'Template {tname} references non-existent field - {str(e)}'
            )

        return NameScheme.create_field(tname, template)

    @staticmethod
    def _is_valid_group_name(group_name: str) -> bool:
        """Check if a string can be a valid regex group name.

        Valid regex group names must be only alphanumeric or underscores
        and must not start with a number.

        Args:
            group_name: A string to check for validity as a regex group name.
        """
        valid_format = r'[A-Za-z_][A-Za-z0-9_]*'
        return bool(re.fullmatch(valid_format, group_name))

    @classmethod
    def _report_invalid_group_names(
        cls, data: dict[str, str], check_vals: bool = False
    ) -> str | None:
        """Find items that can't be converted to a valid regex group.

        Args:
            data: A user-supplied configuration dictionary mapping a meaningful
                key (that can be a valid regex group name) to a regex or
                regex template.
            check_vals: Whether to also check that the data values are usable
                as a regex group name.
        """
        invalid_names = set()
        for key, value in data.items():
            if not cls._is_valid_group_name(key):
                invalid_names.add(key)

            if check_vals and not cls._is_valid_group_name(value):
                invalid_names.add(value)

        if invalid_names:
            return (
                'Invalid entries - must be valid regex group name (i.e. '
                'alphanumeric and underscore chars only and must not start '
                'with a number): '
                f'{", ".join(invalid_names)}'
            )

        return None

    @field_validator('field_map')
    @classmethod
    def check_field_map(cls, data: dict[str, str]) -> dict[str, str]:
        """Make sure every 'field_map' key and value can be a valid group name.
        """
        invalid_names = cls._report_invalid_group_names(data, check_vals=True)

        if invalid_names:
            raise ValueError(invalid_names)

        return data

    @field_validator('fields')
    @classmethod
    def check_fields(cls, data: dict[str, str]) -> dict[str, str]:
        """Ensure field names can be a valid group name.
        """
        invalid_names = cls._report_invalid_group_names(data)

        if invalid_names:
            raise ValueError(invalid_names)

        return data

    @field_validator('templates')
    @classmethod
    def check_templates(
        cls, data: dict[str, str], info: ValidationInfo
    ) -> dict[str, str]:
        """Ensure templates have valid names and reference existing fields.
        """
        errors = []

        invalid = cls._report_invalid_group_names(data)
        if invalid:
            errors.append(
                cls.make_custom_error(
                    'invalid_template_name',
                    invalid,
                    loc=('templates',),
                    user_input=data,
                )
            )

        avail_fields = list(info.data.get('fields', {}).keys())
        for key, template in data.items():

            unknown_fields = check_references(template, avail_fields)

            if unknown_fields:
                err_msg = (
                    f'Template "{key}" contains unknown field(s): '
                    f'{", ".join(unknown_fields)}. If the template depends on '
                    'other templates, it must be defined after them.'
                )
                errors.append(
                    cls.make_custom_error(
                        'unknown_field',
                        err_msg,
                        loc=('templates',),
                        user_input=data,
                    )
                )

            # Append the template name even if malformed, to avoid error
            # cascade if other templates reference it.
            avail_fields.append(key)

        if errors:
            raise ValidationError.from_exception_data(
                title='NameScheme.templates',
                line_errors=errors,
            )

        return data

    @model_validator(mode='after')
    def construct_scheme(self) -> Self:
        """Turn fields and templates into a usable naming scheme.
        """
        scheme = {}
        errors = []
        for fname, re_str in self.fields.items():
            group_name = self.field_map.get(  # pylint: disable=no-member
                fname, fname
            )
            field, error = self.create_field(group_name, re_str)

            if error:
                errors.append(
                    self.make_custom_error(
                        'invalid_regex',
                        error,
                        loc=('fields',),
                        user_input=fname,
                    )
                )
            else:
                scheme[fname] = field

        for tname, re_str in self.templates.items():
            group_name = self.field_map.get(  # pylint: disable=no-member
                tname, tname
            )
            template, error = self.create_template(group_name, re_str, scheme)

            if error:
                errors.append(
                    self.make_custom_error(
                        'invalid_template',
                        error,
                        loc=('templates',),
                        user_input=tname,
                    )
                )
            else:
                assert template is not None
                scheme[tname] = template

        if errors:
            raise ValidationError.from_exception_data(
                title='NameScheme',
                line_errors=errors,
            )

        self._scheme = scheme
        return self

    @property
    def scheme(self) -> dict[str, str]:
        """The fully assembled name scheme, usable by a dataset configuration.

        Returns:
            A fully assembled and validated name scheme.
        """
        return self._scheme


def normalize_plural_field(
        data: dict[Any, Any], singular: str, plural: str
) -> dict[Any, Any]:
    """Change fields that can accept singular or plural names into plural form.

    Args:
        data: A configuration dictionary to normalize.
        singular: The singular form of the key being normalized (e.g.
            'pattern').
        plural: The plural form of the key being normalized (e.g. 'patterns').

    Returns:
        The original configuration dictionary, with the given key in its to
        plural form and the value in list form, if it wasn't already.

    Raises:
        ValueError: If both singular and plural form are present in the
            configuration at once.
    """
    if singular in data and plural in data:
        raise ValueError(
            f'Field may be either {singular} or {plural}, not both.'
        )

    if singular in data:
        value = data.pop(singular)
        if isinstance(value, list):
            # Don't error, just accept it and change key type.
            data[plural] = value
        else:
            data[plural] = [value]

    return data


def normalize_user_path(user_path: Any) -> list[list[str]]:
    """Change path-related config values to expected format (list of lists).

    All path-related configuration is expected to be a list of directory
    levels to traverse, with each dir level potentially having multiple
    patterns that may be accepted (i.e. another list).

    This will output the user's configuration with the correct format, if
    possible. Nested empty lists and empty strings will be ignored.
    """
    if isinstance(user_path, str):
        return [[user_path]] if user_path else []

    if not isinstance(user_path, list):
        raise ValueError(
            f'Invalid input: "{user_path}". Expected a string or a list.'
        )

    fixed_path = []
    for entry in user_path:
        if isinstance(entry, str):
            if entry:
                # Only append if not empty string
                fixed_path.append([entry])
        elif isinstance(entry, list):
            if not all(isinstance(item, str) for item in entry):
                raise ValueError(
                    f'Invalid input: "{user_path}". Contents must be strings '
                    'or lists of strings only.'
                )
            # Strip empty strings
            filtered = [item for item in entry if item]
            if filtered:
                # Only append if not empty list
                fixed_path.append(filtered)
        else:
            raise ValueError(
                f'Invalid input: "{user_path}". Expected all contents to be '
                'strings or a lists of strings.'
            )

    return fixed_path


class FileValue(StrictBaseModel):
    """A single entry to be read from a metadata file and stored in a variable.
    """
    keys: list[str] = Field(min_length=1)
    store: str

    @model_validator(mode='before')
    @classmethod
    def normalize_keys(cls, data):
        """Normalize singular 'key' entries to plural 'keys' form if present.
        """
        if isinstance(data, dict):
            data = normalize_plural_field(data, 'key', 'keys')
        return data


class LoadedValues(StrictBaseModel):
    """Values that must be read from files during filesystem parsing.
    """
    format: FileTypes
    # Can be an empty list when user wants to load entire file.
    values: list[FileValue] = Field(default_factory=list)


def _populate_template(value: Any, info: ValidationInfo) -> Any:
    """Take a template string and populate it via a name scheme.

    Args:
        value: A template that may need to be filled in with components from
            the given naming scheme.
        info: The pydantic ValidationInfo object of the caller. Holds context
            necessary for validation (like name_scheme).

    Returns:
        The template, filled in by the naming scheme, or the original
            unmodified value if it's not recognizeable as a template so that
            pydantic may report the type error normally.

    Raises:
        ValueError: If 'name_scheme' is not defined in the context of the
            caller or if the template is invalid for any reason.
    """
    if not isinstance(value, str):
        # Let pydantic's normal validation process generate an error.
        return value

    if not info.context or 'name_scheme' not in info.context:
        raise ValueError('name_scheme must be provided in validation context.')

    scheme = info.context['name_scheme'].scheme

    try:
        unknown_fields = check_references(value, scheme)
    except ValueError as e:
        raise ValueError(f'Invalid template "{value}": {e}') from e

    if unknown_fields:
        raise ValueError(
            f'Template "{value}" contains unknown reference(s): '
            f'{", ".join(unknown_fields)}.'
        )

    return value.format_map(scheme)


TemplatedRegex = Annotated[re.Pattern[str],
                           BeforeValidator(_populate_template)]


class NameSchemeDependent(StrictBaseModel):
    """A convenience class for Models that require a NameScheme.
    """

    @classmethod
    def load(cls, data: Any, name_scheme: NameScheme) -> Self:
        """Create an instance with all required context.
        """
        return cls.model_validate(
            data,
            context={
                'name_scheme': name_scheme,
            }
        )

    @model_validator(mode='wrap')
    @classmethod
    def _require_name_scheme(cls, data, handler, info: ValidationInfo):
        """Fail early with a clear message if user tries to init incorrectly.
        """
        if (
            not info.context or
            'name_scheme' not in info.context or
            info.context['name_scheme'] is None
        ):
            raise ValueError(
                f'{cls.__name__} requires a valid NameScheme. '
                f'Try {cls.__name__}.load(data, name_scheme) instead.'
            )

        return handler(data)


class FileSystemItem(NameSchemeDependent):
    """Identifies an item to save/read from the filesystem.
    """
    label: str
    scope: ScopeTypes = 'series'
    stray_file: bool = False
    append_path: list[list[TemplatedRegex]] = Field(default_factory=list)
    patterns: list[TemplatedRegex] = Field(min_length=1)
    load_vals: LoadedValues | None = None

    @model_validator(mode='before')
    @classmethod
    def normalize_plural_form(cls, data):
        """Normalize fields that can be singular or plural to the plural form.
        """
        if isinstance(data, dict):
            attrs = [
                ('pattern', 'patterns'),
            ]
            for singular, plural in attrs:
                data = normalize_plural_field(data, singular, plural)
        return data

    @model_validator(mode='before')
    @classmethod
    def normalize_append_path(cls, data):
        """Change short-form path formats to expected format.
        """
        if isinstance(data, dict) and 'append_path' in data:
            normalized = normalize_user_path(data['append_path'])
            data['append_path'] = normalized

        return data


class IgnoreFileSystemItem(FileSystemItem):
    """Represents a filesystem item that should be ignored when encountered.

    This is for when the user is using 'strict' filesystem validation and
    doesn't want to receive error messages for certain files they expect
    to exist and don't want stored in the database.
    """
    # No label needed
    label: Literal['ignore'] = 'ignore'
    # Scope should always be 'ignore' and not configurable.
    scope: Literal['ignore'] = 'ignore'


def check_references(template: str, name_scheme: dict[str, str]) -> list[str]:
    """Check that every reference in template exists in name scheme.

    This will find and report _all_ non-existent items that a template tries
    to reference (versus failing on the first, like a simple .format_map check
    does). If the user mistakenly includes string format specs (``:10``) or
    conversion info (``!r``) it will be reported as an invalid reference.

    Args:
        template: The un-populated string template to check.
        name_scheme: A dictionary of template names mapped to valid regex
            strings (not yet compiled.)

    Returns:
        A list of all references the template makes that do not exist in the
        name scheme. If the entire template can be properly populated,
        an empty list will be returned.

    Raises:
        ValueError: If template is an invalidly formatted string (e.g.
            missing open or close brace).
    """
    invalid_references = []
    for _, field_name, format_spec, conversion in Formatter().parse(template):

        if field_name is None:
            # A literal-only chunk of text, skip it.
            continue

        # Treat these as part of a literal name.
        # String format/conversion not allowed in templates.
        if format_spec:
            field_name += f':{format_spec}'

        if conversion:
            field_name += f'!{conversion}'

        if field_name not in name_scheme:
            invalid_references.append(field_name)

    return invalid_references


class DatasetConfig(NameSchemeDependent):
    """Configuration for ingesting a dataset.
    """
    id: str
    description: str
    timepoint_dir: list[list[TemplatedRegex]] = Field(default_factory=list)
    append_path: list[list[TemplatedRegex]] = Field(default_factory=list)
    find: list[FileSystemItem] = Field(min_length=1)
    ignore: list[IgnoreFileSystemItem] = Field(default_factory=list)
    post_processors: list[PostProcessorConfig] = Field(default_factory=list)

    @model_validator(mode='before')
    @classmethod
    def normalize_paths(cls, data):
        """Normalize all path entries which may take string or list of lists.
        """
        if isinstance(data, dict):
            path_vars = ['append_path', 'timepoint_dir']
            for path_type in path_vars:
                if path_type in data:
                    normalized = normalize_user_path(data[path_type])
                    data[path_type] = normalized

        return data


##########################################################################
#### Everything from here down is temporary garbage

from dataclasses import dataclass, field

@dataclass
class InterForm:
    """Intermediary form for constructing tree form.
    """
    path: list[list[TemplatedRegex]]
    patterns: list[TemplatedRegex]
    entry: FileSystemItem | None = None
    children: list[FileSystemItem] = field(default_factory=list)


def is_grouped(entry: FileSystemItem) -> bool:
    """Check if a FileSystemItem is expected to be grouped into timepoint dirs.
    """
    if entry.scope == 'dataset':
        # Dataset level files don't get grouped into subject/timepoint dirs.
        return False

    if entry.stray_file:
        # Files deliberately marked 'stray' also don't
        return False

    return True


def make_inter_form(ds_conf: DatasetConfig) -> list[InterForm]:
    """Convert items from a dataset config into an intermediate form.

    This intermediate form can then be used to construct a tree of regexes
    to efficiently match while parsing an actual file tree.
    """
    entries = list(ds_conf.find)
    # 'strict' mode needs to be checked here...
    # Turn off adding ignore items if not strict checking.
    entries.extend(ds_conf.ignore)

    grouped = []
    free_items = []
    for entry in entries:
        if ds_conf.timepoint_dir and is_grouped(entry):
            grouped.append(
                InterForm(
                    path=entry.append_path,
                    patterns=entry.patterns,
                    entry=entry,
                )
            )
        else:
            free_items.append(
                InterForm(
                    path=entry.append_path,
                    patterns=entry.patterns,
                    entry=entry,
                )
            )

    if ds_conf.timepoint_dir:
        *pseudo_append_path, pseudo_patterns = ds_conf.timepoint_dir
        # The 'grouped' items get nested within the timepoint_dir
        free_items.append(
            InterForm(
                path=pseudo_append_path,
                patterns=pseudo_patterns,
                children=grouped,
            )
        )

    return free_items


@dataclass
class TreeNode:
    """A node representing a single directory or file.
    """
    files: dict[TemplatedRegex, InterForm] = field(default_factory=dict)
    subdirs: dict[TemplatedRegex, InterForm] = field(default_factory=dict)
    # Indicates anything matching should be saved to the database as
    # a 'timepoint_dir' / collection of files.
    is_tp_dir: bool = False


def make_tree(conf_items):
    """parse_data.make_tree

    Take parseable-format nodes and assemble them into a regex tree for
    matching against the filesystem being parsed.
    """
    files = {}
    subdirs = {}

    for entry in conf_items:
        if entry.path != []:
            # Gather every directory entry first before you recurse, to
            # catch redundancies up front.
            current_dir, *remaining = entry.path
            for alt_pattern in current_dir:
                subdirs.setdefault(alt_pattern, []).append((remaining, entry))
            continue

        # base case
        # Found a specific item or a timepoint dir (which is a subtree)
        if entry.children:
            # Create a subtree for each accepted timepoint_dir directory name
            for alt_pattern in entry.patterns:
                node = make_tree(entry.children)
                # This indicates the directory should be saved in the database.
                node.tp_dir = True
                files[alt_pattern] = node
        else:
            # Item represents a plain file
            for regex in entry.patterns:
                if regex in files:
                    raise Exception(
                        f'Duplicate file path/pattern given: {regex}'
                    )
                files[regex] = entry

    # Make sub-trees for the nested dirs
    final_dirs = {}
    for regex, entry in subdirs.items():
        node = make_tree(entry)
        final_dirs[regex] = node

    return TreeNode(files=files, subdirs=final_dirs)


def read_source_dir(source_path, conf_tree, collected=None, strict=True):
    """Parse a source directory using the tree form of the user configuration.

    Strict controls whether to report unmatched items as errors. If it's used,
    reporting may be turned off for select items by explicitly adding an
    'ignore' item for them in the dataset configuration.
    """
    collected = collected or {}
    found = {
        'tp_dirs': [],
        'files': [],
    }
    # This isn't collected if strict=False
    fails = []

    for item in source_path.iterdir():
        entry = None
        for regex in conf_tree.files:
            match = regex.match(item.name)
            if match:
                entry = match.groupdict()
                entry['path'] = item
                entry['conf'] = conf_tree.files[regex]
                if entry['conf'].entry.load_vals:
                    # Needs implementation still
                    load_metadata(entry)
                break

        if entry:
            all_vals = {**collected, **entry}
            # Found a match to a terminal item.
            if entry['conf'].entry.scope == 'ignore':
                # Deliberately ignore, so pass
                continue
            elif entry['conf'].is_tp_dir:
                found['tp_dirs'].append(all_vals)
            else:
                found['files'].append(all_vals)
            continue

        # No terminal item matched. If the item is not a dir, this an error.
        if not item.is_dir():
            if strict:
                fails.append(f'Unknown file found - {item}')
            continue

        match = None
        for dir_regex in conf_tree.subdirs:
            m = dir_regex.match(item.name)
            if m:
                match = m
                entry = {**collected, **match.groupdict()}
                conf = conf_tree.subdirs[dir_regex]
                break

        if not match:
            if strict:
                fails.append(f'Unknown directory found - {item}')
            continue

        # Collect files recursively from this directory
        subdir_results, subdir_fails = read_source_dir(
            item, conf_tree, entry
        )
        found['tp_dirs'].extend(subdir_results['tp_dirs'])
        found['files'].extend(subdir_results['files'])
        fails.extend(subdir_fails)

    return found, fails


def pydantic_load(ds_conf):
    """This is a temporary load function.

    Another prototype to get closer to a final setup.

    Takes in the pydantic class for a dataset config.
    """
    return


# def make_inter_form(ds_conf):
#     """
#     parse_data.make_parseable(find, timepoint_dir, ignore)
#     """
#     # To avoid modifying orig list
#     entries = list(ds_conf.find)
#     # safe even if no ignore items
#     # But might want to skip, if strict is turned off?
#     entries.extend(ds_conf.ignore)

#     nested = []
#     parseable = []
#     for entry in entries:
#         if (
#                 entry.scope == 'dataset' or
#                 entry.stray_file or
#                 not ds_conf.timepoint_dir
#         ):
#             parseable.append((entry.append_path, entry))
#         else:
#             nested.append((entry.append_path, entry))

#     # This doesn't really work now, because most entries are FindItem
#     # and now this pseudo one is a dict.
#     if ds_conf.timepoint_dir:
#         # All of path except last part is pseudo-append path
#         *fake_append_path, fake_pattern = ds_conf.timepoint_dir
#         tp_dir = {
#             'append_path': fake_append_path,
#             'pattern': fake_pattern,
#             'sub_entries': nested
#         }
#         parseable.append((fake_append_path, tp_dir))

#     # Maybe can take just append paths + patterns, but keep separate
#     # list of nested items (also append_path + patterns) and resume
#     # search per timepoint dir after discovering them like non-nested
#     # find items? i.e two searches and always on just path + pattern
#     return parseable


# def make_tree(parseable_nodes):
#     """
#     parse_data.make_tree
#     """
#     files = {}
#     dirs = {}

#     for path, entry in parseable_nodes:
#         if path != []:
#             # Gather every directory entry first before you recurse, to
#             # catch redundancies up front.
#             current_dir, *remaining = path
#             for alt_pattern in current_dir:
#                 dirs.setdefault(alt_pattern, []).append((remaining, entry))
#             continue

#         # base case
#         # Found a specific item or a timepoint dir (which is a subtree)
#         if 'sub_entries' in entry:
#             # Recursively create nodes for a timepoint_dir's children.
#             for alt_pattern in entry['pattern']:
#                 node = make_tree(entry['sub_entries'])
#                 node['tp_dir'] = True
#                 files[alt_pattern] = node
#         else:
#             # Just a plain file to discover
#             for regex in entry['pattern']:
#                 if regex in files:
#                     # raise exception here
#                     # exact same path + file is defined multiple times
#                     print(f'Duplicate file pattern given: {regex}')
#                     continue
#                 files[regex] = entry

#     # Make sub-trees for the nested dirs
#     final_dirs = {}
#     for regex, entry in dirs.items():
#         node = make_tree(entry)
#         final_dirs[regex] = node

#     return {'items': files, 'dirs': final_dirs}



