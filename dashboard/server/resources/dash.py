# -*- coding: utf-8 -*-

# built-in package
import time
import json
import random
import hashlib

# third-party package
from flask import request, make_response, render_template, redirect
from flask.ext.restful import Resource

# user-defined package
from dashboard import r_db, config
from ..utils import build_response, print_info


class Dash(Resource):
    """Dashboard html render.

    return the dashboard id, let js do the other work.

    Attributes:
    """
    def get(self, dash_id):
        """Just return the dashboard id in the rendering html.

        JS will do other work [ajax and rendering] according to the dash_id.

        Args:
            dash_id: dashboard id.

        Returns:
            rendered html.
        """
        return make_response(render_template('dashboard.html', dash_id=dash_id, api_root=config.app_host))


class DashData(Resource):
    """Dashboard meta/content CRUD operation.

    Create, read, update and delete dash operation.

    Attributes:
    """
    def get(self, dash_id):
        """Read dashboard content.

        If not found in active area, check archived area and return with archived flag.

        Args:
            dash_id: dashboard id.

        Returns:
            A dict containing the content of that dashboard.
        """
        raw = r_db.hmget(config.DASH_CONTENT_KEY, dash_id)[0]
        if raw:
            data = json.loads(raw)
            return build_response(dict(data=data, code=200))

        # Check archived area
        archived_raw = r_db.hmget(config.DASH_DELETED_CONTENT_KEY, dash_id)[0]
        if archived_raw:
            data = json.loads(archived_raw)
            return build_response(dict(data=data, archived=True, code=200))

        return build_response(dict(data=None, code=404, message="Dashboard not found"))

    def put(self, dash_id=0):
        """Update a dash meta and content, return updated dash content.

        Args:
            dash_id: dashboard id.

        Returns:
            A dict containing the updated content of that dashboard, not include the meta info.
        """
        data = request.get_json()
        updated = self._update_dash(dash_id, data)
        return build_response(dict(data=updated, code=200))

    def delete(self, dash_id):
        """Archive a dashboard (soft delete).

        Moves the dashboard data from active area to archived area in Redis.
        The data is fully preserved and can be restored later.

        Args:
            dash_id: dashboard id.

        Returns:
            A dict indicating the dashboard has been archived.
        """
        meta_raw = r_db.hget(config.DASH_META_KEY, dash_id)
        content_raw = r_db.hget(config.DASH_CONTENT_KEY, dash_id)

        if not meta_raw or not content_raw:
            return build_response(dict(data=None, code=404, message="Dashboard not found"))

        archived_time = time.time()

        # Write to archived area
        r_db.zadd(config.DASH_DELETED_KEY, dash_id, archived_time)
        r_db.hset(config.DASH_DELETED_META_KEY, dash_id, meta_raw)
        r_db.hset(config.DASH_DELETED_CONTENT_KEY, dash_id, content_raw)

        # Remove from active area
        r_db.zrem(config.DASH_ID_KEY, dash_id)
        r_db.hdel(config.DASH_META_KEY, dash_id)
        r_db.hdel(config.DASH_CONTENT_KEY, dash_id)

        return build_response(dict(archived=True, dash_id=dash_id, code=200))

    def _update_dash(self, dash_id, data):
        current_time = time.time()

        meta = json.loads(r_db.hget(config.DASH_META_KEY, dash_id))
        meta.update({'name': '' + data['name'],
                     'time_modified': int(current_time)})
        content = json.loads(r_db.hget(config.DASH_CONTENT_KEY, dash_id))
        content.update(data)

        r_db.hset(config.DASH_META_KEY, dash_id, json.dumps(meta))
        r_db.hset(config.DASH_CONTENT_KEY, dash_id, json.dumps(data))

        updated = {
            "meta": r_db.hget(config.DASH_META_KEY, dash_id),
            "content": r_db.hget(config.DASH_CONTENT_KEY, dash_id),
        }

        return updated


class DashArchiveList(Resource):
    """List all archived dashboards."""

    def get(self, page=0, size=10):
        """Get archived dashboard list with meta information.

        Args:
            page: page number.
            size: page size.

        Returns:
            List of archived dashboard meta info, sorted by archived time (newest first).
        """
        dash_list = r_db.zrevrange(config.DASH_DELETED_KEY, 0, -1, True)
        id_list = dash_list[page * size : page * size + size]
        data = []
        if id_list:
            dash_meta = r_db.hmget(config.DASH_DELETED_META_KEY, [i[0] for i in id_list])
            data = [json.loads(i) for i in dash_meta if i]

        return build_response(dict(data=data, code=200))


class DashRestore(Resource):
    """Restore an archived dashboard back to active area."""

    def post(self, dash_id):
        """Restore a dashboard from archive.

        Checks for ID conflict before restoring. Updates time_modified to current time.

        Args:
            dash_id: dashboard id.

        Returns:
            A dict indicating the dashboard has been restored.
        """
        # Check if the dashboard exists in archived area
        meta_raw = r_db.hget(config.DASH_DELETED_META_KEY, dash_id)
        content_raw = r_db.hget(config.DASH_DELETED_CONTENT_KEY, dash_id)

        if not meta_raw or not content_raw:
            return build_response(dict(data=None, code=404, message="Archived dashboard not found"))

        # Check for ID conflict in active area
        existing = r_db.hget(config.DASH_META_KEY, dash_id)
        if existing:
            return build_response(dict(data=None, code=409, message="A dashboard with this ID already exists in active area"))

        # Restore to active area with updated time
        current_time = time.time()
        meta = json.loads(meta_raw)
        meta['time_modified'] = int(current_time)

        r_db.zadd(config.DASH_ID_KEY, dash_id, current_time)
        r_db.hset(config.DASH_META_KEY, dash_id, json.dumps(meta))
        r_db.hset(config.DASH_CONTENT_KEY, dash_id, content_raw)

        # Remove from archived area
        r_db.zrem(config.DASH_DELETED_KEY, dash_id)
        r_db.hdel(config.DASH_DELETED_META_KEY, dash_id)
        r_db.hdel(config.DASH_DELETED_CONTENT_KEY, dash_id)

        return build_response(dict(restored=True, dash_id=dash_id, code=200))


class DashPermanentDelete(Resource):
    """Permanently delete an archived dashboard."""

    def delete(self, dash_id):
        """Permanently delete a dashboard from the archive. This is irreversible.

        Args:
            dash_id: dashboard id.

        Returns:
            A dict indicating the dashboard has been permanently deleted.
        """
        meta_raw = r_db.hget(config.DASH_DELETED_META_KEY, dash_id)

        if not meta_raw:
            return build_response(dict(data=None, code=404, message="Archived dashboard not found"))

        r_db.zrem(config.DASH_DELETED_KEY, dash_id)
        r_db.hdel(config.DASH_DELETED_META_KEY, dash_id)
        r_db.hdel(config.DASH_DELETED_CONTENT_KEY, dash_id)

        return build_response(dict(deleted=True, dash_id=dash_id, code=200))
