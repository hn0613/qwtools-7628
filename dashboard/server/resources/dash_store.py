# -*- coding: utf-8 -*-
"""Dashboard storage gateway.

This module provides a single, consistent layer for all dashboard CRUD
operations.  Every route that reads or writes dashboard data should go
through ``DashboardStore`` instead of touching Redis directly.

Three components:

* ``DashboardRecord`` -- schema contract (validation on write, normalisation
  on read).  Pure logic, no Redis dependency.
* ``DashboardStore`` -- the only class that talks to Redis for dashboard
  data.  Uses ``pipeline()`` for atomic multi-key writes.
* ``DashboardNotFoundError`` / ``DashboardValidationError`` -- typed
  exceptions that routes convert to structured HTTP error responses.

Redis data structures (all in ``r_db``, DB 1):

===================  ============  =========================================
Key                  Redis type    Contents
===================  ============  =========================================
``dash_id``          Sorted Set    member=dash_id, score=time_modified
``dash_meta``        Hash          field=dash_id, value=JSON meta dict
``dash_content``     Hash          field=dash_id, value=JSON content dict
``dash_seq``         String        INCR counter for monotonic ID generation
===================  ============  =========================================
"""

# built-in package
import json
import time

try:
    basestring
except NameError:
    # Python 3 compatibility
    basestring = str

# user-defined package
from dashboard import r_db, config


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class DashboardNotFoundError(Exception):
    """Raised when a dashboard record does not exist or is corrupted."""

    def __init__(self, dash_id, reason='missing'):
        self.dash_id = dash_id
        self.reason = reason
        super(DashboardNotFoundError, self).__init__(
            'Dashboard {} not found ({})'.format(dash_id, reason)
        )


class DashboardValidationError(Exception):
    """Raised when dashboard data fails schema validation."""
    pass


# ---------------------------------------------------------------------------
# Schema contract
# ---------------------------------------------------------------------------

# Limits
_MAX_NAME_LENGTH = 200
_MAX_AUTHOR_LENGTH = 200
_GRID_REQUIRED_FIELDS = {'id', 'x', 'y', 'width', 'height', 'key', 'type', 'option'}


