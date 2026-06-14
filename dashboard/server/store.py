# -*- coding: utf-8 -*-
"""Consolidated dashboard storage operations.

Every dashboard Redis read/write goes through :class:`DashboardStore`.
Resources should never touch ``r_db`` for dashboard data directly.
"""
from __future__ import absolute_import

import json
import time

from dashboard import r_db
from dashboard.conf import config
from .models import (
    safe_json_loads,
    build_meta,
    build_content,
    validate_meta,
    validate_content,
    validate_update_data,
    ValidationError,
)


class DashboardStore(object):
    """Unified CRUD interface for dashboard records in Redis.

    Uses a dedicated ``INCR`` key for ID generation so IDs are
    monotonically increasing and never collide after deletions.

    All multi-key mutations use a Redis pipeline to minimise the
    window for partial writes.
    """

    def __init__(self, redis_conn=None):
        self.r = redis_conn or r_db

    # ------------------------------------------------------------------
    # ID generation
    # ------------------------------------------------------------------

    def _ensure_counter(self):
        """Initialise the ID counter from the max existing ID if needed."""
        if not self.r.exists(config.DASH_ID_COUNTER_KEY):
            existing_ids = self.r.zrange(config.DASH_ID_KEY, 0, -1)
            if existing_ids:
                max_id = max(int(i) for i in existing_ids)
            else:
                max_id = 0
            # Only set if still absent (narrow race window is acceptable
            # for a single-process Flask dev server).
            self.r.setnx(config.DASH_ID_COUNTER_KEY, max_id)

    def _next_id(self):
        """Return the next dashboard ID (atomic, monotonically increasing)."""
        self._ensure_counter()
        return int(self.r.incr(config.DASH_ID_COUNTER_KEY))

    # ------------------------------------------------------------------
    # Existence check
    # ------------------------------------------------------------------

    def exists(self, dash_id):
        """Return ``True`` if *dash_id* is present in the active ID set."""
        return self.r.zscore(config.DASH_ID_KEY, dash_id) is not None

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(self, name, author):
        """Create a new dashboard.

        Returns:
            tuple: ``(dash_id, meta_dict, content_dict)``

        Raises:
            ValidationError: if *name* or *author* are invalid.
        """
        dash_id = self._next_id()
        now = time.time()

        meta = build_meta(dash_id, name, author, time_modified=now)
        validate_meta(meta)

        content = build_content(dash_id, name)
        validate_content(content)

        pipe = self.r.pipeline()
        pipe.zadd(config.DASH_ID_KEY, dash_id, now)
        pipe.hset(config.DASH_META_KEY, dash_id, json.dumps(meta))
        pipe.hset(config.DASH_CONTENT_KEY, dash_id, json.dumps(content))
        pipe.execute()

        return dash_id, meta, content

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_content(self, dash_id):
        """Return parsed content dict, or ``None`` if not found / corrupt."""
        raw = self.r.hget(config.DASH_CONTENT_KEY, dash_id)
        return safe_json_loads(raw)

    def get_meta(self, dash_id):
        """Return parsed meta dict, or ``None`` if not found / corrupt."""
        raw = self.r.hget(config.DASH_META_KEY, dash_id)
        return safe_json_loads(raw)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dash_id, data):
        """Update an existing dashboard's meta and content.

        The stored content is merged with *data* (i.e. ``content.update(data)``),
        so callers may send a full replacement or a partial patch.

        Returns:
            dict: The merged content after writing, or ``None`` if *dash_id*
                  does not exist.

        Raises:
            ValidationError: if *data* is invalid.
        """
        validate_update_data(data)

        if not self.exists(dash_id):
            return None

        meta = self.get_meta(dash_id)
        content = self.get_content(dash_id)

        if meta is None or content is None:
            return None

        now = time.time()
        meta["time_modified"] = now
        if "name" in data:
            meta["name"] = data["name"]

        content.update(data)

        pipe = self.r.pipeline()
        pipe.hset(config.DASH_META_KEY, dash_id, json.dumps(meta))
        pipe.hset(config.DASH_CONTENT_KEY, dash_id, json.dumps(content))
        pipe.zadd(config.DASH_ID_KEY, dash_id, now)
        pipe.execute()

        return content

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete(self, dash_id):
        """Delete a dashboard, archiving its data under ``DASH_DELETED_KEY``.

        Returns:
            dict: Snapshot of the removed record, or ``None`` if *dash_id*
                  did not exist.
        """
        if not self.exists(dash_id):
            return None

        removed_info = {
            "time_deleted": time.time(),
            "time_modified": self.r.zscore(config.DASH_ID_KEY, dash_id),
            "meta": safe_json_loads(self.r.hget(config.DASH_META_KEY, dash_id), {}),
            "content": safe_json_loads(self.r.hget(config.DASH_CONTENT_KEY, dash_id), {}),
        }

        pipe = self.r.pipeline()
        pipe.hset(config.DASH_DELETED_KEY, dash_id, json.dumps(removed_info))
        pipe.zrem(config.DASH_ID_KEY, dash_id)
        pipe.hdel(config.DASH_META_KEY, dash_id)
        pipe.hdel(config.DASH_CONTENT_KEY, dash_id)
        pipe.execute()

        return removed_info

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def list_dashboards(self, page=0, size=10):
        """Return a page of meta dicts, newest first.

        Corrupt or missing meta entries are silently skipped so that one
        bad record never breaks the entire listing.
        """
        dash_list = self.r.zrevrange(config.DASH_ID_KEY, 0, -1, withscores=True)
        page_slice = dash_list[page * size: page * size + size]

        if not page_slice:
            return []

        ids = [entry[0] for entry in page_slice]
        raw_metas = self.r.hmget(config.DASH_META_KEY, ids)

        result = []
        for raw in raw_metas:
            parsed = safe_json_loads(raw)
            if parsed is not None:
                result.append(parsed)
        return result
