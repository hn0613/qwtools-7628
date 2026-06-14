# -*- coding: utf-8 -*-
"""Comprehensive tests for the dashboard CRUD layer.

Covers models (validation / builders), the DashboardStore (direct
Redis operations), HTTP endpoints (via the Flask test client), ID
collision regression, and error / edge-case scenarios.

Requires a running Redis instance on the configured host.  Dashboard
keys are cleaned between tests — do **not** run against a Redis that
holds production data.

Run with::

    nosetests dashboard/tests/test_dashboard_crud.py -v
    # or
    python -m pytest dashboard/tests/test_dashboard_crud.py -v
"""
from __future__ import absolute_import

import json
import time
import unittest

from dashboard import app, r_db
from dashboard.conf import config
from dashboard.server.store import DashboardStore
from dashboard.server.models import (
    safe_json_loads,
    build_meta,
    build_content,
    make_default_grid,
    validate_meta,
    validate_content,
    validate_update_data,
    ValidationError,
)


# Keys to clean between tests
_DASHBOARD_KEYS = [
    config.DASH_ID_KEY,
    config.DASH_META_KEY,
    config.DASH_CONTENT_KEY,
    config.DASH_DELETED_KEY,
    config.DASH_ID_COUNTER_KEY,
]


class BaseTestCase(unittest.TestCase):
    """Sets up the Flask test client and cleans Redis between tests."""

    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        self.store = DashboardStore()
        for key in _DASHBOARD_KEYS:
            r_db.delete(key)

    def tearDown(self):
        for key in _DASHBOARD_KEYS:
            r_db.delete(key)

    # Helpers ---------------------------------------------------------------

    def _post_json(self, url, data, **kwargs):
        return self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json',
            **kwargs
        )

    def _put_json(self, url, data):
        return self.client.put(
            url,
            data=json.dumps(data),
            content_type='application/json',
        )

    def _get_json(self, response):
        """Parse JSON from a test-client response."""
        return json.loads(response.data)


# ======================================================================
# Models
# ======================================================================

class TestSafeJsonLoads(BaseTestCase):

    def test_none_returns_default(self):
        self.assertIsNone(safe_json_loads(None))
        self.assertEqual(safe_json_loads(None, {}), {})

    def test_corrupt_returns_default(self):
        self.assertIsNone(safe_json_loads("{bad json"))
        self.assertEqual(safe_json_loads("{bad", []), [])

    def test_valid_json(self):
        self.assertEqual(safe_json_loads('{"a": 1}'), {"a": 1})
        self.assertEqual(safe_json_loads('[1,2,3]'), [1, 2, 3])

    def test_empty_string_returns_default(self):
        self.assertIsNone(safe_json_loads(""))

    def test_integer_input_returns_default(self):
        self.assertIsNone(safe_json_loads(123))


class TestValidateMeta(BaseTestCase):

    def test_valid_meta(self):
        meta = {"id": 1, "name": "test", "author": "alice",
                "time_modified": 1.0}
        validate_meta(meta)  # should not raise

    def test_missing_id(self):
        with self.assertRaises(ValidationError):
            validate_meta({"name": "x", "author": "a"})

    def test_missing_name(self):
        with self.assertRaises(ValidationError):
            validate_meta({"id": 1, "author": "a"})

    def test_empty_name(self):
        with self.assertRaises(ValidationError):
            validate_meta({"id": 1, "name": "", "author": "a"})

    def test_name_too_long(self):
        with self.assertRaises(ValidationError):
            validate_meta({"id": 1, "name": "x" * 200, "author": "a"})

    def test_missing_author(self):
        with self.assertRaises(ValidationError):
            validate_meta({"id": 1, "name": "x"})

    def test_non_dict_raises(self):
        with self.assertRaises(ValidationError):
            validate_meta("not a dict")


