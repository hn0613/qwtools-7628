# -*- coding: utf-8 -*-
"""Unit tests for DashboardRecord schema contract.

These tests do NOT require Redis or Flask -- they test pure data logic.
Run with: pytest tests/test_dash_record.py -v
"""

import sys
import os
import pytest

# conftest.py handles mock setup for sys.modules
from dashboard.server.resources.dash_store import (
    DashboardRecord,
    DashboardValidationError,
)


class TestValidateMeta(object):
    """Tests for DashboardRecord.validate_meta()."""

    def test_valid_meta_passes(self):
        meta = {'name': 'Test Dashboard', 'author': 'Alice'}
        DashboardRecord.validate_meta(meta)

    def test_valid_meta_empty_author_passes(self):
        meta = {'name': 'Test', 'author': ''}
        DashboardRecord.validate_meta(meta)

    def test_valid_meta_no_author_key_passes(self):
        meta = {'name': 'Test'}
        DashboardRecord.validate_meta(meta)

    def test_none_meta_raises(self):
        with pytest.raises(DashboardValidationError):
            DashboardRecord.validate_meta(None)

    def test_non_dict_meta_raises(self):
        with pytest.raises(DashboardValidationError):
            DashboardRecord.validate_meta("not a dict")

    def test_empty_name_raises(self):
        with pytest.raises(DashboardValidationError, match='name is required'):
            DashboardRecord.validate_meta({'name': '', 'author': 'Alice'})

    def test_whitespace_name_raises(self):
        with pytest.raises(DashboardValidationError, match='name is required'):
            DashboardRecord.validate_meta({'name': '   ', 'author': 'Alice'})

    def test_none_name_raises(self):
        with pytest.raises(DashboardValidationError):
            DashboardRecord.validate_meta({'name': None, 'author': 'Alice'})

    def test_non_string_name_raises(self):
        with pytest.raises(DashboardValidationError, match='must be a string'):
            DashboardRecord.validate_meta({'name': 123, 'author': 'Alice'})

    def test_long_name_raises(self):
        with pytest.raises(DashboardValidationError, match='too long'):
            DashboardRecord.validate_meta({'name': 'x' * 201, 'author': 'Alice'})

    def test_max_length_name_passes(self):
        meta = {'name': 'x' * 200, 'author': 'Alice'}
        DashboardRecord.validate_meta(meta)


class TestValidateContent(object):
    """Tests for DashboardRecord.validate_content()."""

    def test_valid_content_passes(self):
        content = {
            'id': 1, 'name': 'Test',
            'grid': {
                '0': {
                    'id': '0', 'x': 0, 'y': 0, 'width': 6, 'height': 5,
                    'key': 'none', 'type': 'none', 'option': {'x': [], 'y': []}
                }
            }
        }
        DashboardRecord.validate_content(content)

    def test_empty_grid_passes(self):
        content = {'id': 1, 'name': 'Test', 'grid': {}}
        DashboardRecord.validate_content(content)

    def test_no_grid_key_passes(self):
        content = {'id': 1, 'name': 'Test'}
        DashboardRecord.validate_content(content)

    def test_non_dict_content_raises(self):
        with pytest.raises(DashboardValidationError):
            DashboardRecord.validate_content("string")

    def test_non_dict_grid_raises(self):
        with pytest.raises(DashboardValidationError, match='grid must be a dict'):
            DashboardRecord.validate_content({'grid': 'bad'})

    def test_non_dict_widget_raises(self):
        with pytest.raises(DashboardValidationError, match='must be a dict'):
            DashboardRecord.validate_content({'grid': {'0': 'bad'}})

    def test_widget_missing_fields_raises(self):
        with pytest.raises(DashboardValidationError, match='missing fields'):
            DashboardRecord.validate_content({
                'grid': {'0': {'id': '0', 'x': 0}}
            })


