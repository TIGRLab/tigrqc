"""Forms for the main views in the application.
"""
from flask_wtf import FlaskForm
from sqlalchemy import select
from wtforms import (BooleanField, RadioField, SelectMultipleField,
                     StringField, TextAreaField)
from wtforms.validators import DataRequired, Length, Regexp

from tigrqc.extensions import db
from tigrqc.models import DatasetType, NameScheme, Project, Site
from tigrqc.validators import SafePath


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


class DataFolderForm(FlaskForm):
    """Form to add a new data input source from the file system.
    """
    path = StringField(
        'Choose directory',
        [
            # Max length of a path on Linux
            Length(max=4096),
            DataRequired(),
            SafePath(),
        ],
        render_kw={
            'maxlength': 4096,
            'title': 'Select a directory to load data from.',
            'placeholder': 'Type path or select from file tree.',
            'id': 'dir-input',
        },
    )
    name_type = RadioField(
        'Naming Convention',
        [
            DataRequired()
        ],
        render_kw={
            'title': 'The naming convention used for these files.'
        },
    )
    data_type = RadioField(
        'Dataset Type',
        [
            DataRequired()
        ],
        render_kw={
            'title': 'Determines how these files will be used and displayed.'
        },
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set choices in form based on database contents
        name_types = db.session.scalars(
            select(NameScheme).order_by(NameScheme.id)
        ).all()
        data_types = db.session.scalars(
            select(DatasetType).order_by(DatasetType.id)
        ).all()

        self.name_type.choices = [
            (nc.id, nc.description)
            for nc in name_types
        ]

        self.data_type.choices = [
            (dt.id, dt.description)
            for dt in data_types
        ]
