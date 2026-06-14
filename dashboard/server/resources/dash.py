# -*- coding: utf-8 -*-
from __future__ import absolute_import

from flask import request, make_response, render_template
from flask.ext.restful import Resource

from dashboard import config
from ..utils import build_response
from ..store import DashboardStore
from ..models import ValidationError


_store = DashboardStore()


class Dash(Resource):
    """Dashboard detail page renderer.

    Checks that the dashboard exists before rendering.  Returns a 404
    response for unknown *dash_id* values so the browser does not load
    a page that will immediately break on the subsequent AJAX call.
    """

    def get(self, dash_id):
        if not _store.exists(dash_id):
            return build_response(dict(data=None, code=404,
                                       message="Dashboard not found"))
        return make_response(
            render_template('dashboard.html',
                            dash_id=dash_id,
                            api_root=config.app_host))


class DashData(Resource):
    """Dashboard content CRUD via JSON API."""

    def get(self, dash_id):
        content = _store.get_content(dash_id)
        if content is None:
            return build_response(dict(data=None, code=404,
                                       message="Dashboard not found"))
        return build_response(dict(data=content, code=200))

    def put(self, dash_id=0):
        data = request.get_json(silent=True)
        if not data:
            return build_response(dict(data=None, code=400,
                                       message="Invalid JSON body"))
        try:
            updated = _store.update(dash_id, data)
        except ValidationError as e:
            return build_response(dict(data=None, code=400,
                                       message=e.message))

        if updated is None:
            return build_response(dict(data=None, code=404,
                                       message="Dashboard not found"))
        return build_response(dict(data=updated, code=200))

    def delete(self, dash_id):
        removed = _store.delete(dash_id)
        if removed is None:
            return build_response(dict(data=None, code=404,
                                       message="Dashboard not found"))
        return build_response(dict(data=removed, code=200))
