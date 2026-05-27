"""Core application views (project listing, creation, etc.)
"""
from collections.abc import Sequence

from flask import flash, redirect, render_template, url_for
from sqlalchemy import select

from tigrqc.exceptions import InvalidDataException
from tigrqc.models import Project, Site, db

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
    form.populate_obj(project)
    project.scans = _get_sites(form.sites.data)
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

    # Todo:
    #   - Implement the 'cancel' button for the subform. Must 'post' here
    #     with flag so db update / form validate is skipped
    #   - Implement the saving/restoring of any selected sites that may have
    #     been selected by the user before hitting the 'add site' button

    site_form = SiteForm()

    if site_form.validate_on_submit():
        site = Site()
        site_form.populate_obj(site)
        try:
            site.save()
        except InvalidDataException as e:
            flash('Invalid site ID or invalid form contents.', 'danger')
        else:
            sites = _get_sites()
            # Site has been added, so re-display the original list with
            # the new site in it.
            return render_template('partials/_select_site.html', sites=sites)

    return render_template('partials/_add_site.html', site_form=site_form)