class TestValidateContent(BaseTestCase):

    def test_valid_content(self):
        validate_content({"id": 1, "grid": {}})

    def test_missing_grid(self):
        with self.assertRaises(ValidationError):
            validate_content({"id": 1})

    def test_grid_not_dict(self):
        with self.assertRaises(ValidationError):
            validate_content({"id": 1, "grid": "bad"})


class TestValidateUpdateData(BaseTestCase):

    def test_valid_update(self):
        validate_update_data({"name": "new", "grid": {}})

    def test_non_dict_raises(self):
        with self.assertRaises(ValidationError):
            validate_update_data("bad")

    def test_name_too_long(self):
        with self.assertRaises(ValidationError):
            validate_update_data({"name": "x" * 200})


class TestBuilders(BaseTestCase):

    def test_build_meta_shape(self):
        meta = build_meta(1, "test", "alice", time_modified=100.0)
        self.assertEqual(meta["id"], 1)
        self.assertEqual(meta["name"], "test")
        self.assertEqual(meta["author"], "alice")
        self.assertEqual(meta["time_modified"], 100.0)

    def test_build_meta_default_time(self):
        before = time.time()
        meta = build_meta(1, "t", "a")
        after = time.time()
        self.assertGreaterEqual(meta["time_modified"], before)
        self.assertLessEqual(meta["time_modified"], after)

    def test_build_content_default_grid(self):
        content = build_content(1, "test")
        self.assertEqual(content["id"], 1)
        self.assertEqual(content["name"], "test")
        self.assertIn("grid", content)
        self.assertEqual(len(content["grid"]), 4)

    def test_build_content_custom_grid(self):
        grid = {"0": {"x": 0, "y": 0}}
        content = build_content(1, "test", grid=grid)
        self.assertEqual(content["grid"], grid)

    def test_default_grid_structure(self):
        grid = make_default_grid()
        self.assertEqual(len(grid), 4)
        for key in ["0", "1", "2", "3"]:
            item = grid[key]
            self.assertEqual(item["id"], key)
            self.assertEqual(item["key"], "none")
            self.assertEqual(item["type"], "none")
            self.assertIn("option", item)
            self.assertIn("graph_name", item)
            for field in ["x", "y", "width", "height"]:
                self.assertIn(field, item)


# ======================================================================
# Store — direct Redis operations
# ======================================================================

class TestStoreCreate(BaseTestCase):

    def test_create_returns_tuple(self):
        dash_id, meta, content = self.store.create("My Dash", "alice")
        self.assertEqual(dash_id, 1)
        self.assertEqual(meta["name"], "My Dash")
        self.assertEqual(meta["author"], "alice")
        self.assertEqual(content["id"], 1)
        self.assertEqual(content["name"], "My Dash")
        self.assertIn("grid", content)

    def test_create_stores_in_redis(self):
        dash_id, _, _ = self.store.create("d1", "a1")
        self.assertTrue(self.store.exists(dash_id))
        self.assertIsNotNone(self.store.get_meta(dash_id))
        self.assertIsNotNone(self.store.get_content(dash_id))

    def test_create_monotonic_ids(self):
        id1, _, _ = self.store.create("d1", "a1")
        id2, _, _ = self.store.create("d2", "a2")
        id3, _, _ = self.store.create("d3", "a3")
        self.assertEqual(id1, 1)
        self.assertEqual(id2, 2)
        self.assertEqual(id3, 3)

    def test_create_invalid_name_raises(self):
        with self.assertRaises(ValidationError):
            self.store.create("", "alice")

    def test_create_invalid_author_raises(self):
        with self.assertRaises(ValidationError):
            self.store.create("test", "")


