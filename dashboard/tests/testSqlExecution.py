# -*- coding: utf-8 -*-

"""Tests for SQL execution workflow.

Covers:
- sqlparse.split() statement boundary parsing
- SQL.run() structured return values
- SqlData Flask endpoint for all execution modes

Run with: nosetests -s dashboard.tests.testSqlExecution
"""

# built-in package
import json

# third-party package
import sqlparse

# user-defined package
from dashboard import config
from dashboard.server import utils


# =============================================================================
# Tests for sqlparse.split() - statement boundary parsing
# =============================================================================

def test_sqlparse_split_single_statement():
    """Single statement should produce a list with one entry."""
    result = [s.strip() for s in sqlparse.split("SELECT 1;") if s.strip()]
    assert len(result) == 1
    assert 'SELECT' in result[0]


def test_sqlparse_split_multiple_statements():
    """Multiple statements separated by semicolons should split correctly."""
    sql = "SELECT 1; SELECT 2; SELECT 3;"
    result = [s.strip() for s in sqlparse.split(sql) if s.strip()]
    assert len(result) == 3
    assert '1' in result[0]
    assert '3' in result[-1]


def test_sqlparse_split_empty_string():
    """Empty string should produce no valid statements after filtering."""
    result = [s.strip() for s in sqlparse.split("") if s.strip()]
    assert len(result) == 0


def test_sqlparse_split_whitespace_only():
    """Whitespace-only string should produce no valid statements."""
    result = [s.strip() for s in sqlparse.split("   \n\t  ") if s.strip()]
    assert len(result) == 0


def test_sqlparse_split_trailing_semicolons():
    """Trailing/extra semicolons should not produce extra empty entries."""
    sql = "SELECT 1;; ; "
    result = [s.strip() for s in sqlparse.split(sql) if s.strip()]
    assert len(result) == 1
    assert 'SELECT' in result[0]


def test_sqlparse_split_first_last_extraction():
    """Verify first and last extraction from multi-statement SQL."""
    sql = "INSERT INTO t VALUES(1); SELECT * FROM t; DELETE FROM t WHERE id=1;"
    statements = [s.strip() for s in sqlparse.split(sql) if s.strip()]
    assert 'INSERT' in statements[0]
    assert 'DELETE' in statements[-1]


def test_sqlparse_split_no_trailing_semicolon():
    """Statement without trailing semicolon should still be captured."""
    sql = "SELECT 1; SELECT 2"
    result = [s.strip() for s in sqlparse.split(sql) if s.strip()]
    assert len(result) == 2


# =============================================================================
# Tests for SQL.run() - structured return values
# These tests require a live MySQL connection (same as testCreateData.py)
# =============================================================================

def _get_sql_conn():
    """Get a SQL connection using test config."""
    # Reset singleton to allow fresh connection
    utils.SQL.instance = None
    return utils.SQL(host=config.sql_host, port=config.sql_port,
                     user=config.sql_user, passwd=config.sql_pwd,
                     db=config.sql_db)


def test_sql_run_select():
    """SELECT should return success=True, type='select', data as dict."""
    conn = _get_sql_conn()
    result = conn.run("SELECT 1 AS num")
    assert result['success'] is True
    assert result['type'] == 'select'
    assert 'data' in result
    assert 'num' in result['data']


def test_sql_run_non_select():
    """Non-SELECT (DDL) should return success=True, type='execute', rowcount."""
    conn = _get_sql_conn()
    # Use a safe DDL that won't fail even if table doesn't exist
    conn.run("CREATE TABLE IF NOT EXISTS _test_sql_exec (id INT)")
    result = conn.run("INSERT INTO _test_sql_exec VALUES (1)")
    assert result['success'] is True
    assert result['type'] == 'execute'
    assert 'rowcount' in result
    assert result['rowcount'] >= 1
    # Cleanup
    conn.run("DROP TABLE IF EXISTS _test_sql_exec")


def test_sql_run_bad_query():
    """Invalid SQL should return success=False with error message."""
    conn = _get_sql_conn()
    result = conn.run("SELECTXYZ INVALID SQL")
    assert result['success'] is False
    assert 'error' in result
    assert len(result['error']) > 0


