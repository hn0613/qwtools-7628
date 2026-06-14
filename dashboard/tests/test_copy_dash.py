# -*- coding: utf-8 -*-

"""
Tests for the dashboard copy (duplicate) functionality.

Covers:
1. Normal copy — creates a new dashboard with correct name and content
2. Independence — editing the copy does not affect the original
3. Error tolerance — missing data sources are sanitized during copy
4. 404 handling — copying a non-existent dashboard returns 404
5. List identification — copied dashboard meta includes 'copied_from' field

Run with: nosetests dashboard/tests/test_copy_dash.py
"""

# built-in package
import json
import time

# user-defined package
from .. import r_kv, r_db, config
from dashboard.server.resources import home
from dashboard.server.resources import dash


def _setup():
    """Create helper instances."""
    home_resource = home.Home()
    dash_resource = dash.DashData()
    copy_resource = dash.DashCopy()
    return home_resource, dash_resource, copy_resource


def _cleanup_dash(dash_id):
    """Remove a dashboard from Redis (cleanup helper)."""
    r_db.zrem(config.DASH_ID_KEY, dash_id)
    r_db.hdel(config.DASH_META_KEY, dash_id)
    r_db.hdel(config.DASH_CONTENT_KEY, dash_id)


def test_normal_copy():
    """Copy an existing dashboard and verify the new one has correct name, content and different id."""
    home_res, dash_res, copy_res = _setup()

    # Create source dashboard
    src_id, src_meta, src_content = home_res._create_dash("Test Dashboard", "tester")

    try:
        # Copy it
        result = copy_res.post(src_id)
        # Result is a Flask response tuple; extract data
        copy_data = result[0] if isinstance(result, tuple) else result
        if hasattr(copy_data, 'get_data'):
            copy_data = json.loads(copy_data.get_data())
        elif isinstance(copy_data, dict) and 'data' in copy_data:
            copy_data = copy_data

        new_id = copy_data['data']['id']
        new_name = copy_data['data']['name']

        # Verify name has "(副本)" suffix
        assert u"(副本)" in new_name, "Copy name should contain '(副本)', got: {}".format(new_name)
        assert new_name == "Test Dashboard (副本)", "Expected 'Test Dashboard (副本)', got: {}".format(new_name)

        # Verify different id
        assert new_id != src_id, "Copy should have a different id from source"

        # Verify content structure is preserved (grid exists)
        new_meta_raw = r_db.hget(config.DASH_META_KEY, new_id)
        assert new_meta_raw is not None, "Copied dashboard meta should exist in Redis"
        new_meta = json.loads(new_meta_raw)
        assert new_meta['name'] == new_name
        assert new_meta['author'] == "tester"

        new_content_raw = r_db.hget(config.DASH_CONTENT_KEY, new_id)
        assert new_content_raw is not None, "Copied dashboard content should exist in Redis"
        new_content = json.loads(new_content_raw)
        assert 'grid' in new_content, "Copied content should have 'grid' key"
        assert new_content['id'] == new_id

        # Cleanup
        _cleanup_dash(new_id)
    finally:
        _cleanup_dash(src_id)


def test_copy_independence():
    """After copying, modifying the copy should not affect the original."""
    home_res, dash_res, copy_res = _setup()

    # Create source dashboard
    src_id, src_meta, src_content = home_res._create_dash("Independence Test", "tester")

    try:
        # Copy it
        result = copy_res.post(src_id)
        copy_data = result[0] if isinstance(result, tuple) else result
        if hasattr(copy_data, 'get_data'):
            copy_data = json.loads(copy_data.get_data())
        new_id = copy_data['data']['id']

        # Modify the copy's content
        new_data = {
            "name": "Modified Copy",
            "grid": {"0": {"id": "0", "key": "none", "type": "none",
                           "option": {"x": [], "y": []},
                           "x": 0, "y": 0, "width": 6, "height": 5,
                           "graph_name": "modified graph"}}
        }
        dash_res._update_dash(new_id, new_data)

        # Verify original is unchanged
        orig_meta_raw = r_db.hget(config.DASH_META_KEY, src_id)
        orig_meta = json.loads(orig_meta_raw)
        assert orig_meta['name'] == "Independence Test", \
            "Original name should be unchanged, got: {}".format(orig_meta['name'])

        orig_content_raw = r_db.hget(config.DASH_CONTENT_KEY, src_id)
        orig_content = json.loads(orig_content_raw)
        assert orig_content.get('name') != "Modified Copy", \
            "Original content should not be affected by copy modification"

        # Cleanup
        _cleanup_dash(new_id)
    finally:
        _cleanup_dash(src_id)


