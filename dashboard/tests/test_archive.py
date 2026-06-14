# -*- coding: utf-8 -*-
"""Integration tests for the archive/restore feature.

Tests cover:
- Archive (soft delete) and restore
- Hard delete (permanent)
- List filtering (active/archived/all)
- Idempotency of archive and restore
- Content preservation through archive-restore cycles
- Edge cases: empty lists, non-existent dashes, double operations

Run with: nosetests dashboard/tests/test_archive.py
Requires: Redis running on localhost:6379
"""

import json
import time
import unittest

from dashboard import r_db, config
from dashboard.server.resources.home import Home, DashListData
from dashboard.server.resources.dash import DashData, DashArchive


class TestArchiveFeature(unittest.TestCase):
    """Test the archive/restore/hard-delete workflow."""

    def setUp(self):
        """Create test dashboards and clean archived set."""
        # Clean up archived set
        r_db.delete(config.DASH_ARCHIVED_KEY)

        # Create test dashboards
        self.home = Home()
        self.dash_data = DashData()
        self.dash_archive = DashArchive()
        self.dash_list = DashListData()

        # Create 3 test dashboards
        self.dash_ids = []
        for i in range(3):
            dash_id, meta, content = self.home._create_dash(
                'test-dash-{}'.format(i), 'test-author'
            )
            self.dash_ids.append(str(dash_id))

    def tearDown(self):
        """Clean up test data."""
        for dash_id in self.dash_ids:
            r_db.zrem(config.DASH_ID_KEY, dash_id)
            r_db.hdel(config.DASH_META_KEY, dash_id)
            r_db.hdel(config.DASH_CONTENT_KEY, dash_id)
        r_db.delete(config.DASH_ARCHIVED_KEY)

    # ========================================
    # Archive tests
    # ========================================

    def test_archive_dashboard(self):
        """Archiving a dash should move it from active to archived list."""
        dash_id = self.dash_ids[0]

        # Archive it
        result = self.dash_archive.post(dash_id)
        self.assertEqual(result.status_code, 200)

        # Verify it's in the archived set
        self.assertTrue(r_db.zscore(config.DASH_ARCHIVED_KEY, dash_id) is not None)

    def test_archive_is_idempotent(self):
        """Archiving an already-archived dash should succeed."""
        dash_id = self.dash_ids[0]

        self.dash_archive.post(dash_id)
        result = self.dash_archive.post(dash_id)
        self.assertEqual(result.status_code, 200)

    def test_archive_nonexistent_dash(self):
        """Archiving a non-existent dash should return 404."""
        result = self.dash_archive.post('99999')
        self.assertEqual(result.status_code, 200)
        data = json.loads(result.data)
        self.assertEqual(data['code'], 404)

    def test_archived_data_stays_in_redis(self):
        """Archiving should NOT remove data from DASH_META_KEY or DASH_CONTENT_KEY."""
        dash_id = self.dash_ids[0]

        # Get original content
        original_meta = r_db.hget(config.DASH_META_KEY, dash_id)
        original_content = r_db.hget(config.DASH_CONTENT_KEY, dash_id)

        # Archive
        self.dash_archive.post(dash_id)

        # Data should still be there
        self.assertEqual(r_db.hget(config.DASH_META_KEY, dash_id), original_meta)
        self.assertEqual(r_db.hget(config.DASH_CONTENT_KEY, dash_id), original_content)

    # ========================================
    # Restore tests
    # ========================================

    def test_restore_dashboard(self):
        """Restoring should remove dash from archived set."""
        dash_id = self.dash_ids[0]

        # Archive then restore
        self.dash_archive.post(dash_id)
        result = self.dash_archive.put(dash_id)
        self.assertEqual(result.status_code, 200)

        # Verify it's NOT in the archived set
        self.assertTrue(r_db.zscore(config.DASH_ARCHIVED_KEY, dash_id) is None)

    def test_restore_is_idempotent(self):
        """Restoring a non-archived dash should succeed (no-op)."""
        dash_id = self.dash_ids[0]

        result = self.dash_archive.put(dash_id)
        self.assertEqual(result.status_code, 200)

    def test_restore_nonexistent_dash(self):
        """Restoring a non-existent dash should return 404."""
        result = self.dash_archive.put('99999')
        self.assertEqual(result.status_code, 200)
        data = json.loads(result.data)
        self.assertEqual(data['code'], 404)

    def test_content_preserved_through_archive_restore(self):
        """Content should be byte-identical after archive-restore cycle."""
        dash_id = self.dash_ids[0]

        # Get original content
        original_meta = r_db.hget(config.DASH_META_KEY, dash_id)
        original_content = r_db.hget(config.DASH_CONTENT_KEY, dash_id)

        # Archive and restore
        self.dash_archive.post(dash_id)
        self.dash_archive.put(dash_id)

        # Content should be byte-identical
        self.assertEqual(r_db.hget(config.DASH_META_KEY, dash_id), original_meta)
        self.assertEqual(r_db.hget(config.DASH_CONTENT_KEY, dash_id), original_content)

    def test_time_modified_preserved_on_restore(self):
        """Restore should NOT update time_modified."""
        dash_id = self.dash_ids[0]

        original_meta = json.loads(r_db.hget(config.DASH_META_KEY, dash_id))
        original_time = original_meta['time_modified']

        # Wait a moment, then archive and restore
        time.sleep(0.1)
        self.dash_archive.post(dash_id)
        self.dash_archive.put(dash_id)

        restored_meta = json.loads(r_db.hget(config.DASH_META_KEY, dash_id))
        self.assertEqual(restored_meta['time_modified'], original_time)

    # ========================================
    # Hard delete tests
    # ========================================

    def test_hard_delete_removes_from_all_keys(self):
        """Hard delete should remove from all 4 Redis keys."""
        dash_id = self.dash_ids[0]

        result = self.dash_archive.delete(dash_id)
        self.assertEqual(result.status_code, 200)

        # Verify removed from all keys
        self.assertTrue(r_db.zscore(config.DASH_ID_KEY, dash_id) is None)
        self.assertTrue(r_db.hget(config.DASH_META_KEY, dash_id) is None)
        self.assertTrue(r_db.hget(config.DASH_CONTENT_KEY, dash_id) is None)
        self.assertTrue(r_db.zscore(config.DASH_ARCHIVED_KEY, dash_id) is None)

    def test_hard_delete_archived_dash(self):
        """Hard deleting an archived dash should clean up archived set too."""
        dash_id = self.dash_ids[0]

        # Archive first, then hard delete
        self.dash_archive.post(dash_id)
        self.dash_archive.delete(dash_id)

        # Verify removed from archived set
        self.assertTrue(r_db.zscore(config.DASH_ARCHIVED_KEY, dash_id) is None)

    # ========================================
    # List filter tests
    # ========================================

    def test_list_active_only(self):
        """Active list should exclude archived dashes."""
        # Archive one dash
        self.dash_archive.post(self.dash_ids[0])

        # Get active list (simulate request with status=active)
        with self._request_context('?status=active'):
            result = self.dash_list.get()

        data = json.loads(result.data)
        active_ids = [str(d['id']) for d in data['data']]
        self.assertNotIn(self.dash_ids[0], active_ids)
        self.assertIn(self.dash_ids[1], active_ids)
        self.assertIn(self.dash_ids[2], active_ids)

    def test_list_archived_only(self):
        """Archived list should only include archived dashes."""
        self.dash_archive.post(self.dash_ids[0])

        with self._request_context('?status=archived'):
            result = self.dash_list.get()

        data = json.loads(result.data)
        archived_ids = [str(d['id']) for d in data['data']]
        self.assertIn(self.dash_ids[0], archived_ids)
        self.assertNotIn(self.dash_ids[1], archived_ids)

    def test_list_all(self):
        """All list should include both active and archived."""
        self.dash_archive.post(self.dash_ids[0])

        with self._request_context('?status=all'):
            result = self.dash_list.get()

        data = json.loads(result.data)
        all_ids = [str(d['id']) for d in data['data']]
        for dash_id in self.dash_ids:
            self.assertIn(dash_id, all_ids)

    def test_list_injects_is_archived_flag(self):
        """Each item in the list should have an is_archived boolean."""
        self.dash_archive.post(self.dash_ids[0])

        with self._request_context('?status=all'):
            result = self.dash_list.get()

        data = json.loads(result.data)
        for item in data['data']:
            self.assertIn('is_archived', item)
            if str(item['id']) == self.dash_ids[0]:
                self.assertTrue(item['is_archived'])
            else:
                self.assertFalse(item['is_archived'])

    def test_empty_archive_list(self):
        """Archived list should return empty array when nothing is archived."""
        with self._request_context('?status=archived'):
            result = self.dash_list.get()

        data = json.loads(result.data)
        self.assertEqual(data['data'], [])

    # ========================================
    # Backward compatibility
    # ========================================

    def test_old_data_appears_as_active(self):
        """Data created before archive feature should appear in active list."""
        # All test dashes are not archived, so they should be active
        with self._request_context('?status=active'):
            result = self.dash_list.get()

        data = json.loads(result.data)
        active_ids = [str(d['id']) for d in data['data']]
        for dash_id in self.dash_ids:
            self.assertIn(dash_id, active_ids)

    # ========================================
    # Rapid operation tests
    # ========================================

    def test_rapid_archive_restore_cycle(self):
        """Rapid archive-restore cycles should not corrupt data."""
        dash_id = self.dash_ids[0]
        original_content = r_db.hget(config.DASH_CONTENT_KEY, dash_id)

        for _ in range(5):
            self.dash_archive.post(dash_id)
            self.dash_archive.put(dash_id)

        # Content should still be intact
        self.assertEqual(r_db.hget(config.DASH_CONTENT_KEY, dash_id), original_content)
        # Should be active (restored)
        self.assertTrue(r_db.zscore(config.DASH_ARCHIVED_KEY, dash_id) is None)

    # ========================================
    # Edit after restore test
    # ========================================

    def test_edit_after_restore(self):
        """Editing a restored dashboard should work normally."""
        dash_id = self.dash_ids[0]

        # Archive and restore
        self.dash_archive.post(dash_id)
        self.dash_archive.put(dash_id)

        # Simulate an edit via PUT
        import flask
        app = flask.Flask(__name__)
        with app.test_request_context(
            '/data/dash/' + dash_id,
            method='PUT',
            data=json.dumps({
                'name': 'restored-and-edited',
                'id': int(dash_id),
                'grid': {'0': {'key': 'none', 'type': 'none', 'option': {'x': [], 'y': []}}}
            }),
            content_type='application/json'
        ):
            result = self.dash_data.put(dash_id)

        self.assertEqual(result.status_code, 200)

        # Verify the name was updated
        meta = json.loads(r_db.hget(config.DASH_META_KEY, dash_id))
        self.assertEqual(meta['name'], 'restored-and-edited')

    # ========================================
    # Helpers
    # ========================================

    def _request_context(self, query_string):
        """Create a Flask request context with the given query string."""
        import flask
        app = flask.Flask(__name__)
        return app.test_request_context('/data/dashes/' + query_string)


if __name__ == '__main__':
    unittest.main()
