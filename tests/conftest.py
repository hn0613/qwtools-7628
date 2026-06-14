# -*- coding: utf-8 -*-
"""Shared test fixtures and mock setup for dashboard tests.

This conftest sets up mock objects for all dashboard dependencies (Flask,
Redis, MySQL) so that tests can run without those packages installed.
"""

import sys
import os
import types
from unittest import mock


def _make_mock_redis():
    """Create a mock Redis connection with realistic in-memory state."""
    r = mock.MagicMock()
    _data = {
        'hashes': {},
        'sorted_sets': {},
        'strings': {},
    }

    def _exists(key):
        return key in _data['hashes'] or key in _data['sorted_sets'] or key in _data['strings']

    def _incr(key):
        val = int(_data['strings'].get(key, 0)) + 1
        _data['strings'][key] = str(val)
        return val

    def _set(key, value):
        _data['strings'][key] = str(value)
        return True

    def _get(key):
        return _data['strings'].get(key)

    def _hget(hash_key, field):
        h = _data['hashes'].get(hash_key, {})
        return h.get(str(field))

    def _hset(hash_key, field, value):
        if hash_key not in _data['hashes']:
            _data['hashes'][hash_key] = {}
        _data['hashes'][hash_key][str(field)] = value
        return 1

    def _hdel(hash_key, field):
        h = _data['hashes'].get(hash_key, {})
        if str(field) in h:
            del h[str(field)]
            return 1
        return 0

    def _hexists(hash_key, field):
        h = _data['hashes'].get(hash_key, {})
        return str(field) in h

    def _hmget(hash_key, fields):
        h = _data['hashes'].get(hash_key, {})
        return [h.get(str(f)) for f in fields]

    def _zadd(ss_key, member, score):
        if ss_key not in _data['sorted_sets']:
            _data['sorted_sets'][ss_key] = {}
        _data['sorted_sets'][ss_key][str(member)] = float(score)
        return 1

    def _zrem(ss_key, member):
        ss = _data['sorted_sets'].get(ss_key, {})
        if str(member) in ss:
            del ss[str(member)]
            return 1
        return 0

    def _zscore(ss_key, member):
        ss = _data['sorted_sets'].get(ss_key, {})
        return ss.get(str(member))

    def _zrevrange(ss_key, start, end, withscores=False):
        ss = _data['sorted_sets'].get(ss_key, {})
        items = sorted(ss.items(), key=lambda x: x[1], reverse=True)
        if end == -1:
            sliced = items[start:]
        else:
            sliced = items[start:end + 1]
        if withscores:
            return sliced
        return [m for m, s in sliced]

    def _zcount(ss_key, min_score, max_score):
        ss = _data['sorted_sets'].get(ss_key, {})
        return len(ss)

    def _keys(pattern='*'):
        return list(_data['strings'].keys())

    class MockPipeline(object):
        def __init__(self):
            self._ops = []

        def zadd(self, ss_key, member, score):
            self._ops.append(('zadd', ss_key, member, score))
            return self

        def hset(self, hash_key, field, value):
            self._ops.append(('hset', hash_key, field, value))
            return self

        def hdel(self, hash_key, field):
            self._ops.append(('hdel', hash_key, field))
            return self

        def zrem(self, ss_key, member):
            self._ops.append(('zrem', ss_key, member))
            return self

        def execute(self):
            results = []
            for op in self._ops:
                if op[0] == 'zadd':
                    results.append(_zadd(op[1], op[2], op[3]))
                elif op[0] == 'hset':
                    results.append(_hset(op[1], op[2], op[3]))
                elif op[0] == 'hdel':
                    results.append(_hdel(op[1], op[2]))
                elif op[0] == 'zrem':
                    results.append(_zrem(op[1], op[2]))
            self._ops = []
            return results

    def _pipeline():
        return MockPipeline()

    r.exists = mock.MagicMock(side_effect=_exists)
    r.incr = mock.MagicMock(side_effect=_incr)
    r.set = mock.MagicMock(side_effect=_set)
    r.get = mock.MagicMock(side_effect=_get)
    r.hget = mock.MagicMock(side_effect=_hget)
    r.hset = mock.MagicMock(side_effect=_hset)
    r.hdel = mock.MagicMock(side_effect=_hdel)
    r.hexists = mock.MagicMock(side_effect=_hexists)
    r.hmget = mock.MagicMock(side_effect=_hmget)
    r.zadd = mock.MagicMock(side_effect=_zadd)
    r.zrem = mock.MagicMock(side_effect=_zrem)
    r.zscore = mock.MagicMock(side_effect=_zscore)
    r.zrevrange = mock.MagicMock(side_effect=_zrevrange)
    r.zcount = mock.MagicMock(side_effect=_zcount)
    r.keys = mock.MagicMock(side_effect=_keys)
    r.pipeline = mock.MagicMock(side_effect=_pipeline)

    return r, _data


