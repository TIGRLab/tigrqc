"""Core application views (project listing, creation, etc.)
"""
from collections.abc import Sequence
from typing import TYPE_CHECKING

from flask import flash, redirect, render_template, url_for
from flask_login import fresh_login_required
from sqlalchemy import select

from tigrqc.access import global_admin_required
from tigrqc.exceptions import InvalidDataException, UserException
from tigrqc.models import Project, ProjectSite, Site, db

from . import main_bp as main
from .forms import ProjectForm, SiteForm

if TYPE_CHECKING:
    from flask_sqlalchemy.model import Model
else:
    Model = db.Model


def _get_records(
        table: Model,
        subset: list[str] | None = None,
        sort: bool = False
) -> Sequence[Model]:
    """Get all (or a subset) of records from the given table.

    Args:
        table: The table to pull data from.
        subset: A list of IDs from the table to restrict results to. Optional,
            if omitted all records will be returned.
        sort: Whether to sort the output by the ID column. Default False.
    """
    statement = select(table)
    if subset:
        statement = statement.where(table.id.in_(subset))
    if sort:
        statement = statement.order_by(table.id)
    return db.session.scalars(statement).all()


def _add_project(form: ProjectForm):
    """Add a new project.

    Args:
        form: A ProjectForm containing project details to add to the database.
    """
    project = Project()
    chosen_sites = _get_records(Site, form.sites.data)
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
    projects = _get_records(Project, sort=True)
    return render_template('index.html', projects=projects)


@main.route('/projects/new', methods=['GET', 'POST'])
def add_project():
    """Add a project to the database.
    """
    project_form = ProjectForm()
    sites = _get_records(Site, sort=True)

    # Template doesn't use project_form.sites, but it must still be
    # populated or validation fails when this route receives a post
    project_form.sites.choices = [
        (site.id, site.label)
        for site in sites
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
        projects = _get_records(Project, sort=True)
        return render_template(
            'partials/_project_list.html', projects=projects
        )

    return render_template(
        'partials/_add_project.html',
        project_form=project_form,
        sites=sites
    )


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
        sites = _get_records(Site, sort=True)
        return render_template('partials/_select_site.html', sites=sites)

    return render_template('partials/_add_site.html', site_form=site_form)


@main.route('/sites/add-site/cancel', methods=['GET'])
def add_site_cancel():
    """Re-render the list of scan sites for the 'add project' form.
    """
    sites = _get_records(Site, sort=True)
    return render_template('partials/_select_site.html', sites=sites)


@main.route('/projects/<string:project_id>')
def project_home(project_id: str = ''):
    """View a project's home page.
    """
    project = Project.query.get_or_404(project_id)
    return render_template('project.html', project=project)


@main.route('/projects/<string:project_id>/settings')
@global_admin_required
@fresh_login_required
def project_settings(project_id: str = ''):
    """View or modify a project's settings.
    """
    project = Project.query.get_or_404(project_id)
    return render_template('project_settings.html', project=project)


@main.route('/projects/<string:project_id>/delete', methods=['POST'])
@global_admin_required
@fresh_login_required
def delete_project(project_id: str = ''):
    """Delete a project and all of its contents from the database.
    """
    project = Project.query.get_or_404(project_id)
    project.delete()
    flash(f'{project.id} successfully deleted.', 'success')
    return redirect(url_for('main.index'))
