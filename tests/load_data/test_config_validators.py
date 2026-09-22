"""Tests for tigrqc.load_data.config_validators
"""
# pylint: disable=redefined-outer-name
import importlib
import typing

import pytest
from pydantic import BaseModel, ValidationError
from pydantic_core import PydanticCustomError

import tigrqc.load_data.config_validators as config
import tigrqc.load_data.post_processors  # Import needed for monkeypatch

# -----------------------------------------
# Mock post processor functions for testing
# -----------------------------------------


def mock_one_simple_kwarg(*, num: int):  # pylint: disable=unused-argument
    """A mock post-processor that takes a simple kwarg with no default.
    """
    return


def mock_simple_kwarg_w_default(
        *, num: int = 5
):  # pylint: disable=unused-argument
    """A mock post-processor that takes a simple kwarg with a default.
    """
    return


def mock_one_complex_kwarg(
        *, group_by: list[str] = ['subid', 'series']
):  # pylint: disable=unused-argument,dangerous-default-value
    """A mock post-processor that takes a list kwarg.
    """
    return


def mock_no_kwargs(input_files):  # pylint: disable=unused-argument
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
        model = config.build_kwargs_validator(mock_simple_kwarg_w_default)
        assert issubclass(model, BaseModel)

    def test_validator_ignores_function_params_that_arent_keyword_only(self):
        """Users can only set keyword-only params so the validator can safely
        ignore other arguments.
        """
        def func(
                pos_arg, *, kw_arg: int = 5
        ):  # pylint: disable=unused-argument
            pass

        model = config.build_kwargs_validator(func)

        assert 'kw_arg' in model.model_fields
        assert 'pos_arg' not in model.model_fields

    def test_validator_requires_arg_if_default_not_set(self):
        """When the function arg doesn't set a default the validator should
        raise an error if it's not set by the user.
        """
        def func(*, required: int):  # pylint: disable=unused-argument
            pass

        model = config.build_kwargs_validator(func)

        with pytest.raises(ValidationError):
            model()

        assert model(required=3).required == 3

    def test_default_is_correctly_used_when_arg_has_default(self):
        """Args with a default get treated as optional and set the default.
        """
        def func(
                *, optional: str = 'hello'
        ):  # pylint: disable=unused-argument
            pass

        model = config.build_kwargs_validator(func)

        assert model().optional == 'hello'
        assert model(optional='world').optional == 'world'

    def test_when_param_lacks_type_hint_it_is_treated_as_object_type(self):
        """If not type hints are given, it should be treated as generic object.
        """
        def func(*, anything=None):  # pylint: disable=unused-argument
            pass

        model = config.build_kwargs_validator(func)

        assert model.model_fields['anything'].annotation is object
        # object accepts any type
        assert model(anything=123).anything == 123
        assert model(anything='str').anything == 'str'
        assert model(anything=[1, 2, 3]).anything == [1, 2, 3]

    def test_raises_validation_error_when_unknown_arg_given(self):
        """Raise an exception if the user tries to use an unknown keyword arg.
        """
        def func(*, a: int = 1):  # pylint: disable=unused-argument
            pass

        model = config.build_kwargs_validator(func)

        with pytest.raises(ValidationError):
            model(b=2)

    def test_enforces_type_for_keyword_args(self):
        """If the function annotation has a type hint it must be enforced.
        """
        def func(*, count: int = 0):  # pylint: disable=unused-argument
            pass

        model = config.build_kwargs_validator(func)

        with pytest.raises(ValidationError):
            model(count='not-a-number')

        assert model(count=5).count == 5

    def test_model_fields_empty_when_no_keyword_only_params_for_function(self):
        """A function without keyword-only params should expect no args.
        """
        def func(a, b=2):  # pylint: disable=unused-argument
            pass

        model = config.build_kwargs_validator(func)

        assert model.model_fields == {}
        model()


