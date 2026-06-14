# -*- coding: utf-8 -*-
"""Unit tests for DashboardStore gateway.

Uses unittest.mock to simulate Redis -- no real Redis needed.
Run with: pytest tests/test_dash_store.py -v
"""

import json
import pytest
from unittest import mock

# conftest.py handles mock setup for sys.modules
from tests.conftest import get_mock_redis
from dashboard.server.resources.dash_store import (
    DashboardStore,
    DashboardRecord,
    DashboardNotFoundError,
    DashboardValidationError,
)


@pytest.fixture
def store():
    """Create a DashboardStore with a mock Redis backend."""
    r, data = get_mock_redis()
    s = DashboardStore(redis_conn=r)
    s._mock_data = data
    return s


class TestNextId(object):
    """Tests for DashboardStore.next_id()."""

    def test_first_id_from_empty_db(self, store):
        assert store.next_id() == 1

    def test_ids_increment(self, store):
        id1 = store.next_id()
        id2 = store.next_id()
        id3 = store.next_id()
        assert id1 == 1
        assert id2 == 2
        assert id3 == 3

    def test_seeds_from_existing_data(self, store):
        store.r_db.zadd("dash_id", 3, 100.0)
        store.r_db.zadd("dash_id", 7, 200.0)
        store.r_db.zadd("dash_id", 15, 300.0)
        store.r_db.exists = mock.MagicMock(return_value=False)
        next_id = store.next_id()
        assert next_id == 16

    def test_no_reuse_after_delete(self, store):
        id1 = store.next_id()
        id2 = store.next_id()
        id3 = store.next_id()
        id4 = store.next_id()
        assert id4 == 4
        assert id4 != id2


class TestCreate(object):
    """Tests for DashboardStore.create()."""

    def test_create_success(self, store):
        dash_id, meta, content = store.create('Test Dashboard', 'Alice')
        assert dash_id == 1
        assert meta['name'] == 'Test Dashboard'
        assert meta['author'] == 'Alice'
        assert meta['id'] == dash_id
        assert 'time_modified' in meta
        assert content['id'] == dash_id
        assert content['name'] == 'Test Dashboard'
        assert 'grid' in content
        assert len(content['grid']) == 4

    def test_create_stores_in_redis(self, store):
        dash_id, meta, content = store.create('Test', 'Bob')
        raw_meta = store.r_db.hget("dash_meta", dash_id)
        assert raw_meta is not None
        stored_meta = json.loads(raw_meta)
        assert stored_meta['name'] == 'Test'
        raw_content = store.r_db.hget("dash_content", dash_id)
        assert raw_content is not None
        stored_content = json.loads(raw_content)
        assert stored_content['name'] == 'Test'

    def test_create_empty_name_raises(self, store):
        with pytest.raises(DashboardValidationError):
            store.create('', 'Alice')

    def test_create_whitespace_name_raises(self, store):
        with pytest.raises(DashboardValidationError):
            store.create('   ', 'Alice')

    def test_create_empty_author_defaults(self, store):
        dash_id, meta, content = store.create('Test', '')
        assert meta['author'] == ''

    def test_create_none_author_defaults(self, store):
        dash_id, meta, content = store.create('Test', None)
        assert meta['author'] == ''

    def test_create_multiple_unique_ids(self, store):
        id1, _, _ = store.create('Dash 1', 'Alice')
        id2, _, _ = store.create('Dash 2', 'Bob')
        id3, _, _ = store.create('Dash 3', 'Charlie')
        assert len(set([id1, id2, id3])) == 3


class TestGetContent(object):
    """Tests for DashboardStore.get_content()."""

    def test_get_existing(self, store):
        dash_id, _, _ = store.create('Test', 'Alice')
        content = store.get_content(dash_id)
        assert content['name'] == 'Test'
        assert content['id'] == dash_id

    def test_get_missing_raises(self, store):
        with pytest.raises(DashboardNotFoundError):
            store.get_content(99999)

    def test_get_corrupted_json_raises(self, store):
        store.r_db.hset("dash_content", "99", "not valid json{{{")
        store.r_db.hset("dash_meta", "99", '{"id": 99, "name": "x", "author": "", "time_modified": 0}')
        original_hexists = store.r_db.hexists.side_effect
        def hexists_override(key, field):
            if key == "dash_content" and str(field) == "99":
                return True
            if key == "dash_meta" and str(field) == "99":
                return True
            if original_hexists:
                return original_hexists(key, field)
            return False
        store.r_db.hexists = mock.MagicMock(side_effect=hexists_override)
        original_hget = store.r_db.hget.side_effect
        def hget_override(key, field):
            if key == "dash_content" and str(field) == "99":
                return "not valid json{{{"
            if original_hget:
                return original_hget(key, field)
            return None
        store.r_db.hget = mock.MagicMock(side_effect=hget_override)
        with pytest.raises(DashboardNotFoundError) as exc_info:
            store.get_content(99)
        assert exc_info.value.reason == 'corrupted'


