"""Validators for user provided configuration used during data import.
"""
import inspect
from typing import Callable

from pydantic import create_model, ConfigDict, BaseModel

from .post_processors import POST_PROCESSORS


class StrictBaseModel(BaseModel):
    """Ensure un-recognized fields are treated as errors.
    """
    # Catches user-typos
    model_config = ConfigDict(extra="forbid")


def build_kwargs_validator(func: Callable) -> type[StrictBaseModel]:
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

    return create_model(f"KwargsModel_{func.__name__}", **kwargs)


# Used to check that user-provided args are valid for the function they want.
USER_ARG_VALIDATORS = {
    name: build_kwargs_validator(func) for name, func in POST_PROCESSORS.items()
}
