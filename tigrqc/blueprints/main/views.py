"""Core application views (project listing, creation, etc.)
"""
from flask import flash, redirect, render_template, url_for
from sqlalchemy import select

from tigrqc.exceptions import InvalidDataException
from tigrqc.models import Project, db

from . import main_bp as main
from .forms import ProjectForm


def _get_projects() -> list[Project]:
    """Get a list of all projects currently in the database
    """
    statement = select(Project)
    return list(db.session.scalars(statement).all())


def _add_project(form: ProjectForm):
    """Add a new project.

    Args:
        form: A ProjectForm containing project details to add to the database.
    """
    project = Project()
    form.populate_obj(project)
    project.save()


def is_duplicate_project_exc(exc: InvalidDataException) -> bool:
    """Check if an exception was caused by a duplicate project ID.

    Args:
        exc: An InvalidDataException that has been caught.
    """
    return (
        'IntegrityError' in str(exc) and
        f'{Project.__tablename__}.id' in str(exc)
    )


@main.route('/')
@main.route('/index')
def index():
    """The main landing page.
    """
    projects = _get_projects()
    return render_template('index.html', projects=projects)


@main.route('/projects/new', methods=['GET', 'POST'])
def add_project():
    """Add a project to the database.
    """
    form = ProjectForm()

    if form.validate_on_submit():
        try:
            _add_project(form)
        except InvalidDataException as e:
            if is_duplicate_project_exc(e):
                # The user attempted to add a project with an already
                # in-use project ID. Warn them.
                flash(
                    'Project ID must be unique, ID already in use.',
                    'danger'
                )
            else:
                # Generic warning for other form/database issues.
                flash(
                    'Invalid project configuration. Please review contents.',
                    'danger'
                )
        else:
            # On success show updated project list. Otherwise fall through
            # and re-render 'add project' form (with flashed messages added)
            projects = _get_projects()
            return render_template(
                'partials/_project_list.html', projects=projects
            )

    return render_template('partials/_add_project.html', project_form=form)


@main.route('/projects/<string:project_id>')
def project_home(project_id=None):
    """View a project's home page.
    """
    # This is just a placeholder for now, so 'url_for' can be used in templates
    return redirect(url_for('main.index'))
