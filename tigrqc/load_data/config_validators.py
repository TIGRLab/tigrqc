"""Validators for user provided configuration used during data import.
"""
import inspect
import re
from string import Formatter
from typing import Any, Callable, Literal, Self

from pydantic import (BaseModel, ConfigDict, Field, PrivateAttr,
                      ValidationError, ValidationInfo, create_model,
                      field_validator, model_validator)
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

            unknown_fields = []
            for _, field_name, _, _ in Formatter().parse(template):
                if field_name is not None and field_name not in avail_fields:
                    unknown_fields.append(field_name)

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
