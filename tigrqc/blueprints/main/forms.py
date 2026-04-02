"""Forms for the main views in the application.
"""
from flask_wtf import FlaskForm
from wtforms import BooleanField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Regexp

from tigrqc.models import Project


class ProjectForm(FlaskForm):
    """Form to add a new project.
    """
    id = StringField(
        'Project ID',
        [
            Length(min=3, max=Project.id.type.length),
            DataRequired(),
            Regexp(
                r'^[a-zA-Z0-9]+$',
                message='ID can only contain letters and numbers.'
            ),
        ],
        render_kw={
            'maxlength': Project.id.type.length,
            'title': 'Provide a short (<=32 char) unique ID for the project.'
        }
    )
    name = StringField(
        'Project Name',
        [Length(max=Project.name.type.length)],
        render_kw={
            'maxlength': Project.name.type.length,
            'title': 'The full name of the project.',
        }
    )
    description = TextAreaField(
        'Description',
        render_kw={
            'title': 'An extended description of this project / dataset.'
        }
    )
    is_active = BooleanField(
        'Actively Collecting Data',
        default=True,
        render_kw={
            'title': 'Is the project collecting data still?'
        }
    )
