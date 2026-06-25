"""Core application views (project listing, creation, etc.)
"""
from collections.abc import Sequence

from flask import redirect, render_template, url_for
from sqlalchemy import select

from tigrqc.exceptions import InvalidDataException, UserException
from tigrqc.models import Project, ProjectSite, Site, db

from . import main_bp as main
from .forms import ProjectForm, SiteForm


def _get_projects() -> Sequence[Project]:
    """Get all projects currently in the database.
    """
    statement = select(Project)
    return db.session.scalars(statement).all()


def _get_sites(sites: list = None) -> Sequence[Site]:
    """Get all scan sites currently in the database.

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
        site.id: ProjectSite(project_id=project.id, site_id=site.id)
        for site in chosen_sites
    }
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


def is_duplicate_site_exc(exc: InvalidDataException) -> bool:
    """Check if an exception was caused by a duplicated site ID.

    Args:
        exc: An InvalidDataException that has been caught.
    """
    return (
        'IntegrityError' in str(exc) and
        f'{Site.__tablename__}.id' in str(exc)
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
            if is_duplicate_project_exc(e):
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
    # This is just a placeholder for now, so 'url_for' can be used in templates
    return redirect(url_for('main.index'))


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
            if is_duplicate_site_exc(e):
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