class TestStrictBaseModel:
    """Tests for StrictBaseModel

    StrictBaseModel is a pydantic BaseModel that sets extra="forbid" by
    default.
    """

    def test_child_classes_forbid_extra_fields(self):
        """Child classes should raise when extra fields are given.
        """
        class MyTestClass(config.StrictBaseModel):
            """A test subclass of StrictBaseModel.
            """
            a: int

        assert MyTestClass(a=1).a == 1

        with pytest.raises(ValidationError):
            MyTestClass(a=1, b='hello')

    def test_returns_pydantics_init_error_details(self):
        """The output should be pydantic's InitErrorDetails.
        """
        result = config.StrictBaseModel.make_custom_error(
            err_type='some_error',
            err_msg='Something went wrong',
            user_input='bad-value',
        )

        assert isinstance(result, dict)  # InitErrorDetails is a TypedDict
        assert result['input'] == 'bad-value'
        assert isinstance(result['type'], PydanticCustomError)

    def test_loc_and_ctx_set_correct_default_values(self):
        """Defaults for these options should match pydantic's expectations.
        """
        result = config.StrictBaseModel.make_custom_error(
            err_type='some_error',
            err_msg='Something went wrong',
            user_input='bad-value',
        )

        assert result['loc'] == tuple()
        assert result['ctx'] == {}

    def test_provided_value_for_loc_gets_set_properly(self):
        """When 'loc' is given it can be retrieved from output.
        """
        result = config.StrictBaseModel.make_custom_error(
            err_type='some_error',
            err_msg='Something went wrong',
            user_input='bad-value',
            loc=('fields', 'my_field'),
        )

        assert result['loc'] == ('fields', 'my_field')

    def test_explicit_ctx_is_preserved_and_usable(self):
        """When 'ctx' is given it can be retrieved from output.
        """
        ctx = {'name': 'foo'}
        result = config.StrictBaseModel.make_custom_error(
            err_type='some_error',
            err_msg='Something went wrong',
            user_input='foo',
            ctx=ctx,
        )

        assert result['ctx'] == ctx

    def test_message_renders_with_ctx_inserted_when_raised(self):
        """When 'ctx' is given and err_msg contains a slot, ctx gets inserted.
        """
        error_detail = config.StrictBaseModel.make_custom_error(
            err_type='some_error',
            err_msg='Field {name} is invalid',
            user_input='foo',
            ctx={'name': 'foo'},
        )

        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError.from_exception_data(
                title='Test',
                line_errors=[error_detail],
            )

        assert 'Field foo is invalid' in str(exc_info.value)

    def test_message_without_ctx_slots_renders_as_is_even_with_ctx(self):
        """Message should be unaltered, even if ctx is given, if no slots.
        """
        error_detail = config.StrictBaseModel.make_custom_error(
            err_type='some_error',
            err_msg='Plain message with no slots',
            user_input='x',
            ctx={'name': 'foo'}
        )

        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError.from_exception_data(
                title='Test',
                line_errors=[error_detail],
            )

        assert 'Plain message with no slots' in str(exc_info.value)

    def test_err_type_is_reflected_in_exception_error_type(self):
        """The user provided 'err_type' should propagate to the exception.
        """
        error_detail = config.StrictBaseModel.make_custom_error(
            err_type='my_custom_type',
            err_msg='msg',
            user_input='x',
        )

        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError.from_exception_data(
                title='Test',
                line_errors=[error_detail],
            )

        errors = exc_info.value.errors()
        assert errors[0]['type'] == 'my_custom_type'