class DashboardRecord(object):
    """Pure-data schema contract for dashboard records.

    **Meta** (stored in ``DASH_META_KEY`` hash):

    ==========  =========  ==========================================
    Field       Type       Notes
    ==========  =========  ==========================================
    id          int        Globally unique, monotonically increasing
    name        str        1 -- 200 characters
    author      str        May be empty string
    time_modified float   Unix timestamp
    ==========  =========  ==========================================

    **Content** (stored in ``DASH_CONTENT_KEY`` hash):

    ==========  =========  ==========================================
    Field       Type       Notes
    ==========  =========  ==========================================
    id          int        Same as meta.id
    name        str        Same as meta.name
    grid        dict       key=str(grid_id), value=widget dict
    ==========  =========  ==========================================

    Each grid widget must contain: ``id``, ``x``, ``y``, ``width``,
    ``height``, ``key``, ``type``, ``option``.
    """

    # -- validation (strict, used on write) --------------------------------

    @staticmethod
    def validate_meta(meta):
        """Validate a meta dict before writing to storage.

        Raises ``DashboardValidationError`` on any problem.
        """
        if not isinstance(meta, dict):
            raise DashboardValidationError('meta must be a dict')

        name = meta.get('name')
        if name is None or (isinstance(name, basestring) and len(name.strip()) == 0):
            raise DashboardValidationError('dashboard name is required')
        if not isinstance(name, basestring):
            raise DashboardValidationError('dashboard name must be a string')
        if len(name) > _MAX_NAME_LENGTH:
            raise DashboardValidationError(
                'dashboard name too long (max {} chars)'.format(_MAX_NAME_LENGTH)
            )

    @staticmethod
    def validate_content(content):
        """Validate a content dict before writing to storage.

        Raises ``DashboardValidationError`` on any problem.
        """
        if not isinstance(content, dict):
            raise DashboardValidationError('content must be a dict')

        grid = content.get('grid')
        if grid is not None and not isinstance(grid, dict):
            raise DashboardValidationError('grid must be a dict')

        if isinstance(grid, dict):
            for gid, widget in grid.items():
                if not isinstance(widget, dict):
                    raise DashboardValidationError(
                        'grid widget {} must be a dict'.format(gid)
                    )
                missing = _GRID_REQUIRED_FIELDS - set(widget.keys())
                if missing:
                    raise DashboardValidationError(
                        'grid widget {} missing fields: {}'.format(
                            gid, ', '.join(sorted(missing))
                        )
                    )

    # -- normalisation (tolerant, used on read) ----------------------------

    @staticmethod
    def normalize_meta(meta):
        """Fill defaults for missing meta fields (backward compat).

        Returns a *new* dict -- never mutates the input.
        """
        if not isinstance(meta, dict):
            return {'id': 0, 'name': 'Unknown', 'author': '', 'time_modified': 0}
        result = dict(meta)
        result.setdefault('id', 0)
        result.setdefault('name', 'Unknown')
        result.setdefault('author', '')
        result.setdefault('time_modified', 0)
        return result

    @staticmethod
    def normalize_content(content):
        """Fill defaults for missing content fields (backward compat).

        Returns a *new* dict -- never mutates the input.
        """
        if not isinstance(content, dict):
            return {'id': 0, 'name': 'Unknown', 'grid': {}}
        result = dict(content)
        result.setdefault('id', 0)
        result.setdefault('name', 'Unknown')
        result.setdefault('grid', {})
        # Ensure each widget has all required fields with safe defaults
        grid = result.get('grid', {})
        if isinstance(grid, dict):
            for gid, widget in grid.items():
                if isinstance(widget, dict):
                    widget.setdefault('id', gid)
                    widget.setdefault('x', 0)
                    widget.setdefault('y', 0)
                    widget.setdefault('width', 6)
                    widget.setdefault('height', 5)
                    widget.setdefault('key', 'none')
                    widget.setdefault('type', 'none')
                    widget.setdefault('option', {'x': [], 'y': []})
                    widget.setdefault('graph_name', 'graph name ' + str(gid))
        return result

    # -- factory -----------------------------------------------------------

    @staticmethod
    def make_default_content(dash_id, name):
        """Create the default 4-grid content layout for a new dashboard."""
        default_option = {"x": [], "y": []}
        grid = {
            "0": {"x": 0, "y": 5, "width": 6, "height": 5,
                  "key": "none", "type": "none", "option": dict(default_option),
                  "graph_name": "graph name 0", "id": "0"},
            "1": {"x": 6, "y": 5, "width": 6, "height": 5,
                  "key": "none", "type": "none", "option": dict(default_option),
                  "graph_name": "graph name 1", "id": "1"},
            "2": {"x": 0, "y": 0, "width": 6, "height": 5,
                  "key": "none", "type": "none", "option": dict(default_option),
                  "graph_name": "graph name 2", "id": "2"},
            "3": {"x": 6, "y": 0, "width": 6, "height": 5,
                  "key": "none", "type": "none", "option": dict(default_option),
                  "graph_name": "graph name 3", "id": "3"},
        }
        return {"grid": grid, "name": name, "id": dash_id}


# ---------------------------------------------------------------------------
# Storage gateway
# ---------------------------------------------------------------------------