class TestStoreRead(BaseTestCase):

    def test_get_content_existing(self):
        dash_id, _, _ = self.store.create("d1", "a1")
        content = self.store.get_content(dash_id)
        self.assertIsNotNone(content)
        self.assertEqual(content["name"], "d1")

    def test_get_content_missing(self):
        self.assertIsNone(self.store.get_content(9999))

    def test_get_meta_existing(self):
        dash_id, _, _ = self.store.create("d1", "a1")
        meta = self.store.get_meta(dash_id)
        self.assertIsNotNone(meta)
        self.assertEqual(meta["author"], "a1")

    def test_get_meta_missing(self):
        self.assertIsNone(self.store.get_meta(9999))

    def test_exists_true(self):
        dash_id, _, _ = self.store.create("d1", "a1")
        self.assertTrue(self.store.exists(dash_id))

    def test_exists_false(self):
        self.assertFalse(self.store.exists(9999))


class TestStoreUpdate(BaseTestCase):

    def test_update_name(self):
        dash_id, _, _ = self.store.create("old", "a1")
        updated = self.store.update(dash_id, {"name": "new", "grid": {},
                                               "id": dash_id})
        self.assertEqual(updated["name"], "new")
        # meta should also be updated
        meta = self.store.get_meta(dash_id)
        self.assertEqual(meta["name"], "new")

    def test_update_merges_content(self):
        dash_id, _, original = self.store.create("d1", "a1")
        original_grid_keys = set(original["grid"].keys())
        custom_grid = {"0": {"x": 1, "y": 2, "width": 12, "height": 10,
                              "key": "mykey", "type": "bar",
                              "option": {"x": ["a"], "y": ["b"]},
                              "graph_name": "chart1", "id": "0"}}
        self.store.update(dash_id, {"name": "d1", "grid": custom_grid,
                                     "id": dash_id})
        content = self.store.get_content(dash_id)
        self.assertEqual(content["grid"]["0"]["key"], "mykey")

    def test_update_timestamp_advances(self):
        dash_id, meta_before, _ = self.store.create("d1", "a1")
        time.sleep(0.05)
        self.store.update(dash_id, {"name": "d1", "grid": {}, "id": dash_id})
        meta_after = self.store.get_meta(dash_id)
        self.assertGreater(meta_after["time_modified"],
                           meta_before["time_modified"])

    def test_update_nonexistent_returns_none(self):
        result = self.store.update(9999, {"name": "x"})
        self.assertIsNone(result)

    def test_update_invalid_data_raises(self):
        dash_id, _, _ = self.store.create("d1", "a1")
        with self.assertRaises(ValidationError):
            self.store.update(dash_id, "not a dict")


class TestStoreDelete(BaseTestCase):

    def test_delete_existing(self):
        dash_id, _, _ = self.store.create("d1", "a1")
        removed = self.store.delete(dash_id)
        self.assertIsNotNone(removed)
        self.assertIn("meta", removed)
        self.assertIn("content", removed)
        self.assertIn("time_deleted", removed)

    def test_delete_removes_from_active(self):
        dash_id, _, _ = self.store.create("d1", "a1")
        self.store.delete(dash_id)
        self.assertFalse(self.store.exists(dash_id))
        self.assertIsNone(self.store.get_meta(dash_id))
        self.assertIsNone(self.store.get_content(dash_id))

    def test_delete_archives_to_deleted_key(self):
        dash_id, _, _ = self.store.create("d1", "a1")
        self.store.delete(dash_id)
        raw = r_db.hget(config.DASH_DELETED_KEY, dash_id)
        self.assertIsNotNone(raw)
        archived = json.loads(raw)
        self.assertEqual(archived["meta"]["name"], "d1")

    def test_delete_nonexistent_returns_none(self):
        self.assertIsNone(self.store.delete(9999))