class TestPostProcessorConfig:
    """Tests for PostProcessorConfig
    """

    def test_args_defaults_to_empty_dict(self, mock_module_config):
        """'args' should be set to an empty dict when no args given and none
        are strictly required.
        """
        post_processor = mock_module_config.PostProcessorConfig

        result = post_processor(use='mock_simple_kwarg_w_default')
        assert result.args == {}

        result = post_processor(use='mock_no_kwargs')
        assert result.args == {}

    def test_raises_on_unknown_function_name(self, mock_module_config):
        """ValidationError should happen when user requests unknown function.
        """
        post_processor = mock_module_config.PostProcessorConfig

        with pytest.raises(ValidationError):
            post_processor(use='some_random_function')

    def test_default_scope_is_series(self, mock_module_config):
        """When user doesn't specify 'scope' it should be 'series'.
        """
        post_processor = mock_module_config.PostProcessorConfig

        result = post_processor(use='mock_no_kwargs')
        assert result.scope == 'series'

    def test_raises_on_invalid_scope(self, mock_module_config):
        """ValidationError should happen if user picks unknown 'scope'.
        """
        post_processor = mock_module_config.PostProcessorConfig

        with pytest.raises(ValidationError):
            post_processor(
                use='mock_one_simple_kwarg',
                scope='some random string',
            )

    @pytest.mark.parametrize('scope', typing.get_args(config.ScopeTypes))
    def test_accepts_all_valid_scope_types(self, mock_module_config, scope):
        """All valid scope types should be accepted for a function.
        """
        post_processor = mock_module_config.PostProcessorConfig
        result = post_processor(use='mock_no_kwargs', scope=scope)
        assert result.scope == scope

    def test_raises_when_missing_required_kwarg(self, mock_module_config):
        """An exception should happen when a kwarg with no default is missing.
        """
        post_processor = mock_module_config.PostProcessorConfig
        with pytest.raises(ValidationError):
            post_processor(use='mock_one_simple_kwarg', args={})

    def test_accepts_valid_kwargs(self, mock_module_config):
        """When arg types are correctly named and types they should pass.
        """
        post_processor = mock_module_config.PostProcessorConfig

        result = post_processor(
            use='mock_one_simple_kwarg',
            args={'num': 10},
        )
        assert result.args['num'] == 10

        groups = ['one', 'two', 'three']
        result = post_processor(
            use='mock_one_complex_kwarg',
            args={'group_by': groups},
        )
        assert result.args['group_by'] == groups

    def test_raises_on_unknown_arg_name(self, mock_module_config):
        """An exception should happen if the user provides an unknown arg
        """
        post_processor = mock_module_config.PostProcessorConfig
        with pytest.raises(ValidationError):
            post_processor(
                use='mock_one_simple_kwarg',
                args={'fake_arg': 1},
            )

    def test_raises_on_invalid_arg_type(self, mock_module_config):
        """An exception should happen if the wrong arg type is given.
        """
        post_processor = mock_module_config.PostProcessorConfig
        with pytest.raises(ValidationError):
            post_processor(
                use='mock_one_complex_kwarg',
                args={'group_by': 1},
            )

    def test_raises_on_unrecognized_top_level_field(self, mock_module_config):
        """An exception should happen if some unknown type level key given.
        """
        post_processor = mock_module_config.PostProcessorConfig
        with pytest.raises(ValidationError):
            post_processor(
                use='mock_one_simple_kwarg',
                extra_field='oops',
            )

    def test_accepts_valid_configuration(self, mock_module_config):
        """When all top level keys and args are correct, config should pass.
        """
        post_processor = mock_module_config.PostProcessorConfig

        args = {'group_by': ['fname']}

        result = post_processor(
            use='mock_one_complex_kwarg',
            args=args,
            scope='series',
        )

        expected_func = MOCK_POST_PROCESSORS['mock_one_complex_kwarg']

        assert result.function is expected_func
        assert result.scope == 'series'
        assert result.args == args


class TestNameSchemeHelpers:
    """Tests for NameScheme's helper functions (create_field, etc.)
    """
    # pylint: disable=protected-access

    def test_is_valid_group_name_correctly_finds_valid_names(self):
        """Is valid group name should be able to identify valid names.
        """
        assert config.NameScheme._is_valid_group_name('valid_name1')
        assert config.NameScheme._is_valid_group_name('MyGroupName')
        assert not config.NameScheme._is_valid_group_name('1_num_cant_start')
        assert not config.NameScheme._is_valid_group_name('has space')
        assert not config.NameScheme._is_valid_group_name('has-dash')
        assert not config.NameScheme._is_valid_group_name('')

    def test_create_field_wraps_field_in_regex_group(self):
        """Field is correctly wrapped in regex group.
        """
        group, error = config.NameScheme.create_field('subject', r'\d+')

        assert group == r'(?P<subject>\d+)'
        assert error is None

    def test_create_field_reports_re_compile_issues(self):
        """If re.compile has a problem it should produce an error message.
        """
        _, error = config.NameScheme.create_field('subject', '(')

        assert error is not None
        assert 'cannot compile' in error

    def test_create_template_fills_template_and_wraps_in_group(self):
        """A valid template should get filled in and wrapped in an re group.
        """
        fields = {'subject': r'(?P<subject>\d+)'}
        template, error = config.NameScheme.create_template(
            'sub_dir', 'sub-{subject}', fields
        )

        assert error is None
        assert template == r'(?P<sub_dir>sub-(?P<subject>\d+))'

    def test_create_template_reports_reference_to_unknown_field(self):
        """A template can't reference an unknown field/template.
        """
        template, error = config.NameScheme.create_template(
            'sub_dir', 'sub-{missing}', {}
        )

        assert template is None
        assert 'non-existent field' in error

    def test_report_invalid_group_names_returns_none_when_all_valid(self):
        """If all group names are valid, the result should be None.
        """
        result = config.NameScheme._report_invalid_group_names(
            {'good_name': 'also_good'}, check_vals=True
        )

        assert result is None

    def test_report_invalid_group_names_reports_bad_keys(self):
        """An invalid group name in the 'keys' should always be reported.
        """
        result = config.NameScheme._report_invalid_group_names(
            {'Bad name': 'valid_name'}
        )

        assert 'Bad name' in result

    def test_report_invalid_group_names_checks_keys_only_by_default(self):
        """An invalid group name in values should be ignored by default.
        """
        result = config.NameScheme._report_invalid_group_names(
            {'good_key': 'bad value'}
        )

        assert result is None

    def test_report_invalid_group_names_checks_values_when_requested(self):
        """If check_vals=True, should report invalid re groups in values too.
        """
        result = config.NameScheme._report_invalid_group_names(
            {'good_key': 'bad value'}, check_vals=True
        )

        assert result is not None
        assert 'bad value' in result


