"""Views for admins to configure the app + users.
"""
from flask import render_template

from . import settings_bp as settings


@settings.route('/')
def settings_home():
    """The main landing page for the admin settings page(s).
    """
    return render_template('settings_home.html')
