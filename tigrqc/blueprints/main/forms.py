"""Forms for the main views in the application.
"""
from flask_wtf import FlaskForm
from wtforms import (BooleanField, SelectMultipleField, StringField,
                     TextAreaField)
from wtforms.validators import DataRequired, Length, Regexp

from tigrqc.models import Project, Site


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
            'title': (
                f'Provide a short (<={Project.id.type.length} char) '
                'unique ID for the project.'
            ),
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
    sites = SelectMultipleField(
        'Sites',
        render_kw={
            'id': 'select-site',
            'title': 'Scan sites that collect data for the project.'
        }
    )


class SiteForm(FlaskForm):
    """Form to add a new scan site.
    """
    id = StringField(
        'Site ID',
        [
            Length(max=Site.id.type.length),
            DataRequired(),
        ],
        render_kw={
            'maxlength': Site.id.type.length,
            'title': (
                f'Provide a short (<={Site.id.type.length} char) '
                'unique ID for the scan site.'
            ),
        }
    )
    name = StringField(
        'Full Name',
        [
            Length(max=Site.name.type.length)
        ],
        render_kw={
            'maxlength': Site.name.type.length,
            'title': (
                'Provide an optional long for name for the site to help '
                'recognize the site.'
            )
        }
    )
    description = TextAreaField(
        'Description',
        render_kw={
            'title': 'An extended name and/or description for the scan site.'
        }
    )
