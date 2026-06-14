# -*- coding: utf-8 -*-
"""Tests for SQL execution workflow.

Covers:
    - split_statements: statement boundary parsing
    - SqlData.post(): API endpoint for all execution modes
    - Error handling: empty SQL, invalid SQL, unknown modes, server errors
    - Result structure: query vs write vs empty result

These tests use Flask's test client and mock the MySQL connection so they
can run without a live database.
"""

import json

# third-party
from nose.tools import eq_, ok_, assert_raises

# project
from dashboard import app
from dashboard.server.utils import split_statements
from dashboard.server import utils


# ---------------------------------------------------------------------------
# split_statements unit tests (no DB needed)
# ---------------------------------------------------------------------------

def test_split_single_statement():
    stmts = split_statements('SELECT 1;')
    eq_(stmts, ['SELECT 1;'])


def test_split_multiple_statements():
    stmts = split_statements('SELECT 1; SELECT 2; SELECT 3;')
    eq_(len(stmts), 3)
    eq_(stmts[0], 'SELECT 1;')
    eq_(stmts[1], 'SELECT 2;')
    eq_(stmts[2], 'SELECT 3;')


def test_split_with_trailing_semicolon():
    stmts = split_statements('SELECT 1; SELECT 2;')
    eq_(len(stmts), 2)


def test_split_empty_string():
    eq_(split_statements(''), [])


def test_split_only_whitespace():
    eq_(split_statements('   \n  \t  '), [])


def test_split_only_semicolons():
    eq_(split_statements(';;;'), [])


def test_split_newline_separated():
    sql = 'SELECT 1;\nSELECT 2;\nSELECT 3;'
    stmts = split_statements(sql)
    eq_(len(stmts), 3)


def test_split_no_trailing_semicolon():
    stmts = split_statements('SELECT 1; SELECT 2')
    eq_(len(stmts), 2)
    eq_(stmts[1], 'SELECT 2')


def test_split_with_comments():
    sql = 'SELECT 1; -- comment\nSELECT 2;'
    stmts = split_statements(sql)
    ok_(len(stmts) >= 2)


def test_split_filters_blank_fragments():
    sql = '  ;  ;  SELECT 1;  ;  '
    stmts = split_statements(sql)
    eq_(len(stmts), 1)
    eq_(stmts[0], 'SELECT 1;')


def test_split_complex_statement():
    sql = ("SELECT a, b FROM t1 WHERE a > 10 AND b LIKE '%test%'; "
           "INSERT INTO t2 (x) VALUES (1);")
    stmts = split_statements(sql)
    eq_(len(stmts), 2)
    ok_('SELECT' in stmts[0].upper())
    ok_('INSERT' in stmts[1].upper())


# ---------------------------------------------------------------------------
# SqlData.post() API tests (mocked DB)
# ---------------------------------------------------------------------------

class MockCursor(object):
    """Mock MySQL cursor that returns configurable results."""
    def __init__(self, description=None, rows=None, rowcount=0):
        self.description = description
        self._rows = rows or []
        self.rowcount = rowcount

    def execute(self, sql):
        pass

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class MockConn(object):
    """Mock MySQL connection."""
    def __init__(self, cursor):
        self._cursor = cursor

    def stat(self):
        return 'alive'

    def cursor(self):
        return self._cursor

    def commit(self):
        pass


def _setup_mock(mock_cursor):
    """Replace the SQL singleton with a mock that returns the given cursor."""
    original_init = utils.SQL.__init__

    def mock_init(self, host, port, user, passwd, db):
        self.host = host
        self.port = port
        self.user = user
        self.passwd = passwd
        self.db = db
        self.conn = MockConn(mock_cursor)

    utils.SQL.__init__ = mock_init
    # Reset singleton so next call creates a fresh mock
    utils.SQL.instance = None
    return original_init


def _teardown_mock(original_init):
    """Restore original SQL.__init__ and reset singleton."""
    utils.SQL.__init__ = original_init
    utils.SQL.instance = None


def _post_sql(client, options, sql_raw):
    """Helper to POST to the SQL endpoint."""
    return client.post('/data/sql/',
                       data=json.dumps({'options': options, 'sql_raw': sql_raw}),
                       content_type='application/json')


def test_api_empty_sql():
    """Empty SQL should return warning, not crash."""
    with app.test_client() as c:
        resp = _post_sql(c, 'all', '')
        data = json.loads(resp.data)
        eq_(data['status'], 'warning')
        eq_(data['data'], None)


def test_api_whitespace_only():
    """Whitespace-only SQL should return warning."""
    with app.test_client() as c:
        resp = _post_sql(c, 'all', '   \n\t  ')
        data = json.loads(resp.data)
        eq_(data['status'], 'warning')


def test_api_format_empty():
    """Formatting empty SQL should return warning."""
    with app.test_client() as c:
        resp = _post_sql(c, 'format', '')
        data = json.loads(resp.data)
        eq_(data['status'], 'warning')


def test_api_format_valid_sql():
    """Format mode should return formatted SQL."""
    with app.test_client() as c:
        resp = _post_sql(c, 'format', 'select * from t where id=1')
        data = json.loads(resp.data)
        eq_(data['status'], 'success')
        ok_('SELECT' in data['data'])


