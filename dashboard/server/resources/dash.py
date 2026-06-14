# -*- coding: utf-8 -*-

# built-in package
import time
import json
import random
import hashlib

# third-party package
from flask import request, make_response, render_template, redirect
try:
    from flask.ext.restful import Resource
except ImportError:
    from flask_restful import Resource

# user-defined package
from dashboard import r_db, config
from ..utils import build_response, build_error_response, print_info
from .dash_store import DashboardStore, DashboardValidationError, DashboardNotFoundError


# Module-level store singleton
_store = None


def get_store():
    """Return (and lazily create) the module-level DashboardStore instance."""
    global _store
    if _store is None:
        _store = DashboardStore()
    return _store


class Dash(Resource):
    """Dashboard html render.

    return the dashboard id, let js do the other work.

    Attributes:
    """
    def get(self, dash_id):
        """Just return the dashboard id in the rendering html.

        JS will do other work [ajax and rendering] according to the dash_id.

        Args:
            dash_id: dashboard id.

        Returns:
            rendered html.
        """
        return make_response(render_template('dashboard.html', dash_id=dash_id, api_root=config.app_host))


class DashData(Resource):
    """Dashboard meta/content CRUD operation.

    All read/write operations go through DashboardStore for consistent
    storage semantics, input validation, and error handling.

    Attributes:
    """
    def get(self, dash_id):
        """Read dashboard content.

        Args:
            dash_id: dashboard id.

        Returns:
            A dict containing the content of that dashboard, not include the meta info.
            Returns 404 error response if the dashboard does not exist.
        """
        try:
            data = get_store().get_content(dash_id)
        except DashboardNotFoundError:
            return build_error_response('Dashboard not found', 404)
        return build_response(dict(data=data, code=200))

    def put(self, dash_id=0):
        """Update a dash meta and content, return updated dash content.

        Args:
            dash_id: dashboard id.

        Returns:
            A dict containing the updated content of that dashboard, not include the meta info.
            Returns 404 if dashboard does not exist, 400 if validation fails.
        """
        data = request.get_json()
        if not data:
            return build_error_response('Empty request body', 400)
        try:
            updated = get_store().update(dash_id, data)
        except DashboardNotFoundError:
            return build_error_response('Dashboard not found', 404)
        except DashboardValidationError as e:
            return build_error_response(str(e), 400)
        return build_response(dict(data=updated, code=200))

    def delete(self, dash_id):
        """Delete a dash meta and content, return removed info.

        Args:
            dash_id: dashboard id.

        Returns:
            A dict containing info about the removed record.
            Returns 404 if dashboard does not exist.
        """
        try:
            removed_info = get_store().delete(dash_id)
        except DashboardNotFoundError:
            return build_error_response('Dashboard not found', 404)
        return {'removed_info': removed_info}
