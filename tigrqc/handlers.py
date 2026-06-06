"""Manages error handlers for the application.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from flask import flash, render_template, request
from flask_login import current_user

if TYPE_CHECKING:
    from flask import Flask
    from flask.typing import ResponseReturnValue
    from werkzeug.exceptions import Forbidden, NotFound

logger = logging.getLogger(__name__)


def default_error_handler(_error: Exception) -> ResponseReturnValue:
    """Handle 'Exception' if not matched by any more specific handler.
    """
    logger.exception('Unhandled exception occurred.')

    if request.headers.get('HX-Request'):
        flash(
            'Something has gone wrong. Please contact an administrator.',
            'danger'
        )
        # HTMX ignores 4xx/5xx codes so must use 2XX code for flash to work.
        return (
            render_template('partials/_flash.html'),
            200,
            {
                'HX-Retarget': '#alerts',
                'HX-Reswap': 'innerHTML',
                'Content-Type': 'text/html',
            },
        )

    return render_template('500.html'), 500


def handle_404(_error: NotFound) -> ResponseReturnValue:
    """Handle '404' exceptions.
    """
    logger.debug('404: %s', request.path)
    return render_template('404.html'), 404


def handle_403(_error: Forbidden) -> ResponseReturnValue:
    """Handle exceptions from logged-in users with insufficient permissions.
    """
    logger.debug(
        '403: User %s blocked from attempting admin action',
        current_user.id
    )
    return render_template('403.html'), 403


def register_error_handlers(app: Flask) -> Flask:
    """Register error handlers for an application instance.
    """
    app.register_error_handler(
        Exception,
        default_error_handler,
    )
    app.register_error_handler(404, handle_404)
    app.register_error_handler(403, handle_403)
    return app
