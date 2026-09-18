"""
file name: load_schema_registry.py
author: William Hovdestad

this file contains logic to return the schema of my database in the form of a nested dictionary
registry = {table_name {column_name: column_type} }
    The keys on the outside-dict are all the valid tables in my database, 
and the inner-dict is the values of the outer-dict.
    The inner-dict keys are all the columns belonging to a given table
and the values of the inner-dict are the (Python) data-types of a specific column
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
from datetime import datetime # for getting date-time stuff
import logging
from enum import StrEnum
from types import MappingProxyType
from fastapi import FastAPI
import psycopg # stuff needed to connect with postgis database
import sqlalchemy # stuff needed to connect with postgis database
import httpx # used for calling API
import json # used for handling export of json data

from data_pipeline.helper.helper_SQL_tables import DatabaseTables
from backend.query_helpers.schema_errors import SchemaError, FilterError
from backend.query_helpers.schema_constants import \
    ColumnCategory, KNOWN_TABLES, PG_TYPE_TO_CATEGORY, OPERATORS_BY_COLUMN_CATEGORY, OPERATOR_TO_SQL_SYMBOL


########################################################################################################################
### script-setup 3: logging config
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING) # STOP LOGGING EVERY API CALL DAMNIT



########################################################################################################################
### section 1: load_schema_registry

#   This function returns a nested-dict representing the schema of my database.
#   The keys on the outside-dict are all the valid tables in my database, 
# and the inner-dict is the values of the outer-dict.
#   The inner-dict keys are all the columns belonging to a given table
# and the values of the inner-dict are the (Python) data-types of a specific column
def load_schema_registry(conn) -> dict[str, dict[str, ColumnCategory]]:
    known_tables = KNOWN_TABLES
    rows = conn.execute(
        """
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = ANY(%s)
        """,
        (known_tables,),
    ).fetchall()

    # create empty registry
    # the type annotation here just reminds us what it's supposed to look like
    registry: dict[str, dict[str, ColumnCategory]] = {}

    for table_name, column_name, data_type in rows: # note: loops through each "row" and grabs 3 values from said row
        # make sure table is in registry - add table_name as empty-dict if not there
        if table_name not in registry: registry[table_name] = {}
        # get data type of column
        column_category = PG_TYPE_TO_CATEGORY.get(data_type)
        # error and quit if bad data-type
        if column_category is None:
            msg = f"Error: SchemaError: table {table_name} column {column_name}: unknown data type."
            logger.error(msg)
            raise SchemaError(msg)
        # add column-name and column-type now
        registry[table_name][column_name] = column_category
    # done for-loop, now return registry
    return registry



########################################################################################################################
### section 2: build_where_clause



# def build_where_clause(table, filters, registry) -> tuple[str, list]: pass

def build_where_clause(
        table: str, filters: dict[str, str], registry: dict[str, dict[str, ColumnCategory]]
    ) -> tuple[str, list[str]]:

    """filters: {'column__op': 'value'}, e.g. {'break_date__gte': '2020-01-01'}"""

    table_schema = registry.get(table)
    if table_schema is None:
        raise FilterError(f"unknown table '{table}'")

    clauses, params = [], []
    for key, value in filters.items():
        column, _, op = key.partition("__")
        op = op or "eq"

        column_category = table_schema.get(column)
        if column_category is None:
            raise FilterError(f"unknown column '{column}' on '{table}'")
        if column_category == ColumnCategory.GEOMETRY:
            raise FilterError(f"column '{column}' is a geometry column, not filterable this way")
        if op not in OPERATORS_BY_COLUMN_CATEGORY[column_category]:
            raise FilterError(f"operator '{op}' not valid for column '{column}' (type={column_category})")

        clauses.append(f"{column} {OPERATOR_TO_SQL_SYMBOL[op]} %s")  # column validated against registry above
        params.append(value)

    where_sql = " AND ".join(clauses) if clauses else "TRUE"
    return where_sql, params