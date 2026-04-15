"""Core application views (project listing, creation, etc.)
"""
from flask import redirect, render_template, url_for
from sqlalchemy import select

from tigrqc.models import Project, db

from . import main_bp as main
from .forms import ProjectForm


@main.route('/')
@main.route('/index')
def index():
    """The main landing page.
    """
    statement = select(Project)
    projects = db.session.scalars(statement).all()

    if projects:
        return render_template('index.html', projects=projects)

    # No projects found, so show form to make one.
    form = ProjectForm()
    return render_template('new_project.html', project_form=form)


@main.route('/projects/create', methods=['GET', 'POST'])
def create_project():
    """Add a project to the database.
    """
    form = ProjectForm()

    if form.validate_on_submit():
        project = Project()
        form.populate_obj(project)
        project.save()

        statement = select(Project)
        projects = db.session.scalars(statement).all()
        return render_template('project_list.html', projects=projects)

    return render_template('new_project.html', project_form=form)


@main.route('/projects/<string:project_id>')
def project_home(project_id=None):
    """View a project's home page.
    """
    # This is just a placeholder for now, so 'url_for' can be used in templates
    return redirect(url_for('main.index'))