class TestNameSchemeNameFormats:
    """NameScheme tests of field/template/field_map name validity.
    """

    def test_invalid_field_name_raises_validation_error(self):
        """A field name that isn't a valid regex group should raise.
        """
        with pytest.raises(ValidationError, match='Invalid entries'):
            config.NameScheme(fields={'bad name': r'\d+'}, templates={})

    def test_field_name_starting_with_number_is_invalid(self):
        """Regex groups can't start with a number.
        """
        with pytest.raises(ValidationError, match='Invalid entries'):
            config.NameScheme(fields={'1subject': r'\d+'}, templates={})

    def test_invalid_field_map_key_raises_validation_error(self):
        """The keys in field_map must be valid group names.
        """
        with pytest.raises(ValidationError, match='Invalid entries'):
            config.NameScheme(
                field_map={'bad key': 'sub'},
                fields={'subject': r'\d+'},
                templates={},
            )

    def test_invalid_field_map_value_raises_validation_error(self):
        """The values in field_map must be valid group names.
        """
        with pytest.raises(ValidationError, match='Invalid entries'):
            config.NameScheme(
                field_map={'subject': 'bad value'},
                fields={'subject': r'\d+'},
                templates={},
            )

    def test_invalid_template_name_raises_validation_error(self):
        """Template names must be a valid regex group name.
        """
        with pytest.raises(ValidationError, match='Invalid entries'):
            config.NameScheme(
                fields={'subject': r'\d+'},
                templates={'bad name': 'sub-{subject}'},
            )