def test_copy_with_missing_data_source():
    """Copying a dashboard whose widgets reference non-existent keys should succeed,
    with those widgets reset to 'none'."""
    home_res, dash_res, copy_res = _setup()

    # Create source dashboard
    src_id, src_meta, src_content = home_res._create_dash("Missing Data Test", "tester")

    try:
        # Modify source to have a widget referencing a non-existent key
        data_with_bad_key = {
            "name": "Missing Data Test",
            "grid": {
                "0": {"id": "0", "key": "nonexistent_key_12345", "type": "bar",
                       "option": {"x": ["col1"], "y": ["col2"]},
                       "x": 0, "y": 0, "width": 6, "height": 5,
                       "graph_name": "bad key graph"},
                "1": {"id": "1", "key": "none", "type": "none",
                       "option": {"x": [], "y": []},
                       "x": 6, "y": 0, "width": 6, "height": 5,
                       "graph_name": "empty graph"},
            }
        }
        dash_res._update_dash(src_id, data_with_bad_key)

        # Copy should succeed
        result = copy_res.post(src_id)
        copy_data = result[0] if isinstance(result, tuple) else result
        if hasattr(copy_data, 'get_data'):
            copy_data = json.loads(copy_data.get_data())
        new_id = copy_data['data']['id']

        # Verify the bad key widget was reset
        new_content_raw = r_db.hget(config.DASH_CONTENT_KEY, new_id)
        new_content = json.loads(new_content_raw)
        widget_0 = new_content['grid']['0']
        assert widget_0['key'] == 'none', \
            "Widget with missing key should be reset to 'none', got: {}".format(widget_0['key'])
        assert widget_0['type'] == 'none', \
            "Widget with missing key should have type reset to 'none', got: {}".format(widget_0['type'])
        assert widget_0['option'] == {"x": [], "y": []}, \
            "Widget with missing key should have option cleared"

        # Widget 1 should be unchanged (already 'none')
        widget_1 = new_content['grid']['1']
        assert widget_1['key'] == 'none'

        # Cleanup
        _cleanup_dash(new_id)
    finally:
        _cleanup_dash(src_id)


def test_copy_nonexistent_dashboard():
    """Copying a dashboard that doesn't exist should return 404."""
    home_res, dash_res, copy_res = _setup()

    # Use a very high ID that shouldn't exist
    result = copy_res.post("999999")

    # Should be a tuple (response, status_code)
    assert isinstance(result, tuple), "Expected tuple response for 404"
    assert result[1] == 404, "Expected 404 status code, got: {}".format(result[1])


def test_copy_meta_has_copied_from():
    """Copied dashboard's meta should include the 'copied_from' field."""
    home_res, dash_res, copy_res = _setup()

    # Create source dashboard
    src_id, src_meta, src_content = home_res._create_dash("Copy From Test", "tester")

    try:
        # Copy it
        result = copy_res.post(src_id)
        copy_data = result[0] if isinstance(result, tuple) else result
        if hasattr(copy_data, 'get_data'):
            copy_data = json.loads(copy_data.get_data())
        new_id = copy_data['data']['id']

        # Verify meta has copied_from
        new_meta_raw = r_db.hget(config.DASH_META_KEY, new_id)
        new_meta = json.loads(new_meta_raw)
        assert 'copied_from' in new_meta, "Copied dashboard meta should have 'copied_from' field"
        assert new_meta['copied_from'] == int(src_id), \
            "copied_from should be source id {}, got {}".format(src_id, new_meta['copied_from'])

        # Cleanup
        _cleanup_dash(new_id)
    finally:
        _cleanup_dash(src_id)
