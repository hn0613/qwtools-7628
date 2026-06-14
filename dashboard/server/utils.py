# -*- coding: utf-8 -*-

# built-in package
import os
import time
import json
import random
from functools import wraps

# third-party package
import MySQLdb
import pandas as pd
import sqlparse
from flask import make_response, jsonify

# user-defined package


def build_response(content, code=200):
    """Build response, add headers"""
    response = make_response( jsonify(content), content['code'] )
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = \
            'Origin, X-Requested-With, Content-Type, Accept, Authorization'
    return response


color_set = {
    "red": u"\033[1;31m{}\033[0m", "green": u"\033[1;32m{}\033[0m",
    "yellow":u"\033[1;33m{}\033[0m", "blue": u"\033[1;34m{}\033[0m",
    "magenta": u"\033[1;35m{}\033[0m", "cyan": u"\033[1;36m{}\033[0m",
    "white": u"\033[1;37m{}\033[0m",
}


def print_info(text, color='white', kill=False):
    global color_set
    print 'color:', color  # for debug from logfile
    template = color_set.get(color)
    print template.format(text)
    if kill:
        exit(-1)

'''
# A simple wrapper, print func name when been executed.
'''
def print_func_name(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        print '\n###start run fun:  {} ...'.format(func.__name__)
        result = func(*args, **kwargs)
        print '\n###finish run fun:  {} ...'.format(func.__name__)
        return result
    return wrapper


class Map(dict):
    """
    Example:
    m = Map({'first_name': 'Eduardo'}, last_name='Pool', age=24, sports=['Soccer'])
    # Add new key
    m.new_key = 'Hello world!'
    # Or
    m['new_key'] = 'Hello world!'
    print m.new_key
    print m['new_key']
    # Update values
    m.new_key = 'Yay!'
    # Or
    m['new_key'] = 'Yay!'
    # Delete key
    del m.new_key
    # Or
    del m['new_key']
    """
    def __init__(self, *args, **kwargs):
        super(Map, self).__init__(*args, **kwargs)
        for arg in args:
            if isinstance(arg, dict):
                for k, v in arg.iteritems():
                    self[k] = v
        if kwargs:
            for k, v in kwargs.iteritems():
                self[k] = v

    def __getattr__(self, attr):
        return self.get(attr)

    def __setattr__(self, key, value):
        self.__setitem__(key, value)

    def __setitem__(self, key, value):
        super(Map, self).__setitem__(key, value)
        self.__dict__.update({key: value})

    def __delattr__(self, item):
        self.__delitem__(item)

    def __delitem__(self, key):
        super(Map, self).__delitem__(key)
        del self.__dict__[key]


class Singleton(type):
    def __init__(cls, name, bases, dict):
        super(Singleton, cls).__init__(name, bases, dict)
        cls.instance = None

    def __call__(cls,*args,**kw):
        if cls.instance is None:
            cls.instance = super(Singleton, cls).__call__(*args, **kw)
        return cls.instance


class SQL(object):
    __metaclass__ = Singleton

    """MySQL connection wrapper with reconnect and write-operation support."""
    def __init__(self, host, port, user, passwd, db):
        super(SQL, self).__init__()
        self.host = host
        self.port = port
        self.user = user
        self.passwd = passwd
        self.db = db
        self.conn = MySQLdb.connect(host=host, port=port, user=user,
                                    passwd=passwd, db=db)

    def get_conn(self):
        try:
            self.conn.stat()
        except:
            self.conn = MySQLdb.connect(host=self.host, port=self.port,
                                        user=self.user, passwd=self.passwd,
                                        db=self.db)
        return self.conn

    def run(self, sql):
        """Execute SQL and return a structured result dict.

        Returns:
            dict with keys:
                status: 'query' | 'write'
                data:   column-oriented dict (query) or None (write)
                columns: list of column names (query) or [] (write)
                row_count: number of result rows (query) or affected rows (write)
        """
        self.get_conn()
        cursor = self.conn.cursor()
        cursor.execute(sql)

        if cursor.description:
            columns = [desc[0] for desc in cursor.description]
            result = cursor.fetchall()
            cursor.close()
            frame = pd.DataFrame.from_records(list(result), columns=columns)
            return {
                'status': 'query',
                'data': frame.to_dict(),
                'columns': columns,
                'row_count': len(result),
            }
        else:
            affected = cursor.rowcount
            self.conn.commit()
            cursor.close()
            return {
                'status': 'write',
                'data': None,
                'columns': [],
                'row_count': affected,
            }


def split_statements(sql_text):
    """Split SQL text into individual non-empty statements.

    Uses sqlparse to split by semicolons, then filters out blank fragments.

    Returns:
        list of stripped, non-empty SQL statement strings.
    """
    parts = sqlparse.split(sql_text)
    return [s.strip() for s in parts if s.strip()]