class TestNameScheme:
    """Tests for core NameScheme functionality.
    """

    def test_exception_raised_when_required_config_missing(self):
        """If a required config entry is absent, it should raise an exception.
        """
        with pytest.raises(ValidationError):
            # fields missing
            config.NameScheme(templates={})

        with pytest.raises(ValidationError):
            # templates missing
            config.NameScheme(fields={})

    def test_exception_raised_when_unknown_top_level_key_is_found(self):
        """An unknown configuration key should raise an exception.
        """
        with pytest.raises(ValidationError):
            config.NameScheme(fields={}, templates={}, whoopsy={})

    def test_accepts_fields_only_w_empty_templates(self):
        """Accepts config that contains fields and empty templates.
        """
        ns = config.NameScheme(
            fields={'subject': r'\d+', 'session': r'\d+'},
            templates={},
        )

        assert ns.scheme == {
            'subject': r'(?P<subject>\d+)',
            'session': r'(?P<session>\d+)',
        }

    def test_sets_defaults_when_field_map_and_post_processors_not_given(self):
        """field_map and post_processors should be fully optional.
        """
        ns = config.NameScheme(fields={'subject': r'\d+'}, templates={})

        assert ns.field_map == {}
        assert ns.post_processors == []

    def test_accepts_template_that_references_a_field(self):
        """A template should be properly filled in when it references a field.
        """
        ns = config.NameScheme(
            fields={'subject': r'\d+'},
            templates={'sub_dir': 'sub-{subject}'},
        )

        assert ns.scheme['subject'] == r'(?P<subject>\d+)'
        assert ns.scheme['sub_dir'] == r'(?P<sub_dir>sub-(?P<subject>\d+))'

    def test_accepts_template_that_references_an_earlier_defined_template(
            self
    ):
        """A template should be able to be filled in with another template.
        """
        ns = config.NameScheme(
            fields={'subject': r'\d+', 'session': r'\d+'},
            templates={
                'sub_dir': 'sub-{subject}',
                'full_dir': '{sub_dir}/ses-{session}',
            },
        )

        expected_regex = (
            r'(?P<full_dir>'
            r'(?P<sub_dir>sub-(?P<subject>\d+))'
            r'/ses-(?P<session>\d+))'
        )

        assert 'sub_dir' in ns.scheme
        assert 'full_dir' in ns.scheme
        assert ns.scheme['full_dir'] == expected_regex

    def test_field_map_correctly_renames_field_group_names(self):
        """A field name in field_map should have its group renamed.
        """
        ns = config.NameScheme(
            field_map={'subject': 'sub'},
            fields={'subject': r'\d+'},
            templates={},
        )

        assert ns.scheme['subject'] == r'(?P<sub>\d+)'

    def test_field_map_correctly_renames_template_group_names(self):
        """A template name in field_map should have its group renamed.
        """
        ns = config.NameScheme(
            field_map={'sub_dir': 'subject_dir'},
            fields={'subject': r'\d+'},
            templates={'sub_dir': 'sub-{subject}'},
        )

        assert ns.scheme['sub_dir'] == r'(?P<subject_dir>sub-(?P<subject>\d+))'

    def test_scheme_property_matches_private_attr(self):
        """The 'scheme' property should just return the private attribute.
        """
        ns = config.NameScheme(fields={'subject': r'\d+'}, templates={})

        assert ns.scheme is ns._scheme  # pylint: disable=protected-access

    def test_exception_raised_when_template_references_unknown_field(self):
        """Template can't be filled if it requests an undefined field.
        """
        with pytest.raises(ValidationError, match='unknown field'):
            config.NameScheme(
                fields={'subject': r'\d+'},
                templates={'sub_dir': 'sub-{nonexistent}'},
            )

    def test_exception_raised_when_template_referenced_before_it_exists(self):
        """If a template uses another template, it must be defined after it.
        """
        with pytest.raises(ValidationError, match='must be defined after'):
            config.NameScheme(
                fields={'subject': r'\d+', 'session': r'\d+'},
                templates={
                    'full_dir': '{sub_dir}/ses-{session}',
                    'sub_dir': 'sub-{subject}',
                },
            )

    def test_template_with_no_references_is_valid(self):
        """Accept templates that are literals or plain regexes.
        """
        ns = config.NameScheme(
            fields={'subject': r'\d+'},
            templates={'literal': 'just-a-literal-string'},
        )

        assert ns.scheme['literal'] == r'(?P<literal>just-a-literal-string)'

    def test_multiple_unknown_fields_get_reported_at_once(self):
        """If multiple errors exist at once, all should be reported in one go.
        """
        with pytest.raises(ValidationError) as exc_info:
            config.NameScheme(
                fields={'subject': r'\d+'},
                templates={'bad': '{foo}-{bar}'},
            )

        msg = str(exc_info.value)
        assert 'foo' in msg
        assert 'bar' in msg

    def test_duplicate_groups_in_a_template_raise_unique_exception(self):
        """Raise when a template mistakenly duplicates a group name.
        """
        with pytest.raises(ValidationError, match='Duplicate fields exist'):
            # Both fields have their groups renamed to 'dup'
            # And then the template references both fields... leading to
            # two regex groups named 'dup'
            config.NameScheme(
                field_map={'subject': 'dup', 'session': 'dup'},
                fields={'subject': r'\d+', 'session': r'\d+'},
                templates={'full_dir': 'sub-{subject}/ses-{session}'},
            )

    def test_bare_quantifier_raises_unique_exception(self):
        """If the user gives a regex with something like '*' it should fail.
        """
        with pytest.raises(ValidationError, match='quantifiers'):
            config.NameScheme(fields={'subject': '*'}, templates={})

    def test_raises_exception_on_generic_regex_compile_issues(self):
        """Any generic issue compiling a regex should raises an exception.
        """
        with pytest.raises(ValidationError, match='cannot compile'):
            config.NameScheme(fields={'subject': '('}, templates={})

    def test_collects_all_field_errors_when_multiple_exist(self):
        """If multiple issues exist, it shouldn't just raise the first one.
        """
        with pytest.raises(ValidationError) as exc_info:
            config.NameScheme(
                fields={'subject': '*', 'session': '('},
                templates={},
            )

        errors = exc_info.value.errors()
        assert len(errors) == 2