class TestStoreList(BaseTestCase):

    def test_list_empty(self):
        self.assertEqual(self.store.list_dashboards(), [])

    def test_list_returns_metas(self):
        self.store.create("d1", "a1")
        self.store.create("d2", "a2")
        result = self.store.list_dashboards()
        self.assertEqual(len(result), 2)
        names = [m["name"] for m in result]
        self.assertIn("d1", names)
        self.assertIn("d2", names)

    def test_list_newest_first(self):
        self.store.create("old", "a1")
        time.sleep(0.05)
        self.store.create("new", "a2")
        result = self.store.list_dashboards()
        self.assertEqual(result[0]["name"], "new")
        self.assertEqual(result[1]["name"], "old")

    def test_list_skips_corrupt_meta(self):
        dash_id, _, _ = self.store.create("good", "a1")
        # Manually corrupt one meta entry
        r_db.hset(config.DASH_META_KEY, dash_id, "{bad json")
        result = self.store.list_dashboards()
        # The corrupt entry should be skipped, not crash
        self.assertEqual(len(result), 0)

    def test_list_pagination(self):
        for i in range(5):
            self.store.create("d%d" % i, "a%d" % i)
        page0 = self.store.list_dashboards(page=0, size=2)
        page1 = self.store.list_dashboards(page=1, size=2)
        page2 = self.store.list_dashboards(page=2, size=2)
        self.assertEqual(len(page0), 2)
        self.assertEqual(len(page1), 2)
        self.assertEqual(len(page2), 1)

    def test_list_excludes_deleted(self):
        id1, _, _ = self.store.create("d1", "a1")
        self.store.create("d2", "a2")
        self.store.delete(id1)
        result = self.store.list_dashboards()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "d2")


# ======================================================================
# ID collision regression
# ======================================================================

class TestIDCollision(BaseTestCase):

    def test_no_collision_after_middle_delete(self):
        """create [1,2,3], delete 2, create new -> ID must be 4."""
        id1, _, _ = self.store.create("d1", "a1")
        id2, _, _ = self.store.create("d2", "a2")
        id3, _, _ = self.store.create("d3", "a3")
        self.store.delete(id2)
        id4, _, _ = self.store.create("d4", "a4")
        self.assertEqual(id4, 4)
        self.assertTrue(self.store.exists(id1))
        self.assertFalse(self.store.exists(id2))
        self.assertTrue(self.store.exists(id3))
        self.assertTrue(self.store.exists(id4))

    def test_no_collision_after_all_deleted(self):
        """create [1,2,3], delete all, create new -> ID must be 4."""
        id1, _, _ = self.store.create("d1", "a1")
        id2, _, _ = self.store.create("d2", "a2")
        id3, _, _ = self.store.create("d3", "a3")
        self.store.delete(id1)
        self.store.delete(id2)
        self.store.delete(id3)
        id4, _, _ = self.store.create("d4", "a4")
        self.assertEqual(id4, 4)

    def test_rapid_create_delete_cycle(self):
        """20 rounds of create/delete produce unique IDs."""
        seen_ids = set()
        for i in range(20):
            did, _, _ = self.store.create("d%d" % i, "a%d" % i)
            self.assertNotIn(did, seen_ids, "Collision at ID %s" % did)
            seen_ids.add(did)
            if i % 3 == 0:
                self.store.delete(did)

    def test_counter_initialises_from_existing_data(self):
        """If dashboards already exist (legacy data), counter starts above max."""
        # Simulate legacy data: manually insert IDs 5 and 10
        now = time.time()
        r_db.zadd(config.DASH_ID_KEY, 5, now)
        r_db.hset(config.DASH_META_KEY, 5,
                  json.dumps({"id": 5, "name": "legacy5", "author": "x",
                              "time_modified": now}))
        r_db.hset(config.DASH_CONTENT_KEY, 5,
                  json.dumps({"id": 5, "name": "legacy5", "grid": {}}))
        r_db.zadd(config.DASH_ID_KEY, 10, now)
        r_db.hset(config.DASH_META_KEY, 10,
                  json.dumps({"id": 10, "name": "legacy10", "author": "x",
                              "time_modified": now}))
        r_db.hset(config.DASH_CONTENT_KEY, 10,
                  json.dumps({"id": 10, "name": "legacy10", "grid": {}}))

        new_id, _, _ = self.store.create("new", "alice")
        self.assertEqual(new_id, 11)

    def test_create_delete_edit_old_then_create(self):
        """Full flow: create several, delete one, edit an old one, create new."""
        id1, _, _ = self.store.create("first", "a1")
        id2, _, _ = self.store.create("second", "a2")
        id3, _, _ = self.store.create("third", "a3")

        # delete the middle one
        self.store.delete(id2)

        # edit the first one
        updated = self.store.update(id1, {"name": "first-edited",
                                           "grid": {}, "id": id1})
        self.assertEqual(updated["name"], "first-edited")

        # create a new one — must get id 4
        id4, _, _ = self.store.create("fourth", "a4")
        self.assertEqual(id4, 4)

        # verify state
        listing = self.store.list_dashboards(size=100)
        names = sorted([m["name"] for m in listing])
        self.assertEqual(names, ["first-edited", "fourth", "third"])