class TestUpdate(object):
    """Tests for DashboardStore.update()."""

    def test_update_existing(self, store):
        dash_id, _, _ = store.create('Original', 'Alice')
        updated = store.update(dash_id, {
            'name': 'Updated Name',
            'grid': {'0': {'id': '0', 'x': 1, 'y': 2, 'width': 6, 'height': 5,
                           'key': 'none', 'type': 'none', 'option': {'x': [], 'y': []}}}
        })
        assert updated is not None
        content = store.get_content(dash_id)
        assert content['name'] == 'Updated Name'

    def test_update_merges_not_overwrites(self, store):
        """Regression test for the old line-102 bug."""
        dash_id, _, _ = store.create('Test', 'Alice')
        store.update(dash_id, {
            'name': 'Test', 'custom_field': 'should_persist', 'grid': {}
        })
        store.update(dash_id, {'name': 'Renamed', 'grid': {}})
        content = store.get_content(dash_id)
        assert content['name'] == 'Renamed'
        assert content.get('custom_field') == 'should_persist'

    def test_update_missing_raises(self, store):
        with pytest.raises(DashboardNotFoundError):
            store.update(99999, {'name': 'Test'})

    def test_update_empty_name_raises(self, store):
        dash_id, _, _ = store.create('Original', 'Alice')
        with pytest.raises(DashboardValidationError):
            store.update(dash_id, {'name': ''})


class TestDelete(object):
    """Tests for DashboardStore.delete()."""

    def test_delete_existing(self, store):
        dash_id, _, _ = store.create('Test', 'Alice')
        removed = store.delete(dash_id)
        assert removed is not None
        assert removed['meta'] is not None
        with pytest.raises(DashboardNotFoundError):
            store.get_content(dash_id)

    def test_delete_missing_raises(self, store):
        with pytest.raises(DashboardNotFoundError):
            store.delete(99999)

    def test_delete_removes_all_keys(self, store):
        dash_id, _, _ = store.create('Test', 'Alice')
        store.delete(dash_id)
        assert store.r_db.hget("dash_meta", dash_id) is None
        assert store.r_db.hget("dash_content", dash_id) is None
        assert store.r_db.zscore("dash_id", dash_id) is None


class TestListMeta(object):
    """Tests for DashboardStore.list_meta()."""

    def test_list_empty(self, store):
        assert store.list_meta() == []

    def test_list_after_create(self, store):
        store.create('Dash 1', 'Alice')
        store.create('Dash 2', 'Bob')
        result = store.list_meta()
        assert len(result) == 2

    def test_list_after_delete(self, store):
        id1, _, _ = store.create('Dash 1', 'Alice')
        store.create('Dash 2', 'Bob')
        store.delete(id1)
        result = store.list_meta()
        assert len(result) == 1
        assert result[0]['name'] == 'Dash 2'

    def test_list_pagination(self, store):
        for i in range(5):
            store.create('Dash {}'.format(i), 'Author')
        page0 = store.list_meta(page=0, size=2)
        page1 = store.list_meta(page=1, size=2)
        page2 = store.list_meta(page=2, size=2)
        assert len(page0) == 2
        assert len(page1) == 2
        assert len(page2) == 1

    def test_list_skips_orphan_ids(self, store):
        id1, _, _ = store.create('Dash 1', 'Alice')
        store.create('Dash 2', 'Bob')
        store.r_db.hdel("dash_meta", id1)
        result = store.list_meta()
        assert len(result) == 1
        assert result[0]['name'] == 'Dash 2'


class TestContinuousOperations(object):
    """Integration-style tests for create/delete/create flows."""

    def test_create_delete_create_no_collision(self, store):
        id1, _, _ = store.create('Dash 1', 'Alice')
        id2, _, _ = store.create('Dash 2', 'Bob')
        id3, _, _ = store.create('Dash 3', 'Charlie')
        store.delete(id2)
        id4, _, _ = store.create('Dash 4', 'Dave')

        assert len(set([id1, id2, id3, id4])) == 4
        assert id4 != id2

        assert store.get_content(id1)['name'] == 'Dash 1'
        assert store.get_content(id3)['name'] == 'Dash 3'
        assert store.get_content(id4)['name'] == 'Dash 4'
        with pytest.raises(DashboardNotFoundError):
            store.get_content(id2)

    def test_edit_old_after_new(self, store):
        id1, _, _ = store.create('First', 'Alice')
        store.create('Second', 'Bob')
        store.create('Third', 'Charlie')
        store.update(id1, {'name': 'First (edited)', 'grid': {}})
        assert store.get_content(id1)['name'] == 'First (edited)'

    def test_list_stable_through_operations(self, store):
        id1, _, _ = store.create('A', 'Author')
        store.create('B', 'Author')
        store.create('C', 'Author')
        store.delete(id1)
        store.create('D', 'Author')
        # Update the newest record (D)
        newest = store.list_meta()[0]
        store.update(newest['id'], {'name': 'D-updated', 'grid': {}})
        result = store.list_meta()
        names = [m['name'] for m in result]
        assert 'A' not in names   # deleted
        assert 'B' in names
        assert 'C' in names
        assert 'D-updated' in names
        assert len(result) == 3
