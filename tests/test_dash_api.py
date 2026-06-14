# -*- coding: utf-8 -*-
"""HTTP integration tests for dashboard API endpoints.

Uses Flask test client with mocked Redis backend.
Run with: pytest tests/test_dash_api.py -v

Requires: flask, flask-restful (pip install flask flask-restful)
If these are not installed, the tests will be skipped.
"""

import sys
import os
import json
import types
import pytest
from unittest import mock

# Try to import Flask; skip all tests if not available
flask = pytest.importorskip('flask')
flask_restful = pytest.importorskip('flask_restful')

from tests.conftest import get_mock_redis
from dashboard.server.resources.dash_store import (
    DashboardStore,
    DashboardNotFoundError,
    DashboardValidationError,
)


def _make_resource_classes(store, mock_config):
    """Build Resource subclasses bound to a specific store and config.

    This avoids import-time side effects from the real resource modules
    (which import Redis, MySQLdb, etc.).
    """
    from flask import render_template, make_response, request, redirect
    from flask_restful import Resource

    # Inline build_response / build_error_response
    def build_response(content, code=200):
        response = make_response(flask.jsonify(content), content['code'])
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    def build_error_response(message, http_code=400, data=None):
        return build_response(
            dict(data=data, code=http_code, message=message, status='error'),
            http_code
        )

    class Home(Resource):
        def get(self):
            return make_response(render_template('home.html', api_root=mock_config.app_host))

        def post(self):
            post_data = request.json
            name = ''
            author = ''
            if post_data:
                raw_name = post_data.get('name', '')
                raw_author = post_data.get('author', '')
                name = raw_name.strip() if isinstance(raw_name, str) else ''
                author = raw_author.strip() if isinstance(raw_author, str) else ''
            try:
                store.create(name, author)
            except DashboardValidationError as e:
                return build_error_response(str(e), 400)
            return redirect('/')

    class DashListData(Resource):
        def get(self, page=0, size=10):
            data = store.list_meta(page, size)
            return build_response(dict(data=data, code=200))

    class Dash(Resource):
        def get(self, dash_id):
            return make_response(render_template('dashboard.html',
                                                 dash_id=dash_id,
                                                 api_root=mock_config.app_host))

    class DashData(Resource):
        def get(self, dash_id):
            try:
                data = store.get_content(dash_id)
            except DashboardNotFoundError:
                return build_error_response('Dashboard not found', 404)
            return build_response(dict(data=data, code=200))

        def put(self, dash_id=0):
            data = request.get_json()
            if not data:
                return build_error_response('Empty request body', 400)
            try:
                updated = store.update(dash_id, data)
            except DashboardNotFoundError:
                return build_error_response('Dashboard not found', 404)
            except DashboardValidationError as e:
                return build_error_response(str(e), 400)
            return build_response(dict(data=updated, code=200))

        def delete(self, dash_id):
            try:
                removed_info = store.delete(dash_id)
            except DashboardNotFoundError:
                return build_error_response('Dashboard not found', 404)
            return {'removed_info': removed_info}

    return Home, DashListData, Dash, DashData


@pytest.fixture
def app_and_client():
    """Create a fresh Flask app with mock Redis for each test."""
    mock_r, mock_data = get_mock_redis()

    app = flask.Flask(__name__,
                      template_folder=os.path.join(
                          os.path.dirname(__file__), '..', 'dashboard', 'templates'),
                      static_folder=os.path.join(
                          os.path.dirname(__file__), '..', 'dashboard', 'static'))
    app.config['TESTING'] = True

    api = flask_restful.Api(app)

    mock_config = mock.MagicMock()
    mock_config.app_host = '127.0.0.1:9090'

    store = DashboardStore(redis_conn=mock_r)

    Home, DashListData, Dash, DashData = _make_resource_classes(store, mock_config)

    api.add_resource(Home, '/', '/dashes')
    api.add_resource(DashListData, '/data/dashes/')
    api.add_resource(Dash, '/dash/<string:dash_id>')
    api.add_resource(DashData, '/data/dash/<string:dash_id>')

    client = app.test_client()
    yield client, store, mock_data


def _create_dash(store, name='Test', author='Author'):
    dash_id, meta, content = store.create(name, author)
    return dash_id


class TestCreateDashboard(object):

    def test_create_success_redirects(self, app_and_client):
        client, store, _ = app_and_client
        resp = client.post('/',
                           data=json.dumps({'name': 'New Dash', 'author': 'Alice'}),
                           content_type='application/json')
        assert resp.status_code in (301, 302, 308)

    def test_create_empty_name_returns_400(self, app_and_client):
        client, store, _ = app_and_client
        resp = client.post('/',
                           data=json.dumps({'name': '', 'author': 'Alice'}),
                           content_type='application/json')
        assert resp.status_code == 400

    def test_create_whitespace_name_returns_400(self, app_and_client):
        client, store, _ = app_and_client
        resp = client.post('/',
                           data=json.dumps({'name': '   ', 'author': 'Alice'}),
                           content_type='application/json')
        assert resp.status_code == 400


