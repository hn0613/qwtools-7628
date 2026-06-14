# -*- coding: utf-8 -*-

"""Test route for the DashTable JS test page."""

from flask.ext.restful import Resource
from flask import make_response, render_template
from dashboard import config


class TestTable(Resource):
    """Render the DashTable unit-test page."""
    def get(self):
        return make_response(render_template('test_table.html', api_root=config.app_host))
