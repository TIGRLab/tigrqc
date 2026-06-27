"""Core application views (project listing, creation, etc.)
"""
from collections.abc import Sequence
from typing import TYPE_CHECKING

from flask import render_template
from sqlalchemy import select

from tigrqc.exceptions import InvalidDataException, UserException
from tigrqc.models import Project, ProjectSite, Site, db

from . import main_bp as main
from .forms import ProjectForm, SiteForm

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model
else:
    Model = db.Model


def _get_projects(projects: list[str] | None = None) -> Sequence[Project]:
    """Get projects currently in the database.

    Args:
        projects: A list of project IDs to retrieve records for. Optional,
            if omitted all projects will be returned.
    """
    statement = select(Project)
    if projects:
        statement = statement.where(Project.id.in_(projects))
    return db.session.scalars(statement).all()


def _get_sites(sites: list[str] | None = None) -> Sequence[Site]:
    """Get scan sites currently in the database.

    Args:
        sites: A list of site IDs to retrieve records for. Optional, if
            omitted all sites will be returned.
    """
    statement = select(Site)
    if sites:
        statement = statement.where(Site.id.in_(sites))
    return db.session.scalars(statement).all()


def _add_project(form: ProjectForm):
    """Add a new project.

    Args:
        form: A ProjectForm containing project details to add to the database.
    """
    project = Project()
    chosen_sites = _get_sites(form.sites.data)
    form.sites.data = {}
    form.populate_obj(project)
    project.sites = {
        site.id: ProjectSite(
            project_id=project.id, site_id=site.id
        )  # type: ignore[call-arg]
        for site in chosen_sites
    }
    project.save()


def is_duplicate_id(exc: InvalidDataException, table: Model) -> bool:
    """Check if an exception was caused by a duplicate ID for a record.

    Args:
        exc: An InvalidDataException that has been caught.
        table: The table that the record was to be added to.
    """
    return (
        'IntegrityError' in str(exc) and
        f'{table.__tablename__}.id' in str(exc)   # type: ignore[attr-defined]
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
    project_form = ProjectForm()
    sites = _get_sites()

    # Template doesn't use project_form.sites, but it must still be
    # populated or validation fails when this route receives a post
    project_form.sites.choices = [
        (site.id, site.label)
        for site in _get_sites()
    ]

    if project_form.validate_on_submit():
        try:
            _add_project(project_form)
        except InvalidDataException as e:
            if is_duplicate_id(e, Project):
                # The user attempted to add a project with an already
                # in-use project ID. Warn them.
                raise UserException(
                    'Project ID must be unique, ID already in use.',
                    'danger'
                ) from e
            # Generic warning for other form/database issues.
            raise UserException(
                'Invalid project configuration. Please review contents.',
                'danger'
            ) from e
        projects = _get_projects()
        return render_template(
            'partials/_project_list.html', projects=projects
        )

    return render_template(
        'partials/_add_project.html',
        project_form=project_form,
        sites=sites
    )


@main.route('/projects/<string:project_id>')
def project_home(project_id=None):
    """View a project's home page.
    """
    project = _get_projects([project_id])
    if len(project) != 1:
        raise InvalidDataException(f'Project {project_id} not found')
    project = project[0]
    return render_template('project.html', project=project)


@main.route('/sites/add-site', methods=['GET', 'POST'])
def add_site():
    """Add a new scan site.
    """
    site_form = SiteForm()

    if site_form.validate_on_submit():
        site = Site()
        site_form.populate_obj(site)
        try:
            site.save()
        except InvalidDataException as e:
            if is_duplicate_id(e, Site):
                raise UserException(
                    'Duplicated site ID. Please enter a unique ID',
                    'danger'
                ) from e
            raise UserException(
                'Invalid site ID or invalid form contents.',
                'danger'
            ) from e
        # Site has been added, so re-display the original list with
        # the new site in it.
        sites = _get_sites()
        return render_template('partials/_select_site.html', sites=sites)

    return render_template('partials/_add_site.html', site_form=site_form)


@main.route('/sites/add-site/cancel', methods=['GET'])
def add_site_cancel():
    """Re-render the list of scan sites for the 'add project' form.
    """
    sites = _get_sites()
    return render_template('partials/_select_site.html', sites=sites)
