# -*- coding: utf-8 -*-
from __future__ import absolute_import

from flask import render_template, make_response, request, redirect
from flask.ext.restful import Resource

from dashboard import config
from ..utils import build_response
from ..store import DashboardStore
from ..models import ValidationError


_store = DashboardStore()


class Home(Resource):
    """Home page — renders the dashboard list template."""

    def get(self):
        return make_response(
            render_template('home.html', api_root=config.app_host))

    def post(self):
        post_data = request.get_json(silent=True)
        if not post_data:
            return build_response(dict(data=None, code=400,
                                       message="Invalid JSON body"))

        name = (post_data.get('name') or '').strip()
        author = (post_data.get('author') or '').strip()

        if not name:
            return build_response(dict(data=None, code=400,
                                       message="Name is required"))
        if not author:
            return build_response(dict(data=None, code=400,
                                       message="Author is required"))

        try:
            _store.create(name, author)
        except ValidationError as e:
            return build_response(dict(data=None, code=400,
                                       message=e.message))

        return redirect('/')


class DashListData(Resource):
    """JSON API that returns paginated dashboard metadata.

    DB structure (for reference — all access goes through DashboardStore):
      1. DASH_ID_KEY   -> Sorted Set : dash_id scored by time_modified
      2. DASH_META_KEY -> Hash : dash_id -> JSON meta
      3. DASH_CONTENT_KEY -> Hash : dash_id -> JSON content
    """

    def get(self, page=0, size=10):
        data = _store.list_dashboards(page, size)
        return build_response(dict(data=data, code=200))