# ======================================================================
# HTTP endpoints
# ======================================================================

class TestHomeEndpoints(BaseTestCase):

    def test_get_home_page(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)

    def test_post_create_valid(self):
        resp = self._post_json('/', {"name": "test dash", "author": "alice"},
                               follow_redirects=False)
        self.assertIn(resp.status_code, [301, 302])

    def test_post_create_missing_name(self):
        resp = self._post_json('/', {"author": "alice"})
        body = self._get_json(resp)
        self.assertEqual(body["code"], 400)

    def test_post_create_missing_author(self):
        resp = self._post_json('/', {"name": "test"})
        body = self._get_json(resp)
        self.assertEqual(body["code"], 400)

    def test_post_create_empty_body(self):
        resp = self.client.post('/', data='not json',
                                content_type='text/plain')
        body = self._get_json(resp)
        self.assertEqual(body["code"], 400)


class TestDashListEndpoints(BaseTestCase):

    def test_list_empty(self):
        resp = self.client.get('/data/dashes/')
        body = self._get_json(resp)
        self.assertEqual(body["code"], 200)
        self.assertEqual(body["data"], [])

    def test_list_after_create(self):
        self.store.create("d1", "a1")
        self.store.create("d2", "a2")
        resp = self.client.get('/data/dashes/')
        body = self._get_json(resp)
        self.assertEqual(body["code"], 200)
        self.assertEqual(len(body["data"]), 2)

    def test_list_response_shape(self):
        self.store.create("d1", "a1")
        resp = self.client.get('/data/dashes/')
        body = self._get_json(resp)
        self.assertIn("data", body)
        self.assertIn("code", body)
        entry = body["data"][0]
        self.assertIn("id", entry)
        self.assertIn("name", entry)
        self.assertIn("author", entry)
        self.assertIn("time_modified", entry)


class TestDashDataEndpoints(BaseTestCase):

    def test_get_existing(self):
        dash_id, _, _ = self.store.create("d1", "a1")
        resp = self.client.get('/data/dash/%s' % dash_id)
        body = self._get_json(resp)
        self.assertEqual(body["code"], 200)
        self.assertEqual(body["data"]["name"], "d1")
        self.assertIn("grid", body["data"])

    def test_get_nonexistent(self):
        resp = self.client.get('/data/dash/9999')
        body = self._get_json(resp)
        self.assertEqual(body["code"], 404)

    def test_get_response_shape(self):
        dash_id, _, _ = self.store.create("d1", "a1")
        resp = self.client.get('/data/dash/%s' % dash_id)
        body = self._get_json(resp)
        self.assertIn("data", body)
        self.assertIn("code", body)

    def test_put_update(self):
        dash_id, _, _ = self.store.create("old", "a1")
        resp = self._put_json('/data/dash/%s' % dash_id,
                              {"name": "new", "grid": {}, "id": dash_id})
        body = self._get_json(resp)
        self.assertEqual(body["code"], 200)
        self.assertEqual(body["data"]["name"], "new")

    def test_put_nonexistent(self):
        resp = self._put_json('/data/dash/9999',
                              {"name": "x", "grid": {}})
        body = self._get_json(resp)
        self.assertEqual(body["code"], 404)

    def test_put_invalid_body(self):
        dash_id, _, _ = self.store.create("d1", "a1")
        resp = self.client.put('/data/dash/%s' % dash_id,
                               data='not json',
                               content_type='text/plain')
        body = self._get_json(resp)
        self.assertEqual(body["code"], 400)

    def test_delete_existing(self):
        dash_id, _, _ = self.store.create("d1", "a1")
        resp = self.client.delete('/data/dash/%s' % dash_id)
        body = self._get_json(resp)
        self.assertEqual(body["code"], 200)
        self.assertIn("meta", body["data"])

    def test_delete_nonexistent(self):
        resp = self.client.delete('/data/dash/9999')
        body = self._get_json(resp)
        self.assertEqual(body["code"], 404)

    def test_get_after_delete_returns_404(self):
        dash_id, _, _ = self.store.create("d1", "a1")
        self.client.delete('/data/dash/%s' % dash_id)
        resp = self.client.get('/data/dash/%s' % dash_id)
        body = self._get_json(resp)
        self.assertEqual(body["code"], 404)


