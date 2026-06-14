# -*- coding: utf-8 -*-
"""Dashboard record contract.

Defines the canonical shape of dashboard meta and content records,
provides validation, safe JSON parsing, and default builders.

Meta structure:
    {"id": int, "name": str, "author": str, "time_modified": float}

Content structure:
    {"id": int, "name": str, "grid": {"0": <grid_item>, ...}}

Grid item structure:
    {"id": str, "x": int, "y": int, "width": int, "height": int,
     "key": str, "type": str, "option": {"x": [], "y": []},
     "graph_name": str}
"""
from __future__ import absolute_import

import json
import time

try:
    basestring
except NameError:
    # Python 3
    basestring = str


# ---------------------------------------------------------------------------
# Safe JSON parsing
# ---------------------------------------------------------------------------

def safe_json_loads(raw, default=None):
    """Parse a JSON string, returning *default* on None or corrupt input."""
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class ValidationError(Exception):
    """Raised when dashboard data fails validation."""

    def __init__(self, message, field=None):
        super(ValidationError, self).__init__(message)
        self.message = message
        self.field = field


def validate_meta(meta):
    """Validate a meta dict.  Raises :class:`ValidationError` on failure."""
    if not isinstance(meta, dict):
        raise ValidationError("Meta must be a dict")
    if "id" not in meta:
        raise ValidationError("Missing required field: id", field="id")
    name = meta.get("name")
    if not name or not isinstance(name, basestring):
        raise ValidationError("Name is required and must be a string",
                              field="name")
    if len(name) > 128:
        raise ValidationError("Name must be at most 128 characters",
                              field="name")
    author = meta.get("author")
    if not author or not isinstance(author, basestring):
        raise ValidationError("Author is required and must be a string",
                              field="author")


def validate_content(content):
    """Validate a content dict.  Raises :class:`ValidationError` on failure."""
    if not isinstance(content, dict):
        raise ValidationError("Content must be a dict")
    if "id" not in content:
        raise ValidationError("Missing required field: id", field="id")
    if "grid" not in content:
        raise ValidationError("Missing required field: grid", field="grid")
    if not isinstance(content["grid"], dict):
        raise ValidationError("Grid must be a dict", field="grid")


def validate_update_data(data):
    """Validate incoming PUT payload.  Raises :class:`ValidationError`."""
    if not isinstance(data, dict):
        raise ValidationError("Update data must be a dict")
    name = data.get("name")
    if name is not None:
        if not isinstance(name, basestring):
            raise ValidationError("Name must be a string", field="name")
        if len(name) > 128:
            raise ValidationError("Name must be at most 128 characters",
                                  field="name")


# ---------------------------------------------------------------------------
# Record builders
# ---------------------------------------------------------------------------

def build_meta(dash_id, name, author, time_modified=None):
    """Return a canonical meta dict."""
    return {
        "id": dash_id,
        "name": name,
        "author": author,
        "time_modified": time_modified if time_modified is not None else time.time(),
    }


def build_content(dash_id, name, grid=None):
    """Return a canonical content dict."""
    return {
        "id": dash_id,
        "name": name,
        "grid": grid if grid is not None else make_default_grid(),
    }


def make_default_grid():
    """Return the default 2x2 grid layout for a new dashboard."""
    positions = [
        {"x": 0, "y": 0, "width": 6, "height": 5},
        {"x": 6, "y": 0, "width": 6, "height": 5},
        {"x": 0, "y": 5, "width": 6, "height": 5},
        {"x": 6, "y": 5, "width": 6, "height": 5},
    ]
    grid = {}
    for i, pos in enumerate(positions):
        key = str(i)
        entry = dict(pos)
        entry.update({
            "key": "none",
            "type": "none",
            "option": {"x": [], "y": []},
            "graph_name": "graph name " + key,
            "id": key,
        })
        grid[key] = entry
    return grid
