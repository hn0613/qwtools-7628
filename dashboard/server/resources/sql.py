# -*- coding: utf-8 -*-

# built-in package
import time

# third-party package
import sqlparse
from flask.ext.restful import Resource
from flask import request, make_response, render_template

# user-defined package
from dashboard import config
from ..utils import build_response, SQL, split_statements


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

            {"options": "all" | "selected" | "first" | "last" | "format",
             "sql_raw": "raw sql ..."}

        Execution modes:
            all      - execute entire editor content as one call
            selected - execute only the highlighted text
            first    - split by semicolons, execute the first non-empty statement
            last     - split by semicolons, execute the last non-empty statement
            format   - format SQL (uppercase keywords, re-indent), no execution

        Returns:
            JSON response with structure:
                status:  'success' | 'error' | 'warning' | 'info'
                data:    query result dict, None, or formatted SQL string
                message: human-readable description
                ...
        '''
        data = request.get_json()
        if not data:
            return build_response(dict(
                status='error', data=None, code=400,
                message='No request data received'))

        options = data.get('options', '')
        sql_raw = data.get('sql_raw', '')

        # --- Format (no execution) ---
        if options == 'format':
            if not sql_raw or not sql_raw.strip():
                return build_response(dict(
                    status='warning', data=None, code=200,
                    message='No SQL content to format'))
            sql_formatted = sqlparse.format(
                sql_raw, keyword_case='upper', reindent=True)
            return build_response(dict(
                status='success', data=sql_formatted, code=200,
                message='SQL formatted'))

        # --- Validate: non-format modes require content ---
        if not sql_raw or not sql_raw.strip():
            return build_response(dict(
                status='warning', data=None, code=200,
                message='No SQL to execute'))

        # --- Determine which SQL to run ---
        start_time = time.time()
        sql_to_run = None
        exec_mode = options

        if options in ('first', 'last'):
            statements = split_statements(sql_raw)
            if not statements:
                return build_response(dict(
                    status='warning', data=None, code=200,
                    message='No valid SQL statements found'))
            sql_to_run = statements[0] if options == 'first' else statements[-1]
        elif options in ('all', 'selected'):
            sql_to_run = sql_raw
        else:
            return build_response(dict(
                status='error', data=None, code=400,
                message='Unknown execution mode: {}'.format(options)))

        # --- Execute ---
        try:
            conn = SQL(config.sql_host, config.sql_port, config.sql_user,
                       config.sql_pwd, config.sql_db)
            result = conn.run(sql_to_run)
            elapsed = round(time.time() - start_time, 3)

            if result['status'] == 'query' and result['row_count'] == 0:
                return build_response(dict(
                    status='info', data=None, code=200,
                    message='Query returned 0 rows',
                    exec_mode=exec_mode, elapsed=elapsed,
                    sql_preview=sql_to_run[:200]))

            return build_response(dict(
                status='success', data=result, code=200,
                message='Query returned {} row(s)'.format(result['row_count']),
                exec_mode=exec_mode, elapsed=elapsed,
                sql_preview=sql_to_run[:200]))

        except Exception as e:
            elapsed = round(time.time() - start_time, 3)
            return build_response(dict(
                status='error', data=None, code=200,
                message=str(e),
                exec_mode=exec_mode, elapsed=elapsed,
                sql_preview=sql_to_run[:200]))