class TestDashPageEndpoint(BaseTestCase):

    def test_existing_dashboard_page(self):
        dash_id, _, _ = self.store.create("d1", "a1")
        resp = self.client.get('/dash/%s' % dash_id)
        self.assertEqual(resp.status_code, 200)

    def test_nonexistent_dashboard_page(self):
        resp = self.client.get('/dash/9999')
        body = self._get_json(resp)
        self.assertEqual(body["code"], 404)


# ======================================================================
# Full workflow integration
# ======================================================================

class TestFullWorkflow(BaseTestCase):
    """Simulates the sequences described in the requirements:
    create several, delete one, go back and edit an old one, access an
    invalid link — all in one continuous flow.
    """

    def test_continuous_flow(self):
        # 1. Create three dashboards
        resp1 = self._post_json('/', {"name": "dash one", "author": "alice"},
                                follow_redirects=False)
        self.assertIn(resp1.status_code, [301, 302])
        resp2 = self._post_json('/', {"name": "dash two", "author": "bob"},
                                follow_redirects=False)
        resp3 = self._post_json('/', {"name": "dash three", "author": "carol"},
                                follow_redirects=False)

        # 2. List should show 3
        listing = self._get_json(self.client.get('/data/dashes/'))
        self.assertEqual(len(listing["data"]), 3)

        # 3. Delete the second one
        id2 = listing["data"][1]["id"]
        del_resp = self.client.delete('/data/dash/%s' % id2)
        self.assertEqual(self._get_json(del_resp)["code"], 200)

        # 4. List should show 2
        listing = self._get_json(self.client.get('/data/dashes/'))
        self.assertEqual(len(listing["data"]), 2)

        # 5. Edit the first one
        id1 = listing["data"][0]["id"]
        edit_resp = self._put_json(
            '/data/dash/%s' % id1,
            {"name": "edited dash", "grid": {}, "id": id1})
        self.assertEqual(self._get_json(edit_resp)["code"], 200)

        # 6. Access the deleted one — should be 404
        resp_gone = self.client.get('/data/dash/%s' % id2)
        self.assertEqual(self._get_json(resp_gone)["code"], 404)

        # 7. Access a totally invalid link
        resp_invalid = self.client.get('/data/dash/no_such_thing')
        self.assertEqual(self._get_json(resp_invalid)["code"], 404)

        # 8. Create a new one — should get a fresh ID with no collision
        resp4 = self._post_json('/', {"name": "dash four", "author": "dave"},
                                follow_redirects=False)
        self.assertIn(resp4.status_code, [301, 302])
        listing = self._get_json(self.client.get('/data/dashes/'))
        self.assertEqual(len(listing["data"]), 3)
        all_ids = [m["id"] for m in listing["data"]]
        self.assertEqual(len(all_ids), len(set(all_ids)), "IDs must be unique")


if __name__ == '__main__':
    unittest.main()
