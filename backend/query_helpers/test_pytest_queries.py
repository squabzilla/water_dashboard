"""
file name: test_pytest_queries.py
author: William Hovdestad

Purpose: actually test that all my querying-PostGIS logic works - test this against `query_builders.py`
to be completed when I have the mental bandwidth to learn testing

Claude gave me some code, I need to actually look over it and make sure I understand it...
"""


########################################################################################################################
### script-setup 1: project-root-setup
import os
import sys
from pathlib import Path

# gets file-path, (hopefully) resolves relative path issues, gets great grand-parent folder
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# sets working directory to project root - there may be redundancy here but oh well lol
os.chdir(PROJECT_ROOT)
# Ensure repository code is importable when this wrapper is run directly.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
# get path for environment so I can load it later



########################################################################################################################
### script-setup 2: library imports
import pytest
from schema_constants import ColumnCategory
from schema_errors import FilterError
from backend.query_helpers.query_builders import build_where_clause


########################################################################################################################
### testing logic
# NOTE: copied from Claude, how does it work????????

# fake registry to test vs
FAKE_REGISTRY = {
    "watermain_breaks": {
        "break_date": ColumnCategory.DATE,
        "status": ColumnCategory.TEXT,
        "geom": ColumnCategory.GEOMETRY,
    }
}

def test_unknown_table_raises():
    with pytest.raises(FilterError):
        build_where_clause("nonexistent", {}, FAKE_REGISTRY)

def test_unknown_column_raises():
    with pytest.raises(FilterError):
        build_where_clause("watermain_breaks", {"nonsense": "x"}, FAKE_REGISTRY)

def test_geometry_column_rejected():
    with pytest.raises(FilterError):
        build_where_clause("watermain_breaks", {"geom__eq": "x"}, FAKE_REGISTRY)

def test_invalid_operator_for_category_raises():
    with pytest.raises(FilterError):
        build_where_clause("watermain_breaks", {"status__gt": "x"}, FAKE_REGISTRY)  # TEXT has no gt

def test_default_operator_is_eq():
    where_sql, params = build_where_clause("watermain_breaks", {"status": "active"}, FAKE_REGISTRY)
    assert "status = :p0" in where_sql
    assert params == {"p0": "active"}

def test_no_filters_returns_true():
    where_sql, params = build_where_clause("watermain_breaks", {}, FAKE_REGISTRY)
    assert where_sql == "TRUE"
    assert params == {}

def test_invalid_date_value_raises():
    with pytest.raises(FilterError):
        build_where_clause("watermain_breaks", {"break_date__gte": "not-a-date"}, FAKE_REGISTRY)

def test_valid_date_value_passes():
    where_sql, params = build_where_clause("watermain_breaks", {"break_date__gte": "2020-01-01"}, FAKE_REGISTRY)
    assert "break_date >= :p0" in where_sql
    assert params == {"p0": "2020-01-01"}

def test_date_validation_only_applies_to_date_columns():
    # a TEXT column with a non-date value should NOT raise — the check is DATE-only
    where_sql, params = build_where_clause("watermain_breaks", {"status": "not-a-date"}, FAKE_REGISTRY)
    assert params == {"p0": "not-a-date"}