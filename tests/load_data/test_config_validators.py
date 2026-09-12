"""Tests for tigrqc.load_data.config_validators
"""
import importlib
import typing

import pytest
from pydantic import BaseModel, ValidationError

import tigrqc.load_data.config_validators as config
import tigrqc.load_data.post_processors  # Import needed for monkeypatch


# -----------------------------------------
# Mock post processor functions for testing
# -----------------------------------------


def mock_one_simple_kwarg(*, num: int):
    """A mock post-processor that takes a simple kwarg with no default.
    """
    return


def mock_simple_kwarg_w_default(*, num: int = 5):
    """A mock post-processor that takes a simple kwarg with a default.
    """
    return


def mock_one_complex_kwarg(*, group_by: list[str] = ['subid', 'series']):
    """A mock post-processor that takes a list kwarg.
    """
    return


def mock_no_kwargs(input):
    """A mock post-processor with no keyword-only args.
    """
    return


MOCK_POST_PROCESSORS = {
    'mock_one_simple_kwarg': mock_one_simple_kwarg,
    'mock_simple_kwarg_w_default': mock_simple_kwarg_w_default,
    'mock_one_complex_kwarg': mock_one_complex_kwarg,
    'mock_no_kwargs': mock_no_kwargs,
}


@pytest.fixture
def mock_module_config(monkeypatch):
    """Use mock post-processors for better edge case testing.

    Restores the original post processors after test finishes, to avoid
    impacting other tests.
    """
    monkeypatch.setattr(
        tigrqc.load_data.post_processors,
        'POST_PROCESSORS',
        MOCK_POST_PROCESSORS,
    )

    reloaded = importlib.reload(config)
    yield reloaded

    # Restore environment to normal to avoid affecting other tests
    monkeypatch.undo()
    importlib.reload(config)


class TestBuildKwargsValidator:
    """Tests for build_kwargs_validator
    """

    def test_output_is_a_pydantic_model(self):
        """Resulting model/validator is pydantic BaseModel.
        """
        def func(*, a: int = 1):
            pass

        Model = config.build_kwargs_validator(func)
        assert issubclass(Model, BaseModel)

    def test_validator_ignores_function_params_that_arent_keyword_only(self):
        """Users can only set keyword-only params so the validator can safely
        ignore other arguments.
        """
        def func(pos_arg, *, kw_arg: int = 5):
            pass

        Model = config.build_kwargs_validator(func)

        assert 'kw_arg' in Model.model_fields
        assert 'pos_arg' not in Model.model_fields

    def test_validator_requires_arg_if_default_not_set(self):
        """When the function arg doesn't set a default the validator should
        raise an error if it's not set by the user.
        """
        def func(*, required: int):
            pass

        Model = config.build_kwargs_validator(func)

        with pytest.raises(ValidationError):
            Model()

        assert Model(required=3).required == 3

    def test_default_is_correctly_used_when_arg_has_default(self):
        """Args with a default get treated as optional and set the default.
        """
        def func(*, optional: str = 'hello'):
            pass

        Model = config.build_kwargs_validator(func)

        assert Model().optional == 'hello'
        assert Model(optional='world').optional == 'world'

    def test_when_param_lacks_type_hint_it_is_treated_as_object_type(self):
        def func(*, anything=None):
            pass

        Model = config.build_kwargs_validator(func)

        assert Model.model_fields['anything'].annotation is object
        # object accepts any type
        assert Model(anything=123).anything == 123
        assert Model(anything='str').anything == 'str'
        assert Model(anything=[1, 2, 3]).anything == [1, 2, 3]

    def test_raises_ValidationError_when_unknown_arg_given(self):
        """Raise an exception if the user tries to use an unknown keyword arg.
        """
        def func(*, a: int = 1):
            pass

        Model = config.build_kwargs_validator(func)

        with pytest.raises(ValidationError):
            Model(b=2)

    def test_enforces_type_for_keyword_args(self):
        """If the function annotation has a type hint it must be enforced.
        """
        def func(*, count: int = 0):
            pass

        Model = config.build_kwargs_validator(func)

        with pytest.raises(ValidationError):
            Model(count='not-a-number')

        assert Model(count=5).count == 5

    def test_model_fields_empty_when_no_keyword_only_params_for_function(self):
        """A function without keyword-only params should expect no args.
        """
        def func(a, b=2):
            pass

        Model = config.build_kwargs_validator(func)

        assert Model.model_fields == {}
        Model()


