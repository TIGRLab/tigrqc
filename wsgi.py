#!/usr/bin/env python
"""Provide a callable to start the application.

This is needed by tools like uWSGI or Gunicorn to start the application in
production instances.

For dev instances you're better off just using this in the root folder:

    flask --app tigrqc run --debug
"""
from tigrqc import create_app

app = create_app()