class DashboardStore(object):
    """Single gateway for all dashboard Redis operations.

    All CRUD routes should call methods on this class instead of accessing
    ``r_db`` directly.  Multi-key writes use ``pipeline()`` for atomicity.
    """

    def __init__(self, redis_conn=None):
        self.r_db = redis_conn if redis_conn is not None else r_db

    # -- ID generation -----------------------------------------------------

    def next_id(self):
        """Generate the next dashboard ID using atomic INCR.

        On first call (when ``DASH_SEQ_KEY`` does not exist), the counter is
        seeded from the maximum existing ID in the sorted set so that
        historical data is respected.
        """
        if not self.r_db.exists(config.DASH_SEQ_KEY):
            existing = self.r_db.zrevrange(
                config.DASH_ID_KEY, 0, 0, withscores=True
            )
            if existing:
                # zrevrange returns [(member, score), ...]
                max_id = int(existing[0][0])
                self.r_db.set(config.DASH_SEQ_KEY, max_id)
        return self.r_db.incr(config.DASH_SEQ_KEY)

    # -- existence check ---------------------------------------------------

    def exists(self, dash_id):
        """Return True if both meta and content exist for *dash_id*."""
        return (
            self.r_db.hexists(config.DASH_META_KEY, dash_id) and
            self.r_db.hexists(config.DASH_CONTENT_KEY, dash_id)
        )

    # -- CREATE ------------------------------------------------------------

    def create(self, name, author):
        """Create a new dashboard record.

        Returns ``(dash_id, meta, content)`` on success.

        Raises ``DashboardValidationError`` if *name* is empty or too long.
        """
        # Validate
        DashboardRecord.validate_meta({'name': name, 'author': author})

        dash_id = self.next_id()
        ts = time.time()

        meta = {
            'id': dash_id,
            'name': name,
            'author': author if author else '',
            'time_modified': ts,
        }
        content = DashboardRecord.make_default_content(dash_id, name)
        DashboardRecord.validate_content(content)

        # Atomic write
        pipe = self.r_db.pipeline()
        pipe.zadd(config.DASH_ID_KEY, dash_id, ts)
        pipe.hset(config.DASH_META_KEY, dash_id, json.dumps(meta))
        pipe.hset(config.DASH_CONTENT_KEY, dash_id, json.dumps(content))
        pipe.execute()

        return dash_id, meta, content

    # -- READ --------------------------------------------------------------

    def get_meta(self, dash_id):
        """Return normalised meta dict for *dash_id*, or None if missing."""
        raw = self.r_db.hget(config.DASH_META_KEY, dash_id)
        if raw is None:
            return None
        try:
            meta = json.loads(raw)
        except (ValueError, TypeError):
            return None
        return DashboardRecord.normalize_meta(meta)

    def get_content(self, dash_id):
        """Return normalised content dict for *dash_id*.

        Raises ``DashboardNotFoundError`` if the record does not exist or
        its JSON is corrupted.
        """
        raw = self.r_db.hget(config.DASH_CONTENT_KEY, dash_id)
        if raw is None:
            raise DashboardNotFoundError(dash_id, reason='missing')
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            raise DashboardNotFoundError(dash_id, reason='corrupted')
        if not isinstance(data, dict):
            raise DashboardNotFoundError(dash_id, reason='invalid format')
        return DashboardRecord.normalize_content(data)

    # -- UPDATE ------------------------------------------------------------

    def update(self, dash_id, data):
        """Update an existing dashboard's meta and content.

        *data* is the incoming request payload (dict).  The content stored
        in Redis is always a **merge** of the existing content with *data*,
        never a blind overwrite.

        Returns a dict ``{'meta': <str>, 'content': <str>}`` with the raw
        Redis values after update (same format as the old ``_update_dash``).

        Raises:
            DashboardNotFoundError -- if the record does not exist.
            DashboardValidationError -- if *data* fails validation.
        """
        # Check existence first
        raw_meta = self.r_db.hget(config.DASH_META_KEY, dash_id)
        raw_content = self.r_db.hget(config.DASH_CONTENT_KEY, dash_id)
        if raw_meta is None or raw_content is None:
            raise DashboardNotFoundError(dash_id)

        try:
            meta = json.loads(raw_meta)
        except (ValueError, TypeError):
            raise DashboardNotFoundError(dash_id, reason='corrupted meta')

        try:
            content = json.loads(raw_content)
        except (ValueError, TypeError):
            raise DashboardNotFoundError(dash_id, reason='corrupted content')

        current_time = time.time()

        # Validate incoming name
        incoming_name = data.get('name', meta.get('name', ''))
        DashboardRecord.validate_meta({'name': incoming_name, 'author': meta.get('author', '')})

        # Update meta
        meta.update({
            'name': '' + incoming_name,
            'time_modified': int(current_time),
        })

        # Merge content -- NEVER overwrite with raw request data
        # This fixes the old line-102 bug where `data` was written instead
        # of the merged `content`.
        if not isinstance(content, dict):
            content = {}
        content.update(data)
        # Ensure id and name stay consistent
        content['id'] = meta.get('id', dash_id)
        content['name'] = meta['name']

        DashboardRecord.validate_content(content)

        # Atomic write
        meta_json = json.dumps(meta)
        content_json = json.dumps(content)

        pipe = self.r_db.pipeline()
        pipe.hset(config.DASH_META_KEY, dash_id, meta_json)
        pipe.hset(config.DASH_CONTENT_KEY, dash_id, content_json)
        pipe.zadd(config.DASH_ID_KEY, dash_id, current_time)
        pipe.execute()

        return {
            'meta': meta_json,
            'content': content_json,
        }

    # -- DELETE ------------------------------------------------------------

    def delete(self, dash_id):
        """Delete a dashboard record from all three Redis keys.

        Returns a summary dict of the removed data.

        Raises ``DashboardNotFoundError`` if the record does not exist.
        """
        if not self.exists(dash_id):
            raise DashboardNotFoundError(dash_id)

        removed_info = {
            'time_modified': self.r_db.zscore(config.DASH_ID_KEY, dash_id),
            'meta': self.r_db.hget(config.DASH_META_KEY, dash_id),
            'content': self.r_db.hget(config.DASH_CONTENT_KEY, dash_id),
        }

        pipe = self.r_db.pipeline()
        pipe.zrem(config.DASH_ID_KEY, dash_id)
        pipe.hdel(config.DASH_META_KEY, dash_id)
        pipe.hdel(config.DASH_CONTENT_KEY, dash_id)
        pipe.execute()

        return removed_info

    # -- LIST --------------------------------------------------------------

    def list_meta(self, page=0, size=10):
        """Return a page of dashboard meta records, newest first.

        Orphan IDs (present in sorted set but missing from meta hash) are
        silently skipped -- they will never crash the list endpoint.
        """
        dash_list = self.r_db.zrevrange(config.DASH_ID_KEY, 0, -1, withscores=True)
        id_list = dash_list[page * size: page * size + size]

        if not id_list:
            return []

        ids = [str(i[0]) for i in id_list]
        raw_metas = self.r_db.hmget(config.DASH_META_KEY, ids)

        data = []
        for raw in raw_metas:
            if raw is None:
                # Orphan ID -- meta was deleted but sorted-set entry remains.
                # Skip instead of crashing.
                continue
            try:
                meta = json.loads(raw)
            except (ValueError, TypeError):
                # Corrupted JSON -- skip.
                continue
            data.append(DashboardRecord.normalize_meta(meta))

        return data

    # -- utility -----------------------------------------------------------

    def cleanup_orphans(self):
        """Remove orphan entries from the sorted set.

        An orphan is a dash_id that exists in ``DASH_ID_KEY`` (sorted set)
        but has no corresponding entry in ``DASH_META_KEY``.  This is a
        maintenance utility -- call it manually, not on every request.

        Returns the number of orphans removed.
        """
        dash_list = self.r_db.zrevrange(config.DASH_ID_KEY, 0, -1)
        removed = 0
        for dash_id in dash_list:
            if not self.r_db.hexists(config.DASH_META_KEY, dash_id):
                self.r_db.zrem(config.DASH_ID_KEY, dash_id)
                removed += 1
        return removed
