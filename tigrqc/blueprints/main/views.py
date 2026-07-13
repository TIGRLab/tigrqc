"""Core application views (project listing, creation, etc.)
"""
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from flask import (abort, current_app, flash, jsonify, redirect,
                   render_template, request, url_for)
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


def _find_root(given_path: str | Path) -> Path:
    """Find the whitelisted dir that contains the user path or raise 403 code.
    """
    user_path = Path(given_path).resolve()

    for root in current_app.config['DATA_DIRS']:
        if user_path.is_relative_to(root):
            return root

    abort(403, 'Invalid path given')


def is_safe_path(given_path: str | Path) -> bool:
    """Check if a given path is within a whitelisted DATA_DIR directory.
    """
    given_path = Path(given_path).resolve()
    return any(
        given_path.is_relative_to(root)
        for root in current_app.config['DATA_DIRS']
    )


@main.route('/')
def index():
    """The main landing page.
    """
    projects = _get_records(Project, sort=True)
    return render_template('index.html', projects=projects)


@main.route('/projects/new', methods=['GET', 'POST'])
@global_admin_required
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
@global_admin_required
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
@global_admin_required
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


@main.route('/data/contents')
@global_admin_required
def list_data_dirs():
    """Return the configured data directories.
    """
    result = {str(item): str(item) for item in current_app.config['DATA_DIRS']}
    return render_template('partials/_dir_list.html', items=result)


@main.route('/data/contents/list')
@global_admin_required
def list_data_subdirs():
    """Return sub-directories of a whitelisted directory or raise 403.

    This will return a mapping of subdir folder names to their full paths for
    every subdir contained within a whitelisted directory (or any of its
    descendents).

    Raises 403 if the given directory is not within the whitelisted DATA_DIRS.
    """
    full_path = Path(request.args.get('path')).resolve()

    # print(f'Received path: {data_path}')
    print(f'Path object: {full_path}')
    # Raises 403 if no valid whitelisted directory root can be found
    _find_root(full_path)

    subdirs = {
        item.name: str(item)
        for item in full_path.iterdir()
        if item.is_dir() and is_safe_path(item)
    }

    return render_template('partials/_dir_list.html', items=subdirs)


@main.route('/file_browser')
def file_browser():
    result = {str(item): str(item) for item in current_app.config['DATA_DIRS']}
    return render_template('partials/_choose_dir.html', items=result)


@main.route('/select/dir', methods=['POST'])
def select_path():
    selected = request.args.get('path')
    print(request.args)
    print(f'This path was chosen: {selected}')
    return redirect(url_for('main.index'))
