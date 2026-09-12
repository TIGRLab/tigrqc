"""Validators for user provided configuration used during data import.
"""
import inspect
from typing import Any, Callable, Literal

from pydantic import (Field, create_model, ConfigDict, BaseModel,
                      model_validator)

from .parsers import FILE_READERS
from .post_processors import POST_PROCESSORS


FileTypes = Literal[tuple(FILE_READERS.keys())]
ScopeTypes = Literal["dataset", "timepoint", "attempt", "series"]
PostProcessorTypes = Literal[tuple(POST_PROCESSORS.keys())]


class StrictBaseModel(BaseModel):
    """Ensure un-recognized fields are treated as errors.
    """
    # Catches user-typos
    model_config = ConfigDict(extra="forbid")


class PostProcessorConfig(StrictBaseModel):
    """Configuration for a post processor that will be run on input data.
    """
    use: PostProcessorTypes
    scope: ScopeTypes = 'series'
    args: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode='after')
    def get_function(self):
        """Retrieve the function from the user's string.
        """
        self._func = POST_PROCESSORS[self.use]
        return self

    @property
    def function(self):
        return self._func

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
            annotation = object
        else:
            annotation = param.annotation

        if param.default is inspect.Parameter.empty:
            default = ...
        else:
            default = param.default

        kwargs[name] = (annotation, default)

    model_config = ConfigDict(extra="forbid")
    validator = create_model(
        f"KwargsModel_{func.__name__}",
        __config__=model_config,
        **kwargs
    )

    return validator


# Used to check that user-provided args are valid for the function they want.
USER_ARG_VALIDATORS = {
    name: build_kwargs_validator(func) for name, func in POST_PROCESSORS.items()
}
