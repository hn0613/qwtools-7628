# -*- coding: utf-8 -*-

# built-in package
import time
import json
import random
import hashlib

# third-party package
import sqlparse
from flask.ext.restful import Resource
from flask import request, make_response, render_template, redirect

# user-defined package
from dashboard import r_db, config
from ..utils import build_response, print_info, SQL


class Sql(Resource):
    """sql html render.

    return the rendered sql template id

    Attributes:
    """
    def get(self):
        return make_response(render_template('sql.html', api_root=config.app_host))


class SqlData(Resource):
    """sql executor.

    return the result of executed sql

    Attributes:
    """
    def post(self):
        '''return executed sql result to client.

        post data format:

            {"options": ['all', 'selected', 'first', 'last', 'format'], "sql_raw": "raw sql ..."}

        Returns:
            sql result.
        '''
        data = request.get_json()
        options, sql_raw = data.get('options'), data.get('sql_raw')

        # --- format mode (no execution) ---
        if options == 'format':
            if not sql_raw or not sql_raw.strip():
                return build_response(dict(data='', code=200))
            sql_formatted = sqlparse.format(sql_raw, keyword_case='upper', reindent=True)
            return build_response(dict(data=sql_formatted, code=200))

        # --- validate non-empty SQL for execution modes ---
        if not sql_raw or not sql_raw.strip():
            return build_response(dict(data=None, error='SQL is empty.', code=400))

        # --- determine which SQL to execute ---
        if options in ('all', 'selected'):
            sql_to_run = sql_raw
        elif options == 'first':
            statements = [s.strip() for s in sqlparse.split(sql_raw) if s.strip()]
            if not statements:
                return build_response(dict(data=None, error='No valid SQL statement found.', code=400))
            sql_to_run = statements[0]
        elif options == 'last':
            statements = [s.strip() for s in sqlparse.split(sql_raw) if s.strip()]
            if not statements:
                return build_response(dict(data=None, error='No valid SQL statement found.', code=400))
            sql_to_run = statements[-1]
        else:
            return build_response(dict(data=None, error='Unknown option: {}'.format(options), code=400))

        # --- execute ---
        try:
            conn = SQL(config.sql_host, config.sql_port, config.sql_user,
                       config.sql_pwd, config.sql_db)
            result = conn.run(sql_to_run)
        except Exception as e:
            return build_response(dict(data=None, error='Database connection error: {}'.format(str(e)), code=500))

        if not result.get('success'):
            return build_response(dict(data=None, error=result.get('error', 'Unknown error'), code=500))

        if result['type'] == 'select':
            return build_response(dict(data=result['data'], code=200))
        else:
            msg = '{} row(s) affected.'.format(result.get('rowcount', 0))
            return build_response(dict(data=None, message=msg, code=200))