# Only set up mocks if dashboard isn't already importable
_project_root = os.path.join(os.path.dirname(__file__), '..')
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

try:
    import dashboard
    _has_dashboard = True
except ImportError:
    _has_dashboard = False

if not _has_dashboard:
    # Create mock Redis instances
    _mock_r_kv, _ = _make_mock_redis()
    _mock_r_db, _mock_db_data = _make_mock_redis()

    # Create mock config
    _mock_config = types.ModuleType('dashboard.conf.config')
    _mock_config.redis_kv_host = 'localhost'
    _mock_config.redis_kv_port = 6379
    _mock_config.redis_kv_db = 0
    _mock_config.redis_db_host = 'localhost'
    _mock_config.redis_db_port = 6379
    _mock_config.redis_db_db = 1
    _mock_config.app_host = '127.0.0.1:9090'
    _mock_config.DASH_ID_KEY = "dash_id"
    _mock_config.DASH_META_KEY = "dash_meta"
    _mock_config.DASH_CONTENT_KEY = "dash_content"
    _mock_config.DASH_DELETED_KEY = "dash_deleted"
    _mock_config.DASH_SEQ_KEY = "dash_seq"
    _mock_config.sql_type = 'mysql'
    _mock_config.sql_host = 'localhost'
    _mock_config.sql_port = 3306
    _mock_config.sql_user = 'test'
    _mock_config.sql_pwd = 'test'
    _mock_config.sql_db = 'test'
    _mock_config.logger = mock.MagicMock()

    # Build proper mock package hierarchy using real types.ModuleType
    # so Python's import system can traverse them
    _dashboard_pkg = types.ModuleType('dashboard')
    _dashboard_pkg.__path__ = [os.path.join(_project_root, 'dashboard')]
    _dashboard_pkg.r_kv = _mock_r_kv
    _dashboard_pkg.r_db = _mock_r_db
    _dashboard_pkg.config = _mock_config
    _dashboard_pkg.log = _mock_config.logger
    _dashboard_pkg.app = mock.MagicMock()
    _dashboard_pkg.api = mock.MagicMock()

    _conf_pkg = types.ModuleType('dashboard.conf')
    _conf_pkg.__path__ = [os.path.join(_project_root, 'dashboard', 'conf')]
    _conf_pkg.config = _mock_config

    _server_pkg = types.ModuleType('dashboard.server')
    _server_pkg.__path__ = [os.path.join(_project_root, 'dashboard', 'server')]

    _resources_pkg = types.ModuleType('dashboard.server.resources')
    _resources_pkg.__path__ = [os.path.join(_project_root, 'dashboard', 'server', 'resources')]

    _client_pkg = types.ModuleType('dashboard.client')
    _client_pkg.__path__ = [os.path.join(_project_root, 'dashboard', 'client')]

    # Mock third-party modules that might not be installed
    # Only mock if they're not already importable
    _third_party_mocks = [
        'flask.ext', 'flask.ext.restful',
        'redis', 'MySQLdb', 'pandas', 'numpy',
        'sqlparse', 'pygments', 'pygments.lexers',
        'pygments.formatters'
    ]
    for mod_name in _third_party_mocks:
        if mod_name not in sys.modules:
            try:
                __import__(mod_name)
            except ImportError:
                sys.modules[mod_name] = mock.MagicMock()

    # Handle flask_restful / flask.ext.restful specifically
    if 'flask_restful' not in sys.modules:
        try:
            import flask_restful as _real_fr
            sys.modules['flask_restful'] = _real_fr
            # Also set flask.ext.restful to point to the real module
            sys.modules['flask.ext'] = mock.MagicMock()
            sys.modules['flask.ext.restful'] = _real_fr
        except ImportError:
            sys.modules['flask_restful'] = mock.MagicMock()
            sys.modules['flask.ext'] = mock.MagicMock()
            sys.modules['flask.ext.restful'] = mock.MagicMock()
    else:
        # flask_restful is already imported (real), make flask.ext.restful point to it
        sys.modules['flask.ext'] = mock.MagicMock()
        sys.modules['flask.ext.restful'] = sys.modules['flask_restful']

    # For flask_restful, provide a Resource base class if mocked
    _mock_restful = sys.modules.get('flask_restful')
    if not hasattr(_mock_restful, 'Resource'):
        _mock_restful.Resource = type('Resource', (), {})

    # Register mock modules
    sys.modules['dashboard'] = _dashboard_pkg
    sys.modules['dashboard.conf'] = _conf_pkg
    sys.modules['dashboard.conf.config'] = _mock_config
    sys.modules['dashboard.server'] = _server_pkg
    sys.modules['dashboard.server.resources'] = _resources_pkg
    sys.modules['dashboard.client'] = _client_pkg


# Expose for tests
def get_mock_redis():
    """Return a fresh mock Redis instance for tests."""
    return _make_mock_redis()