class TestStrictBaseModel:
    """Tests for StrictBaseModel

    StrictBaseModel is a pydantic BaseModel that sets extra="forbid" by
    default.
    """

    def test_child_classes_forbid_extra_fields(self):
        """Child classes should raise when extra fields are given.
        """
        class MyTestClass(config.StrictBaseModel):
            a: int

        assert MyTestClass(a=1).a == 1

        with pytest.raises(ValidationError):
            MyTestClass(a=1, b='hello')


class TestPostProcessorConfig:
    """Tests for PostProcessorConfig
    """

    def test_args_defaults_to_empty_dict(self, mock_module_config):
        """'args' should be set to an empty dict when no args given and none
        are strictly required.
        """
        PostProcessorConfig = mock_module_config.PostProcessorConfig

        result = PostProcessorConfig(use='mock_simple_kwarg_w_default')
        assert result.args == {}

        result = PostProcessorConfig(use='mock_no_kwargs')
        assert result.args == {}

    def test_raises_on_unknown_function_name(self, mock_module_config):
        """ValidationError should happen when user requests unknown function.
        """
        PostProcessorConfig = mock_module_config.PostProcessorConfig

        with pytest.raises(ValidationError):
            PostProcessorConfig(use='some_random_function')

    def test_default_scope_is_series(self, mock_module_config):
        """When user doesn't specify 'scope' it should be 'series'.
        """
        PostProcessorConfig = mock_module_config.PostProcessorConfig

        result = PostProcessorConfig(use='mock_no_kwargs')
        assert result.scope == 'series'

    def test_raises_on_invalid_scope(self, mock_module_config):
        """ValidationError should happen if user picks unknown 'scope'.
        """
        PostProcessorConfig = mock_module_config.PostProcessorConfig

        with pytest.raises(ValidationError):
            PostProcessorConfig(
                use='mock_one_simple_kwarg',
                scope='some random string',
            )

    @pytest.mark.parametrize('scope', typing.get_args(config.ScopeTypes))
    def test_accepts_all_valid_scope_types(self, mock_module_config, scope):
        """All valid scope types should be accepted for a function.
        """
        PostProcessorConfig = mock_module_config.PostProcessorConfig
        result = PostProcessorConfig(use='mock_no_kwargs', scope=scope)
        assert result.scope == scope

    def test_raises_when_missing_required_kwarg(self, mock_module_config):
        """An exception should happen when a kwarg with no default is missing.
        """
        PostProcessorConfig = mock_module_config.PostProcessorConfig
        with pytest.raises(ValidationError):
            PostProcessorConfig(use='mock_one_simple_kwarg', args={})

    def test_accepts_valid_kwargs(self, mock_module_config):
        """When arg types are correctly named and types they should pass.
        """
        PostProcessorConfig = mock_module_config.PostProcessorConfig

        result = PostProcessorConfig(
            use='mock_one_simple_kwarg',
            args={'num': 10},
        )
        assert result.args['num'] == 10

        groups = ['one', 'two', 'three']
        result = PostProcessorConfig(
            use='mock_one_complex_kwarg',
            args={'group_by': groups},
        )
        assert result.args['group_by'] == groups

    def test_raises_on_unknown_arg_name(self, mock_module_config):
        """An exception should happen if the user provides an unknown arg
        """
        PostProcessorConfig = mock_module_config.PostProcessorConfig
        with pytest.raises(ValidationError):
            PostProcessorConfig(
                use='mock_one_simple_kwarg',
                args={'fake_arg': 1},
            )

    def test_raises_on_invalid_arg_type(self, mock_module_config):
        """An exception should happen if the wrong arg type is given.
        """
        PostProcessorConfig = mock_module_config.PostProcessorConfig
        with pytest.raises(ValidationError):
            PostProcessorConfig(
                use='mock_one_complex_kwarg',
                args={'group_by': 1},
            )

    def test_raises_on_unrecognized_top_level_field(self, mock_module_config):
        """An exception should happen if some unknown type level key given.
        """
        PostProcessorConfig = mock_module_config.PostProcessorConfig
        with pytest.raises(ValidationError):
            PostProcessorConfig(
                use='mock_one_simple_kwarg',
                extra_field='oops',
            )

    def test_accepts_valid_configuration(self, mock_module_config):
        """When all top level keys and args are correct, config should pass.
        """
        PostProcessorConfig = mock_module_config.PostProcessorConfig

        args = {'group_by': ['fname']}

        result = PostProcessorConfig(
            use='mock_one_complex_kwarg',
            args=args,
            scope='series',
        )

        expected_func = MOCK_POST_PROCESSORS['mock_one_complex_kwarg']

        assert result.function is expected_func
        assert result.scope == 'series'
        assert result.args == args