class TestCheckReferences:
    """Tests for check_references
    """

    @pytest.fixture
    def name_scheme(self):
        """A mock name scheme for testing errors in template references.
        """
        scheme = {
            'subject': '(?!PHA)[^_]+',
            'timepoint': '[0-9]{2}',
            'site': '[^_]+',
        }
        return scheme

    @pytest.mark.parametrize('template', [
        '',
        'plain text, nothing to populate',
        '{subject}',
        '{subject}-{site}',
        'prefix_{subject}_suffix',
    ])
    def test_returns_empty_list_when_all_references_exist(
        self, template, name_scheme
    ):
        """Result should be empty list when all refs are in name_scheme.
        """
        assert config.check_references(template, name_scheme) == []

    def test_empty_list_when_name_scheme_empty_and_literal_template(self):
        """A template without references should produce empty list.
        """
        assert config.check_references('just text', {}) == []

    def test_reports_single_unknown_reference(self, name_scheme):
        """A single unknown reference should be caught.
        """
        assert config.check_references('{missing}', name_scheme) == ['missing']

    def test_reports_all_unknown_refs_not_just_first(self, name_scheme):
        """All unknown references should be reported, not just first.
        """
        result = config.check_references('{a}-{subject}-{b}-{c}', name_scheme)
        assert result == ['a', 'b', 'c']

    def test_all_refs_reported_when_name_scheme_empty(self):
        """If name scheme is empty, any reference at all is invalid.
        """
        assert config.check_references('{name}{year}', {}) == ['name', 'year']

    def test_references_are_case_sensitive(self, name_scheme):
        """Name scheme references are always case-sensitive.
        """
        assert config.check_references('{Subject}', name_scheme) == ['Subject']

    def test_empty_reference_is_reported_as_empty_string(self, name_scheme):
        """An empty reference is considered the empty string and reported.
        """
        assert config.check_references('{}', name_scheme) == ['']

    def test_format_spec_causes_known_field_to_be_invalid(self, name_scheme):
        """String format specs are not accepted. Render whole ref invalid.
        """
        result = config.check_references('{subject:>10}', name_scheme)
        assert result == ['subject:>10']

    def test_string_conversion_causes_known_field_to_be_invalid(
            self, name_scheme
    ):
        """String conversion not accepted. Renders whole ref invalid.
        """
        result = config.check_references('{subject!r}', name_scheme)
        assert result == ['subject!r']

    def test_both_string_conversion_and_format_spec_get_reported(
            self, name_scheme
    ):
        """If both given, the reported invalid ref contains both.
        """
        result = config.check_references('{subject!r:>10}', name_scheme)
        assert result == ['subject:>10!r']

    def test_nested_references_raise_value_error(self, name_scheme):
        """Nesting references is not allowed.
        """
        with pytest.raises(ValueError):
            config.check_references('{subject{site}}', name_scheme)

    def test_only_reports_invalid_refs_when_valid_exist_too(self, name_scheme):
        result = config.check_references(
            '{subject} {timepoint:04d} {site!s}', name_scheme
        )
        assert result == ['timepoint:04d', 'site!s']

    @pytest.mark.parametrize('template', [
        '{{}}',
        '{{name}}',
        'a {{literal}} b',
    ])
    def test_escaped_braces_arent_references(self, template, name_scheme):
        """Escaped braces are treated as a literal string.
        """
        assert config.check_references(template, {}) == []

    @pytest.mark.parametrize('template', [
        '{',
        '}',
        '{subject',
        'subject}',
        '{subject}{',
        'text {unclosed',
        '{subject:{site}',
    ])
    def test_invalid_template_raises_value_error(self, template, name_scheme):
        """Templates with unclosed braces should raise a ValueError.
        """
        with pytest.raises(ValueError):
            config.check_references(template, name_scheme)

    def test_does_not_modify_name_scheme(self, name_scheme):
        orig_scheme = dict(name_scheme)
        config.check_references('{subject}{missing}', name_scheme)
        assert orig_scheme == name_scheme


