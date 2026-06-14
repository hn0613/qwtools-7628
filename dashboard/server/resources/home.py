# -*- coding: utf-8 -*-

# built-in package
import json

# third-party package
from flask import render_template, make_response, request, redirect
try:
    from flask.ext.restful import Resource
except ImportError:
    from flask_restful import Resource

# user-defined package
from dashboard import config
from ..utils import build_response, build_error_response
from .dash_store import DashboardStore, DashboardValidationError, DashboardNotFoundError


# Module-level store singleton
_store = None


def get_store():
    """Return (and lazily create) the module-level DashboardStore instance."""
    global _store
    if _store is None:
        _store = DashboardStore()
    return _store


class Home(Resource):
    """home page

    Just render the home template, and then js will fetch data from server
    to build the list or other things.

    Attributes:
    """
    def get(self):
        return make_response(render_template('home.html', api_root=config.app_host))

    def post(self):
        post_data = request.json
        name = ''
        author = ''
        if post_data:
            raw_name = post_data.get('name', '')
            raw_author = post_data.get('author', '')
            name = raw_name.strip() if isinstance(raw_name, basestring) else ''
            author = raw_author.strip() if isinstance(raw_author, basestring) else ''
        try:
            get_store().create(name, author)
        except DashboardValidationError as e:
            return build_error_response(str(e), 400)
        return redirect('/')


class DashListData(Resource):
    """Get dashboard list.

    Get the dashboard list with meta information, which is used for rendering
    kinds of `current dashboard list` page.

    DB structure:
    1. DASH_ID_KEY -> Sorted Set : time_modified -> dash_id
    2. DASH_META_KEY -> hash : dash_id -> dash meta info
    3. DASH_CONTENT_KEY -> hash : dash_id -> dash content info [ like ipydb format ]

    Attributes:
    """
    def get(self, page=0, size=10):
        """Get dashboard meta info from in page `page` and page size is `size`.

        Args:
            page: page number.
            size: size number.

        Returns:
            list of dict containing the dash_id and accordingly meta info.
            maybe empty list [] when page * size > total dashes in db. that's reasonable.
        """
        data = get_store().list_meta(page, size)
        return build_response(dict(data=data, code=200))
