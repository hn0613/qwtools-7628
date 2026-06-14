# -*- coding: utf-8 -*-

# built-in package
import copy
import time
import json
import random
import hashlib

# third-party package
from flask import request, make_response, render_template, redirect
from flask.ext.restful import Resource

# user-defined package
from dashboard import r_db, r_kv, config
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
        raw = r_db.hget(config.DASH_CONTENT_KEY, dash_id)
        if raw is None:
            return build_response(dict(data=None, code=404, message='Dashboard not found')), 404
        data = json.loads(raw)
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


class DashCopy(Resource):
    """Dashboard copy (duplicate) operation.

    Creates an independent copy of an existing dashboard. The copy inherits
    layout, chart titles, data source references and chart types, but is
    fully independent — subsequent edits to either side do not affect the other.

    Attributes:
    """
    def post(self, dash_id):
        """Create a copy of the specified dashboard.

        Args:
            dash_id: source dashboard id.

        Returns:
            A dict containing the new dashboard's id, name and meta on success.
            404 error if the source dashboard does not exist.
        """
        # 1. Read source dashboard
        raw_meta = r_db.hget(config.DASH_META_KEY, dash_id)
        raw_content = r_db.hget(config.DASH_CONTENT_KEY, dash_id)

        if raw_meta is None or raw_content is None:
            return build_response(dict(
                data=None, code=404,
                message='Source dashboard not found: {}'.format(dash_id)
            )), 404

        src_meta = json.loads(raw_meta)
        src_content = json.loads(raw_content)

        # 2. Deep-copy content to ensure full independence
        new_content = copy.deepcopy(src_content)

        # 3. Generate new dash_id
        new_time = time.time()
        new_dash_id = r_db.zcount(config.DASH_ID_KEY, '-inf', '+inf') + 1

        # 4. Build new meta
        new_name = src_meta.get('name', 'Untitled') + u' (\u526f\u672c)'
        new_meta = {
            'id': new_dash_id,
            'name': new_name,
            'author': src_meta.get('author', ''),
            'time_modified': new_time,
            'copied_from': int(dash_id),
        }

        # 5. Update content id/name
        new_content['id'] = new_dash_id
        new_content['name'] = new_name

        # 6. Sanitize grid widgets — handle missing keys, incomplete configs
        default_option = {"x": [], "y": []}
        grid = new_content.get('grid', {})
        for widget_id, widget in grid.items():
            # Fill missing fields with safe defaults
            if 'option' not in widget or not isinstance(widget.get('option'), dict):
                widget['option'] = copy.deepcopy(default_option)
            if 'type' not in widget:
                widget['type'] = 'none'
            if 'key' not in widget:
                widget['key'] = 'none'
            if 'graph_name' not in widget:
                widget['graph_name'] = 'graph name ' + str(widget_id)

            # Validate data source existence in KV store
            key = widget.get('key', 'none')
            if key != 'none':
                if not r_kv.exists(key):
                    # Data source no longer available — reset to empty
                    widget['key'] = 'none'
                    widget['type'] = 'none'
                    widget['option'] = copy.deepcopy(default_option)

        # 7. Persist to Redis
        r_db.zadd(config.DASH_ID_KEY, new_dash_id, new_time)
        r_db.hset(config.DASH_META_KEY, new_dash_id, json.dumps(new_meta))
        r_db.hset(config.DASH_CONTENT_KEY, new_dash_id, json.dumps(new_content))

        return build_response(dict(
            data={
                'id': new_dash_id,
                'name': new_name,
                'meta': new_meta,
            },
            code=200
        ))