class TestNormalizeMeta(object):
    """Tests for DashboardRecord.normalize_meta()."""

    def test_complete_meta_unchanged(self):
        meta = {'id': 5, 'name': 'Test', 'author': 'Bob', 'time_modified': 1000.0}
        result = DashboardRecord.normalize_meta(meta)
        assert result == meta

    def test_missing_id_gets_default(self):
        meta = {'name': 'Test', 'author': 'Bob', 'time_modified': 1000.0}
        result = DashboardRecord.normalize_meta(meta)
        assert result['id'] == 0

    def test_missing_author_gets_default(self):
        meta = {'id': 1, 'name': 'Test', 'time_modified': 1000.0}
        result = DashboardRecord.normalize_meta(meta)
        assert result['author'] == ''

    def test_missing_time_modified_gets_default(self):
        meta = {'id': 1, 'name': 'Test', 'author': 'Bob'}
        result = DashboardRecord.normalize_meta(meta)
        assert result['time_modified'] == 0

    def test_none_input_returns_defaults(self):
        result = DashboardRecord.normalize_meta(None)
        assert result['id'] == 0
        assert result['name'] == 'Unknown'
        assert result['author'] == ''
        assert result['time_modified'] == 0

    def test_non_dict_input_returns_defaults(self):
        result = DashboardRecord.normalize_meta("garbage")
        assert result['id'] == 0

    def test_does_not_mutate_input(self):
        meta = {'id': 1, 'name': 'Test'}
        original = dict(meta)
        DashboardRecord.normalize_meta(meta)
        assert meta == original


class TestNormalizeContent(object):
    """Tests for DashboardRecord.normalize_content()."""

    def test_complete_content_unchanged(self):
        content = {'id': 1, 'name': 'Test', 'grid': {}}
        result = DashboardRecord.normalize_content(content)
        assert result['id'] == 1
        assert result['name'] == 'Test'
        assert result['grid'] == {}

    def test_missing_fields_get_defaults(self):
        result = DashboardRecord.normalize_content({})
        assert result['id'] == 0
        assert result['name'] == 'Unknown'
        assert result['grid'] == {}

    def test_none_input_returns_defaults(self):
        result = DashboardRecord.normalize_content(None)
        assert result['id'] == 0
        assert result['grid'] == {}

    def test_widget_missing_fields_get_defaults(self):
        content = {
            'id': 1, 'name': 'Test',
            'grid': {'0': {'id': '0', 'x': 0}}
        }
        result = DashboardRecord.normalize_content(content)
        widget = result['grid']['0']
        assert widget['y'] == 0
        assert widget['width'] == 6
        assert widget['height'] == 5
        assert widget['key'] == 'none'
        assert widget['type'] == 'none'
        assert widget['option'] == {'x': [], 'y': []}
        assert widget['graph_name'] == 'graph name 0'

    def test_does_not_mutate_input(self):
        content = {'id': 1, 'name': 'Test', 'grid': {}}
        original = dict(content)
        DashboardRecord.normalize_content(content)
        assert content == original


class TestMakeDefaultContent(object):
    """Tests for DashboardRecord.make_default_content()."""

    def test_creates_four_grids(self):
        content = DashboardRecord.make_default_content(1, 'Test')
        assert len(content['grid']) == 4
        for i in range(4):
            assert str(i) in content['grid']

    def test_has_correct_id_and_name(self):
        content = DashboardRecord.make_default_content(42, 'My Dash')
        assert content['id'] == 42
        assert content['name'] == 'My Dash'

    def test_each_grid_has_required_fields(self):
        content = DashboardRecord.make_default_content(1, 'Test')
        for gid, widget in content['grid'].items():
            assert 'id' in widget
            assert 'x' in widget
            assert 'y' in widget
            assert 'width' in widget
            assert 'height' in widget
            assert 'key' in widget
            assert 'type' in widget
            assert 'option' in widget
            assert widget['key'] == 'none'
            assert widget['type'] == 'none'

    def test_default_content_passes_validation(self):
        content = DashboardRecord.make_default_content(1, 'Test')
        DashboardRecord.validate_content(content)