def test_api_unknown_mode():
    """Unknown mode should return error."""
    with app.test_client() as c:
        resp = _post_sql(c, 'bogus', 'SELECT 1;')
        data = json.loads(resp.data)
        eq_(data['status'], 'error')
        ok_('Unknown' in data['message'] or 'unknown' in data['message'].lower())


def test_api_run_all_query():
    """'all' mode with a SELECT should return query results."""
    cursor = MockCursor(
        description=[('id',), ('name',)],
        rows=[(1, 'alice'), (2, 'bob')],
    )
    orig = _setup_mock(cursor)
    try:
        with app.test_client() as c:
            resp = _post_sql(c, 'all', 'SELECT * FROM users;')
            data = json.loads(resp.data)
            eq_(data['status'], 'success')
            ok_(data['data'] is not None)
            eq_(data['data']['status'], 'query')
            eq_(data['data']['row_count'], 2)
            ok_('id' in data['data']['data'])
            ok_('name' in data['data']['data'])
            ok_('elapsed' in data)
            eq_(data['exec_mode'], 'all')
    finally:
        _teardown_mock(orig)


def test_api_run_all_empty_result():
    """Query with 0 rows should return 'info' status."""
    cursor = MockCursor(
        description=[('id',), ('name',)],
        rows=[],
    )
    orig = _setup_mock(cursor)
    try:
        with app.test_client() as c:
            resp = _post_sql(c, 'all', 'SELECT * FROM empty_table;')
            data = json.loads(resp.data)
            eq_(data['status'], 'info')
            eq_(data['data'], None)
            ok_('0 rows' in data['message'])
    finally:
        _teardown_mock(orig)


def test_api_run_selected():
    """'selected' mode should work like 'all' but with selected text."""
    cursor = MockCursor(
        description=[('count',)],
        rows=[(42,)],
    )
    orig = _setup_mock(cursor)
    try:
        with app.test_client() as c:
            resp = _post_sql(c, 'selected', 'SELECT COUNT(*) FROM t;')
            data = json.loads(resp.data)
            eq_(data['status'], 'success')
            eq_(data['exec_mode'], 'selected')
    finally:
        _teardown_mock(orig)


def test_api_run_first_statement():
    """'first' mode should execute only the first statement."""
    cursor = MockCursor(
        description=[('val',)],
        rows=[(1,)],
    )
    orig = _setup_mock(cursor)
    try:
        with app.test_client() as c:
            resp = _post_sql(c, 'first', 'SELECT 1; SELECT 2; SELECT 3;')
            data = json.loads(resp.data)
            eq_(data['status'], 'success')
            eq_(data['exec_mode'], 'first')
    finally:
        _teardown_mock(orig)


def test_api_run_last_statement():
    """'last' mode should execute only the last statement."""
    cursor = MockCursor(
        description=[('val',)],
        rows=[(3,)],
    )
    orig = _setup_mock(cursor)
    try:
        with app.test_client() as c:
            resp = _post_sql(c, 'last', 'SELECT 1; SELECT 2; SELECT 3;')
            data = json.loads(resp.data)
            eq_(data['status'], 'success')
            eq_(data['exec_mode'], 'last')
    finally:
        _teardown_mock(orig)


def test_api_first_no_statements():
    """'first' with only semicolons should return warning."""
    with app.test_client() as c:
        resp = _post_sql(c, 'first', ';;;')
        data = json.loads(resp.data)
        eq_(data['status'], 'warning')
        ok_('No valid' in data['message'])


def test_api_sql_error():
    """MySQL error should return structured error, not 500."""
    cursor = MockCursor()

    def raise_on_execute(sql):
        raise Exception("You have an error in your SQL syntax")

    cursor.execute = raise_on_execute
    orig = _setup_mock(cursor)
    try:
        with app.test_client() as c:
            resp = _post_sql(c, 'all', 'SELEC BROKEN SQL;')
            data = json.loads(resp.data)
            eq_(data['status'], 'error')
            ok_('syntax' in data['message'].lower())
            ok_('elapsed' in data)
    finally:
        _teardown_mock(orig)


def test_api_write_operation():
    """INSERT/UPDATE should return write status with affected rows."""
    cursor = MockCursor(description=None, rowcount=5)
    orig = _setup_mock(cursor)
    try:
        with app.test_client() as c:
            resp = _post_sql(c, 'all', 'UPDATE t SET x=1 WHERE y>0;')
            data = json.loads(resp.data)
            eq_(data['status'], 'success')
            eq_(data['data']['status'], 'write')
            eq_(data['data']['row_count'], 5)
    finally:
        _teardown_mock(orig)


def test_api_no_json_body():
    """Request without JSON body should return error."""
    with app.test_client() as c:
        resp = c.post('/data/sql/',
                       data='not json',
                       content_type='text/plain')
        # Flask may return 400 or our custom error
        ok_(resp.status_code in (200, 400, 415))


def test_api_response_always_has_code():
    """All responses should include a 'code' field for build_response."""
    with app.test_client() as c:
        # warning path
        resp = _post_sql(c, 'all', '')
        data = json.loads(resp.data)
        ok_('code' in data)

        # format path
        resp = _post_sql(c, 'format', 'select 1')
        data = json.loads(resp.data)
        ok_('code' in data)

        # unknown mode
        resp = _post_sql(c, 'bogus', 'SELECT 1;')
        data = json.loads(resp.data)
        ok_('code' in data)
