# -*- coding: utf-8 -*-

# built-in package
import json
import time

# third-party package
from flask import render_template, make_response, request, redirect
from flask.ext.restful import Resource

# user-defined package
from dashboard import r_db, config
from ..utils import build_response


def _generate_dash_id():
    """Generate a unique dashboard ID using atomic Redis INCR."""
    return r_db.incr(config.DASH_ID_COUNTER_KEY)


def _generate_copy_name(original_name):
    """Generate a deduplicated copy name.

    First copy: "{name} - Copy"
    Subsequent: "{name} - Copy (2)", "{name} - Copy (3)", etc.
    """
    all_meta_raw = r_db.hvals(config.DASH_META_KEY)
    existing_names = set()
    for raw in all_meta_raw:
        try:
            meta = json.loads(raw)
            existing_names.add(meta.get('name', ''))
        except (ValueError, TypeError):
            pass

    candidate = original_name + ' - Copy'
    if candidate not in existing_names:
        return candidate

    counter = 2
    while True:
        candidate = '{} - Copy ({})'.format(original_name, counter)
        if candidate not in existing_names:
            return candidate
        counter += 1


class Home(Resource):
    """home page

    Just render the home template, and then js will fetch data from server
    to build the list or other things.

    Attributes:
    """
    def get(self):
        return make_response(render_template('home.html', api_root=config.app_host))

    def post(self):
        post_data = request.json
        self._create_dash(post_data.get('name'), post_data.get('author'))
        return redirect('/')

    def _create_dash(self, name, author):
        tmp_time = time.time()
        meta = {'author': author, 'name': name, 'time_modified': tmp_time}
        default_option = {"x": [], "y": []}
        content = {
            "0": {"x": 0, "y": 5, "width": 6, "height": 5, "key": "none", "type": "none", "option": default_option},
            "1": {"x": 6, "y": 5, "width": 6, "height": 5, "key": "none", "type": "none", "option": default_option},
            "2": {"x": 0, "y": 0, "width": 6, "height": 5, "key": "none", "type": "none", "option": default_option},
            "3": {"x": 6, "y": 0, "width": 6, "height": 5, "key": "none", "type": "none", "option": default_option},
        }

        dash_id = _generate_dash_id()
        meta['time_modified'] = tmp_time
        meta['id'] = dash_id
        meta['author'] = author
        meta['name'] = name
        for i in content:
            content[i].update({'graph_name': 'graph name ' + i, 'id': i})

        content = dict(grid=content, name=meta['name'], id=dash_id)
        r_db.zadd(config.DASH_ID_KEY, dash_id, tmp_time)
        r_db.hset(config.DASH_META_KEY, dash_id, json.dumps(meta))
        r_db.hset(config.DASH_CONTENT_KEY, dash_id, json.dumps(content))

        return (dash_id, meta, content)


class DashListData(Resource):
    """Get dashboard list.

    Get the dashboard list with meta information, which is used for rendering
    kinds of `current dashboard list` page.

    DB structure:
    1. DASH_ID_KEY -> Sorted Set : time_modified -> dash_id
    2. DASH_META_KEY -> hash : dash_id -> dash meta info
    3. DASH_CONTENT_KEY -> hash : dash_id -> dash content info [ like ipydb format ]

    Attributes:
    """
    def get(self, page=0, size=10):
        """Get dashboard meta info from in page `page` and page size is `size`.

        Args:
            page: page number.
            size: size number.

        Returns:
            list of dict containing the dash_id and accordingly meta info.
            maybe empty list [] when page * size > total dashes in db. that's reasonable.
        """
        dash_list = r_db.zrevrange(config.DASH_ID_KEY, 0, -1, True)
        id_list = dash_list[page * size : page * size + size]
        dash_meta = []
        data = []
        if id_list:
            dash_meta = r_db.hmget(config.DASH_META_KEY, [i[0] for i in id_list])
            data = [json.loads(i) for i in dash_meta]

        return build_response(dict(data=data, code=200))


class DashDuplicate(Resource):
    """Duplicate an existing dashboard.

    Creates a fully independent copy with a new ID and deduplicated name.
    Deep-copies all grid items, preserving layout, chart types, data key
    references, and axis options.
    """
    def post(self, dash_id):
        raw_content = r_db.hget(config.DASH_CONTENT_KEY, dash_id)
        raw_meta = r_db.hget(config.DASH_META_KEY, dash_id)

        if raw_content is None or raw_meta is None:
            return build_response(dict(
                data=None,
                code=404,
                message='Source dashboard not found'
            ))

        try:
            source_content = json.loads(raw_content)
            source_meta = json.loads(raw_meta)
        except (ValueError, TypeError):
            return build_response(dict(
                data=None,
                code=500,
                message='Failed to parse source dashboard data'
            ))

        new_id = _generate_dash_id()
        new_name = _generate_copy_name(source_meta.get('name', 'Untitled'))
        current_time = time.time()

        # Deep copy grid data to ensure independence
        source_grid = source_content.get('grid', {})
        new_grid = {}
        for grid_key, grid_item in source_grid.iteritems():
            new_item = {}
            for k, v in grid_item.iteritems():
                if isinstance(v, dict):
                    new_item[k] = dict(v)
                    for opt_k, opt_v in v.iteritems():
                        if isinstance(opt_v, list):
                            new_item[k][opt_k] = list(opt_v)
                elif isinstance(v, list):
                    new_item[k] = list(v)
                else:
                    new_item[k] = v
            new_grid[grid_key] = new_item

        new_meta = {
            'id': new_id,
            'name': new_name,
            'author': source_meta.get('author', ''),
            'time_modified': current_time,
        }

        new_content = {
            'id': new_id,
            'name': new_name,
            'grid': new_grid,
        }

        r_db.zadd(config.DASH_ID_KEY, new_id, current_time)
        r_db.hset(config.DASH_META_KEY, new_id, json.dumps(new_meta))
        r_db.hset(config.DASH_CONTENT_KEY, new_id, json.dumps(new_content))

        return build_response(dict(
            data={'id': new_id, 'name': new_name},
            code=200
        ))
