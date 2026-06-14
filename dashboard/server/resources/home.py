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

        dash_id = r_db.zcount(config.DASH_ID_KEY, '-inf', '+inf') + 1
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
    4. DASH_ARCHIVED_KEY -> Sorted Set : time_archived -> dash_id (tracks archived items)

    Query parameters:
        status: 'active' (default), 'archived', or 'all'
        page: page number (default 0)
        size: page size (default 100)

    Attributes:
    """
    def get(self, page=0, size=100):
        """Get dashboard meta info, filtered by archive status.

        Args:
            page: page number.
            size: size number.

        Returns:
            list of dict containing the dash_id and accordingly meta info,
            each with an 'is_archived' boolean field.
        """
        status = request.args.get('status', 'active')
        page = int(request.args.get('page', page))
        size = int(request.args.get('size', size))

        # Get archived IDs set for O(1) membership checks
        archived_members = r_db.zrange(config.DASH_ARCHIVED_KEY, 0, -1)
        archived_ids = set(str(i) for i in archived_members)

        # Get all dash IDs (reverse chronological by time_modified)
        dash_list = r_db.zrevrange(config.DASH_ID_KEY, 0, -1, True)

        # Filter by status
        if status == 'active':
            id_list = [i for i in dash_list if str(i[0]) not in archived_ids]
        elif status == 'archived':
            id_list = [i for i in dash_list if str(i[0]) in archived_ids]
        else:
            # 'all' - no filtering
            id_list = dash_list

        # Pagination
        id_list = id_list[page * size : page * size + size]

        data = []
        if id_list:
            dash_meta = r_db.hmget(config.DASH_META_KEY, [i[0] for i in id_list])
            for idx, raw in enumerate(dash_meta):
                meta = json.loads(raw)
                dash_id_str = str(id_list[idx][0])
                meta['is_archived'] = dash_id_str in archived_ids
                if meta['is_archived']:
                    meta['time_archived'] = r_db.zscore(
                        config.DASH_ARCHIVED_KEY, id_list[idx][0])
                data.append(meta)

        return build_response(dict(data=data, code=200))
