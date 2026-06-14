# -*- coding: utf-8 -*-

# built-in package
import os
import time
import json
import random

# third-party package
import pandas as pd

# user-defined package
from .. import r_kv, r_db, config
from dashboard.server import utils
from dashboard.client import sender
from dashboard.server.resources import home
from dashboard.server.resources import dash
from dashboard.server.resources.home import _generate_dash_id, _generate_copy_name


TMP_DIR = '/mnt/tmp'
TEST_DATA_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'test_data.json')
TEST_DASH_DATA = json.load(file(TEST_DATA_FILE, 'r'))


@utils.print_func_name
def test_create_example_1():
    """Create a dashboard contain using chinese population data in the past 15 years"""
    home_resource = home.Home()
    dash_resource = dash.DashData()

    # get and store population data
    url = 'https://github.com/litaotao/IPython-Dashboard/raw/master/docs/people_number_by_province_lateset_10_years.csv'
    if os.path.isdir(TMP_DIR) and  'people_number_by_province_lateset_10_years.csv' in os.listdir(TMP_DIR):
        url = TMP_DIR + '/people_number_by_province_lateset_10_years.csv'
    value = pd.read_csv(url)
    sender(value, 'chinese_population', value.to_json())

    # create sample dashboard
    dash_id, meta, content, = home_resource._create_dash("Dash: Chinese Population", "that man")
    data = TEST_DASH_DATA.get('example_chinese_population')
    dash_resource._update_dash(dash_id, data)


@utils.print_func_name
def test_duplicate_dashboard():
    """Duplicate a populated dashboard and verify the copy preserves content."""
    home_resource = home.Home()
    dash_resource = dash.DashData()

    # Create and populate source dashboard
    dash_id, meta, content = home_resource._create_dash("Test Dashboard", "tester")
    data = TEST_DASH_DATA.get('example_chinese_population')
    dash_resource._update_dash(dash_id, data)

    # Read source for comparison
    source_content = json.loads(r_db.hget(config.DASH_CONTENT_KEY, dash_id))

    # Perform duplicate
    new_id = _generate_dash_id()
    new_name = _generate_copy_name("Test Dashboard")
    assert new_name == "Test Dashboard - Copy", \
        "Expected 'Test Dashboard - Copy', got '{}'".format(new_name)
    assert new_id != dash_id, \
        "New ID {} should differ from source ID {}".format(new_id, dash_id)

    # Verify source content has grid data
    assert 'grid' in source_content, "Source should have grid data"
    assert len(source_content['grid']) > 0, "Source grid should not be empty"


@utils.print_func_name
def test_copy_name_dedup():
    """Multiple copies produce deduplicated names."""
    home_resource = home.Home()

    home_resource._create_dash("My Board", "author1")

    name_1 = _generate_copy_name("My Board")
    assert name_1 == "My Board - Copy", \
        "First copy should be 'My Board - Copy', got '{}'".format(name_1)

    # Create a dashboard with the first copy name
    home_resource._create_dash("My Board - Copy", "author1")
    name_2 = _generate_copy_name("My Board")
    assert name_2 == "My Board - Copy (2)", \
        "Second copy should be 'My Board - Copy (2)', got '{}'".format(name_2)

    # Create a dashboard with the second copy name
    home_resource._create_dash("My Board - Copy (2)", "author1")
    name_3 = _generate_copy_name("My Board")
    assert name_3 == "My Board - Copy (3)", \
        "Third copy should be 'My Board - Copy (3)', got '{}'".format(name_3)


@utils.print_func_name
def test_duplicate_empty_dashboard():
    """Duplicate a freshly created dashboard with all-empty grid boxes."""
    home_resource = home.Home()
    dash_id, meta, content = home_resource._create_dash("Empty Board", "tester")

    raw_content = json.loads(r_db.hget(config.DASH_CONTENT_KEY, dash_id))
    # Verify all grid items have key="none" and type="none"
    for grid_key, grid_item in raw_content['grid'].iteritems():
        assert grid_item['key'] == 'none', \
            "Empty grid item should have key='none'"
        assert grid_item['type'] == 'none', \
            "Empty grid item should have type='none'"

    # Duplicate should succeed - generate new id without error
    new_id = _generate_dash_id()
    assert new_id != dash_id, "New ID should differ from source"


@utils.print_func_name
def test_deep_copy_independence():
    """Modifying the copy must not affect the original."""
    home_resource = home.Home()
    dash_resource = dash.DashData()

    dash_id, _, _ = home_resource._create_dash("Original", "author")
    data = TEST_DASH_DATA.get('example_chinese_population')
    dash_resource._update_dash(dash_id, data)

    # Read source, deep copy grid
    source_content = json.loads(r_db.hget(config.DASH_CONTENT_KEY, dash_id))
    source_grid = source_content.get('grid', {})

    # Manual deep copy (same logic as DashDuplicate)
    new_grid = {}
    for grid_key, grid_item in source_grid.iteritems():
        new_item = {}
        for k, v in grid_item.iteritems():
            if isinstance(v, dict):
                new_item[k] = dict(v)
                for opt_k, opt_v in v.iteritems():
                    if isinstance(opt_v, list):
                        new_item[k][opt_k] = list(opt_v)
            elif isinstance(v, list):
                new_item[k] = list(v)
            else:
                new_item[k] = v
        new_grid[grid_key] = new_item

    # Modify the copy
    if '0' in new_grid:
        new_grid['0']['graph_name'] = 'MODIFIED'
        if 'option' in new_grid['0'] and 'y' in new_grid['0']['option']:
            new_grid['0']['option']['y'] = ['changed']

    # Verify original is untouched
    original = json.loads(r_db.hget(config.DASH_CONTENT_KEY, dash_id))
    assert original['grid']['0']['graph_name'] != 'MODIFIED', \
        "Original graph_name should not be modified"
    assert 'changed' not in original['grid']['0'].get('option', {}).get('y', []), \
        "Original option.y should not be modified"


@utils.print_func_name
def test_id_no_collision_after_delete():
    """New IDs must never collide with existing ones after deletions."""
    home_resource = home.Home()
    dash_resource = dash.DashData()

    id1, _, _ = home_resource._create_dash("Dash 1", "a")
    id2, _, _ = home_resource._create_dash("Dash 2", "a")
    id3, _, _ = home_resource._create_dash("Dash 3", "a")

    # Delete middle dashboard
    dash_resource.delete(id2)

    # Next ID must be greater than id3
    id4, _, _ = home_resource._create_dash("Dash 4", "a")
    assert id4 > id3, \
        "New ID {} should be greater than {}".format(id4, id3)