class TestNormalizePluralField:
    """Test normalize_plural_field
    """
    def test_fields_not_mentioned_arent_modified(self):
        """Unrelated keys in data shouldn't be changed.
        """
        data = {'other': 1}
        result = config.normalize_plural_field(data, 'key', 'keys')

        assert result == {'other': 1}

    def test_fields_already_plural_arent_modified(self):
        """If a field is already plural it shouldn't be changed.
        """
        data = {'keys': ['a', 'b']}
        result = config.normalize_plural_field(data, 'key', 'keys')

        assert result == {'keys': ['a', 'b']}

    def test_singular_field_replaced_with_plural_name(self):
        """When the singular is present it should be updated to plural.
        """
        data = {'key': 'a'}
        result = config.normalize_plural_field(data, 'key', 'keys')

        assert 'key' not in result
        assert result == {'keys': ['a']}

    def test_normalized_field_also_wraps_value_in_list(self):
        """A singular field changed to plural should also have list value.
        """
        data = {'key': 'a'}
        result = config.normalize_plural_field(data, 'key', 'keys')

        assert 'key' not in result
        assert result == {'keys': ['a']}

    def test_normalized_field_value_unmodified_if_already_list(self):
        """Singular field name with plural value only updates field name.
        """
        data = {'key': ['a', 'b']}
        result = config.normalize_plural_field(data, 'key', 'keys')

        assert result == {'keys': ['a', 'b']}

    def test_raises_when_both_singular_and_plural_form_present(self):
        """Only singular OR plural is valid. Both is an error.
        """
        data = {'key': 'a', 'keys': ['b']}

        with pytest.raises(ValueError, match='not both'):
            config.normalize_plural_field(data, 'key', 'keys')

    def test_modifies_in_place_and_returns_orig_input(self):
        """Changes are done in place. Returned value is just original data.
        """
        data = {'key': 'a'}
        result = config.normalize_plural_field(data, 'key', 'keys')

        assert result is data


class TestFileValue:
    """Tests for FileValue
    """

    def test_accepts_valid_configuration(self):
        """Valid inputs should result in config object creation.
        """
        keys = ['bids_meta', 'SeriesDescription']
        store = 'description'

        fv = config.FileValue(keys=keys, store=store)

        assert fv.keys == keys
        assert fv.store == store

    def test_singular_key_accepted_and_made_plural_form(self):
        """When file keys are given in singular form should become plural.
        """
        fv = config.FileValue(key='SeriesDescription', store='description')

        assert fv.keys == ['SeriesDescription']

    def test_singular_key_with_list_value_accepted_and_normalized(self):
        """Using singular 'key' with list of values is fine and becomes 'keys'.
        """
        key = ['bids_meta', 'SeriesDescription']
        store = 'description'

        fv = config.FileValue(key=key, store=store)

        assert fv.keys == key

    def test_providing_both_key_and_keys_raises_exception(self):
        """Only one of 'key' and 'keys' can be used, not both.
        """
        with pytest.raises(ValidationError):
            config.FileValue(key='a', keys=['b'], store='x')

    def test_missing_required_fields_raises(self):
        """Any missing required field should raise an exception.
        """
        with pytest.raises(ValidationError):
            # Missing key/keys
            config.FileValue(store='x')

        with pytest.raises(ValidationError):
            # Missing store
            config.FileValue(key='a')


class TestLoadedValues:
    """Tests for LoadedValues
    """
    def test_accepts_valid_configuration(self):
        """Config object should be made when valid config given.
        """
        lv = config.LoadedValues(
            file_format='yaml',
            values=[config.FileValue(key='a', store='x')],
        )

        assert lv.file_format == 'yaml'
        assert len(lv.values) == 1
        assert lv.values[0].keys == ['a']

    def test_values_can_accept_plain_dict_objects(self):
        """Pydantic should coerce a dict to a FileValue automatically.
        """
        lv = config.LoadedValues(
            file_format='json',
            values=[{'key': 'a', 'store': 'x'}],
        )

        assert isinstance(lv.values[0], config.FileValue)

    def test_empty_values_list_allowed(self):
        lv = config.LoadedValues(file_format='yaml', values=[])

        assert lv.values == []

    def test_invalid_file_format_raises(self):
        with pytest.raises(ValidationError):
            config.LoadedValues(file_format='not-a-real-format-xyz', values=[])
