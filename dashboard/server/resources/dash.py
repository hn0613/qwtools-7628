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

        Args:
            dash_id: dashboard id.

        Returns:
            A dict containing the content of that dashboard, not include the meta info.
        """
        data = json.loads(r_db.hmget(config.DASH_CONTENT_KEY, dash_id)[0])
        return build_response(dict(data=data, code=200))

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
        """Delete a dash meta and content, return updated dash content.

        Actually, just remove it to a specfied place in database.

        Args:
            dash_id: dashboard id.

        Returns:
            Redirect to home page.
        """
        removed_info = dict(
            time_modified = r_db.zscore(config.DASH_ID_KEY, dash_id),
            meta = r_db.hget(config.DASH_META_KEY, dash_id),
            content = r_db.hget(config.DASH_CONTENT_KEY, dash_id))
        r_db.zrem(config.DASH_ID_KEY, dash_id)
        r_db.hdel(config.DASH_META_KEY, dash_id)
        r_db.hdel(config.DASH_CONTENT_KEY, dash_id)
        return {'removed_info': removed_info}
        # return redirect('/')

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


class DashArchive(Resource):
    """Archive, restore and hard-delete operations for dashboards.

    POST   /data/dash/<id>/archive  - archive (soft delete, reversible)
    PUT    /data/dash/<id>/archive  - restore from archive
    DELETE /data/dash/<id>/archive  - hard delete (permanent, irreversible)

    Design: archived data stays in place in the original Redis keys
    (DASH_ID_KEY, DASH_META_KEY, DASH_CONTENT_KEY). A separate sorted set
    DASH_ARCHIVED_KEY tracks which dash_ids are archived. This means:
    - archive/restore are zero-copy (no data movement)
    - old data works without migration (not in archived set = active)
    - content is byte-identical after an archive-restore round trip
    """

    def post(self, dash_id):
        """Archive a dashboard (soft delete).

        Adds dash_id to DASH_ARCHIVED_KEY with current time as score.
        Data stays in place in all original Redis keys.
        Idempotent: archiving an already-archived dash returns success
        (updates the archive timestamp).
        """
        meta = r_db.hget(config.DASH_META_KEY, dash_id)
        if not meta:
            return build_response(dict(
                data=None, code=404,
                message='Dashboard {} not found'.format(dash_id)
            ))

        r_db.zadd(config.DASH_ARCHIVED_KEY, dash_id, time.time())

        return build_response(dict(
            data={'id': dash_id, 'action': 'archived'}, code=200
        ))

    def put(self, dash_id):
        """Restore an archived dashboard.

        Removes dash_id from DASH_ARCHIVED_KEY. Data stays in place.
        Idempotent: restoring a non-archived dash returns success.
        Does NOT update time_modified - original metadata is preserved.
        """
        meta = r_db.hget(config.DASH_META_KEY, dash_id)
        if not meta:
            return build_response(dict(
                data=None, code=404,
                message='Dashboard {} not found'.format(dash_id)
            ))

        r_db.zrem(config.DASH_ARCHIVED_KEY, dash_id)

        return build_response(dict(
            data={'id': dash_id, 'action': 'restored'}, code=200
        ))

    def delete(self, dash_id):
        """Hard delete a dashboard permanently from all Redis keys.

        Removes from DASH_ID_KEY, DASH_META_KEY, DASH_CONTENT_KEY,
        and DASH_ARCHIVED_KEY. This is IRREVERSIBLE.
        """
        removed_info = dict(
            time_modified=r_db.zscore(config.DASH_ID_KEY, dash_id),
            meta=r_db.hget(config.DASH_META_KEY, dash_id),
            content=r_db.hget(config.DASH_CONTENT_KEY, dash_id)
        )

        r_db.zrem(config.DASH_ID_KEY, dash_id)
        r_db.hdel(config.DASH_META_KEY, dash_id)
        r_db.hdel(config.DASH_CONTENT_KEY, dash_id)
        r_db.zrem(config.DASH_ARCHIVED_KEY, dash_id)

        return build_response(dict(
            data={'id': dash_id, 'action': 'deleted',
                  'removed_info': removed_info}, code=200
        ))