def test_sql_run_empty_result_set():
    """SELECT that returns no rows should still return success with empty data."""
    conn = _get_sql_conn()
    conn.run("CREATE TABLE IF NOT EXISTS _test_empty (id INT)")
    conn.run("DELETE FROM _test_empty")
    result = conn.run("SELECT * FROM _test_empty")
    assert result['success'] is True
    assert result['type'] == 'select'
    assert 'data' in result
    # Cleanup
    conn.run("DROP TABLE IF EXISTS _test_empty")


def test_sql_get_conn_reconnect():
    """After connection is closed, get_conn should reconnect."""
    conn = _get_sql_conn()
    # Forcibly close the underlying connection
    conn.conn.close()
    # get_conn should reconnect
    new_conn = conn.get_conn()
    # Verify connection is alive
    new_conn.stat()


# =============================================================================
# Tests for Flask endpoint - POST /data/sql/
# =============================================================================

def _get_test_client():
    """Get Flask test client."""
    from dashboard import app
    app.config['TESTING'] = True
    return app.test_client()


def test_post_format():
    """Format option should return formatted SQL without execution."""
    client = _get_test_client()
    payload = json.dumps({"sql_raw": "select * from t where id=1", "options": "format"})
    rv = client.post('/data/sql/', data=payload, content_type='application/json')
    data = json.loads(rv.data)
    assert data['code'] == 200
    assert 'SELECT' in data['data']
    assert 'FROM' in data['data']


def test_post_format_empty():
    """Format with empty SQL should return empty string."""
    client = _get_test_client()
    payload = json.dumps({"sql_raw": "", "options": "format"})
    rv = client.post('/data/sql/', data=payload, content_type='application/json')
    data = json.loads(rv.data)
    assert data['code'] == 200
    assert data['data'] == ''


def test_post_empty_sql_all():
    """All mode with empty SQL should return 400 error."""
    client = _get_test_client()
    payload = json.dumps({"sql_raw": "", "options": "all"})
    rv = client.post('/data/sql/', data=payload, content_type='application/json')
    data = json.loads(rv.data)
    assert data['code'] == 400
    assert 'error' in data


def test_post_empty_sql_selected():
    """Selected mode with empty SQL should return 400 error."""
    client = _get_test_client()
    payload = json.dumps({"sql_raw": "   ", "options": "selected"})
    rv = client.post('/data/sql/', data=payload, content_type='application/json')
    data = json.loads(rv.data)
    assert data['code'] == 400
    assert 'error' in data


def test_post_first_mode():
    """First mode should execute only the first statement."""
    client = _get_test_client()
    payload = json.dumps({
        "sql_raw": "SELECT 1 AS num; SELECT 2 AS num;",
        "options": "first"
    })
    rv = client.post('/data/sql/', data=payload, content_type='application/json')
    data = json.loads(rv.data)
    assert data['code'] == 200
    assert data['data'] is not None
    # Result should contain value 1 (first statement), not 2
    assert 1 in data['data']['num'].values()


def test_post_last_mode():
    """Last mode should execute only the last statement."""
    client = _get_test_client()
    payload = json.dumps({
        "sql_raw": "SELECT 1 AS num; SELECT 2 AS num;",
        "options": "last"
    })
    rv = client.post('/data/sql/', data=payload, content_type='application/json')
    data = json.loads(rv.data)
    assert data['code'] == 200
    assert data['data'] is not None
    # Result should contain value 2 (last statement), not 1
    assert 2 in data['data']['num'].values()


def test_post_unknown_option():
    """Unknown option should return 400 error."""
    client = _get_test_client()
    payload = json.dumps({"sql_raw": "SELECT 1", "options": "unknown"})
    rv = client.post('/data/sql/', data=payload, content_type='application/json')
    data = json.loads(rv.data)
    assert data['code'] == 400
    assert 'error' in data


def test_post_invalid_sql():
    """Invalid SQL should return 500 with error message."""
    client = _get_test_client()
    payload = json.dumps({"sql_raw": "INVALID SQL SYNTAX HERE", "options": "all"})
    rv = client.post('/data/sql/', data=payload, content_type='application/json')
    data = json.loads(rv.data)
    assert data['code'] == 500
    assert 'error' in data
    assert len(data['error']) > 0