class TestListDashboards(object):

    def test_list_empty(self, app_and_client):
        client, store, _ = app_and_client
        resp = client.get('/data/dashes/')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['data'] == []

    def test_list_after_create(self, app_and_client):
        client, store, _ = app_and_client
        _create_dash(store, 'Dash 1', 'Alice')
        _create_dash(store, 'Dash 2', 'Bob')
        resp = client.get('/data/dashes/')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data['data']) == 2


class TestReadDashboard(object):

    def test_read_existing(self, app_and_client):
        client, store, _ = app_and_client
        dash_id = _create_dash(store, 'Test', 'Alice')
        resp = client.get('/data/dash/{}'.format(dash_id))
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['data']['name'] == 'Test'
        assert 'grid' in data['data']

    def test_read_nonexistent_returns_404(self, app_and_client):
        client, store, _ = app_and_client
        resp = client.get('/data/dash/99999')
        assert resp.status_code == 404
        data = json.loads(resp.data)
        assert data['status'] == 'error'

    def test_read_invalid_id_returns_404(self, app_and_client):
        client, store, _ = app_and_client
        resp = client.get('/data/dash/not_a_number')
        assert resp.status_code == 404


class TestUpdateDashboard(object):

    def test_update_existing(self, app_and_client):
        client, store, _ = app_and_client
        dash_id = _create_dash(store, 'Original', 'Alice')
        resp = client.put('/data/dash/{}'.format(dash_id),
                          data=json.dumps({'name': 'Updated', 'grid': {}}),
                          content_type='application/json')
        assert resp.status_code == 200
        resp2 = client.get('/data/dash/{}'.format(dash_id))
        data = json.loads(resp2.data)
        assert data['data']['name'] == 'Updated'

    def test_update_nonexistent_returns_404(self, app_and_client):
        client, store, _ = app_and_client
        resp = client.put('/data/dash/99999',
                          data=json.dumps({'name': 'Test', 'grid': {}}),
                          content_type='application/json')
        assert resp.status_code == 404

    def test_update_empty_body_returns_400(self, app_and_client):
        client, store, _ = app_and_client
        dash_id = _create_dash(store, 'Test', 'Alice')
        resp = client.put('/data/dash/{}'.format(dash_id),
                          data='',
                          content_type='application/json')
        assert resp.status_code == 400


class TestDeleteDashboard(object):

    def test_delete_existing(self, app_and_client):
        client, store, _ = app_and_client
        dash_id = _create_dash(store, 'Test', 'Alice')
        resp = client.delete('/data/dash/{}'.format(dash_id))
        assert resp.status_code == 200
        assert 'removed_info' in json.loads(resp.data)
        resp2 = client.get('/data/dash/{}'.format(dash_id))
        assert resp2.status_code == 404

    def test_delete_nonexistent_returns_404(self, app_and_client):
        client, store, _ = app_and_client
        resp = client.delete('/data/dash/99999')
        assert resp.status_code == 404


class TestEndToEndFlows(object):

    def test_create_delete_create_no_id_collision(self, app_and_client):
        client, store, _ = app_and_client
        id1 = _create_dash(store, 'Dash 1', 'Alice')
        id2 = _create_dash(store, 'Dash 2', 'Bob')
        id3 = _create_dash(store, 'Dash 3', 'Charlie')

        client.delete('/data/dash/{}'.format(id2))

        id4 = _create_dash(store, 'Dash 4', 'Dave')

        assert len(set([id1, id2, id3, id4])) == 4
        assert client.get('/data/dash/{}'.format(id1)).status_code == 200
        assert client.get('/data/dash/{}'.format(id3)).status_code == 200
        assert client.get('/data/dash/{}'.format(id4)).status_code == 200
        assert client.get('/data/dash/{}'.format(id2)).status_code == 404

    def test_edit_old_after_creating_new(self, app_and_client):
        client, store, _ = app_and_client
        id1 = _create_dash(store, 'First', 'Alice')
        _create_dash(store, 'Second', 'Bob')
        _create_dash(store, 'Third', 'Charlie')

        resp = client.put('/data/dash/{}'.format(id1),
                          data=json.dumps({'name': 'First (edited)', 'grid': {}}),
                          content_type='application/json')
        assert resp.status_code == 200

        resp2 = client.get('/data/dash/{}'.format(id1))
        data = json.loads(resp2.data)
        assert data['data']['name'] == 'First (edited)'
