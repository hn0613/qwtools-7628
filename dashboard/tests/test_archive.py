# -*- coding: utf-8 -*-

"""Tests for dashboard archive, restore, and permanent delete flow.

Covers the full lifecycle:
  create -> archive -> list archived -> restore -> edit/save -> archive -> permanent delete

Edge cases:
  - archive non-existent dashboard
  - restore when ID conflict exists
  - duplicate archive on same item
  - access archived dashboard detail via API
  - permanent delete non-existent archived dashboard
"""

import json
import time

from dashboard import app, r_db, config
from dashboard.server.resources import home


class TestArchive(object):
    """Test suite for archive/restore/permanent-delete closed loop."""

    def setup_method(self):
        """Set up test client and clean Redis before each test."""
        self.app = app.test_client()
        # Clean all dashboard-related keys
        for key in [config.DASH_ID_KEY, config.DASH_META_KEY, config.DASH_CONTENT_KEY,
                     config.DASH_DELETED_KEY, config.DASH_DELETED_META_KEY,
                     config.DASH_DELETED_CONTENT_KEY]:
            r_db.delete(key)

    def _create_dash(self, name="test-dash", author="tester"):
        """Helper: create a dashboard via the Home resource and return dash_id."""
        h = home.Home()
        dash_id, meta, content = h._create_dash(name, author)
        return dash_id

    def _get_active_list(self):
        resp = self.app.get('/data/dashes/')
        return json.loads(resp.data)

    def _get_archived_list(self):
        resp = self.app.get('/data/dashes/archived/')
        return json.loads(resp.data)

    def _get_dash(self, dash_id):
        resp = self.app.get('/data/dash/{}'.format(dash_id))
        return json.loads(resp.data)

    def _archive_dash(self, dash_id):
        resp = self.app.delete('/data/dash/{}'.format(dash_id))
        return json.loads(resp.data)

    def _restore_dash(self, dash_id):
        resp = self.app.post('/data/dash/{}/restore'.format(dash_id),
                             content_type='application/json')
        return json.loads(resp.data)

    def _permanent_delete(self, dash_id):
        resp = self.app.delete('/data/dash/{}/permanent'.format(dash_id))
        return json.loads(resp.data)

    def _update_dash(self, dash_id, data):
        resp = self.app.put('/data/dash/{}'.format(dash_id),
                            data=json.dumps(data),
                            content_type='application/json')
        return json.loads(resp.data)

    # ---- Core flow tests ----

    def test_archive_removes_from_active_list(self):
        """Archiving a dashboard should remove it from the active list."""
        dash_id = self._create_dash("my-dash", "alice")

        result = self._archive_dash(dash_id)
        assert result['code'] == 200
        assert result['archived'] == True

        active = self._get_active_list()
        assert len(active['data']) == 0

    def test_archive_appears_in_archived_list(self):
        """Archived dashboard should appear in the archived list."""
        dash_id = self._create_dash("my-dash", "alice")
        self._archive_dash(dash_id)

        archived = self._get_archived_list()
        assert len(archived['data']) == 1
        assert archived['data'][0]['name'] == "my-dash"
        assert archived['data'][0]['author'] == "alice"

    def test_restore_returns_to_active(self):
        """Restoring an archived dashboard puts it back in the active list."""
        dash_id = self._create_dash("my-dash", "alice")
        self._archive_dash(dash_id)

        result = self._restore_dash(dash_id)
        assert result['code'] == 200
        assert result['restored'] == True

        active = self._get_active_list()
        assert len(active['data']) == 1
        assert active['data'][0]['name'] == "my-dash"

        archived = self._get_archived_list()
        assert len(archived['data']) == 0

    def test_restore_preserves_content(self):
        """Restored dashboard should have identical content to the original."""
        dash_id = self._create_dash("content-test", "bob")

        # Get original content
        original = self._get_dash(dash_id)
        original_data = original['data']

        # Archive and restore
        self._archive_dash(dash_id)
        self._restore_dash(dash_id)

        # Verify content matches
        restored = self._get_dash(dash_id)
        assert restored['data']['name'] == original_data['name']
        assert restored['data']['id'] == original_data['id']
        assert len(restored['data']['grid']) == len(original_data['grid'])

    def test_edit_after_restore(self):
        """Dashboard should be editable and saveable after restoration."""
        dash_id = self._create_dash("editable", "carol")

        # Archive and restore
        self._archive_dash(dash_id)
        self._restore_dash(dash_id)

        # Get current content and modify
        current = self._get_dash(dash_id)
        updated_data = current['data']
        updated_data['name'] = "editable-renamed"

        result = self._update_dash(dash_id, updated_data)
        assert result['code'] == 200

        # Verify the update persisted
        after = self._get_dash(dash_id)
        assert after['data']['name'] == "editable-renamed"

    def test_permanent_delete_from_archive(self):
        """Permanent delete removes from archive completely."""
        dash_id = self._create_dash("disposable", "dave")
        self._archive_dash(dash_id)

        result = self._permanent_delete(dash_id)
        assert result['code'] == 200
        assert result['deleted'] == True

        archived = self._get_archived_list()
        assert len(archived['data']) == 0

        # Also gone from active
        active = self._get_active_list()
        assert len(active['data']) == 0

    def test_full_lifecycle(self):
        """Full loop: create -> archive -> restore -> edit -> archive -> permanent delete."""
        dash_id = self._create_dash("lifecycle", "eve")

        # Archive
        self._archive_dash(dash_id)
        assert len(self._get_active_list()['data']) == 0
        assert len(self._get_archived_list()['data']) == 1

        # Restore
        self._restore_dash(dash_id)
        assert len(self._get_active_list()['data']) == 1
        assert len(self._get_archived_list()['data']) == 0

        # Edit
        current = self._get_dash(dash_id)
        data = current['data']
        data['name'] = "lifecycle-v2"
        self._update_dash(dash_id, data)

        verify = self._get_dash(dash_id)
        assert verify['data']['name'] == "lifecycle-v2"

        # Archive again
        self._archive_dash(dash_id)
        assert len(self._get_archived_list()['data']) == 1

        # Permanent delete
        self._permanent_delete(dash_id)
        assert len(self._get_archived_list()['data']) == 0
        assert len(self._get_active_list()['data']) == 0

    # ---- Edge case tests ----

    def test_archive_nonexistent_returns_404(self):
        """Archiving a non-existent dashboard should return 404."""
        result = self._archive_dash(999)
        assert result['code'] == 404

    def test_restore_nonexistent_returns_404(self):
        """Restoring a non-existent archived dashboard should return 404."""
        result = self._restore_dash(999)
        assert result['code'] == 404

    def test_restore_id_conflict_returns_409(self):
        """Restoring when the same ID exists in active area should return 409."""
        # Create two dashboards
        dash_id_1 = self._create_dash("first", "user1")
        dash_id_2 = self._create_dash("second", "user2")

        # Archive the first one
        self._archive_dash(dash_id_1)

        # Manually put a dashboard with the same ID back in active area
        meta = json.dumps({'name': 'conflict', 'author': 'hacker',
                           'time_modified': int(time.time()), 'id': dash_id_1})
        content = json.dumps({'grid': {}, 'name': 'conflict', 'id': dash_id_1})
        r_db.zadd(config.DASH_ID_KEY, dash_id_1, time.time())
        r_db.hset(config.DASH_META_KEY, dash_id_1, meta)
        r_db.hset(config.DASH_CONTENT_KEY, dash_id_1, content)

        # Try to restore - should conflict
        result = self._restore_dash(dash_id_1)
        assert result['code'] == 409

    def test_double_archive_returns_404(self):
        """Archiving the same dashboard twice should return 404 on second attempt."""
        dash_id = self._create_dash("double", "user")
        self._archive_dash(dash_id)

        result = self._archive_dash(dash_id)
        assert result['code'] == 404

    def test_permanent_delete_nonexistent_returns_404(self):
        """Permanently deleting a non-existent archived dashboard should return 404."""
        result = self._permanent_delete(999)
        assert result['code'] == 404

    def test_access_archived_dash_returns_archived_flag(self):
        """Accessing an archived dashboard via detail API should return archived=True."""
        dash_id = self._create_dash("flagged", "user")
        self._archive_dash(dash_id)

        result = self._get_dash(dash_id)
        assert result['code'] == 200
        assert result['archived'] == True
        assert result['data']['name'] == "flagged"

    def test_access_nonexistent_dash_returns_404(self):
        """Accessing a dashboard that doesn't exist anywhere should return 404."""
        result = self._get_dash(999)
        assert result['code'] == 404

    def test_archive_multiple_dashboards(self):
        """Archiving multiple dashboards should all appear in archived list."""
        ids = []
        for i in range(5):
            ids.append(self._create_dash("dash-{}".format(i), "user"))

        for dash_id in ids:
            self._archive_dash(dash_id)

        active = self._get_active_list()
        assert len(active['data']) == 0

        archived = self._get_archived_list()
        assert len(archived['data']) == 5

    def test_archived_list_empty(self):
        """Archived list should return empty data when nothing is archived."""
        archived = self._get_archived_list()
        assert archived['code'] == 200
        assert len(archived['data']) == 0
