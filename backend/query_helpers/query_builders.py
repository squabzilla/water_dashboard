"""
file name: query_builders.py
author: William Hovdestad

This file functions four query-related functions:

1. load_schema_registry
This function contains logic to return the schema of my database in the form of a nested dictionary
registry = {table_name {column_name: column_type} }
    The keys on the outside-dict are all the valid tables in my database, 
and the inner-dict is the values of the outer-dict.
    The inner-dict keys are all the columns belonging to a given table
and the values of the inner-dict are the (Python) data-types of a specific column

2. build_where_clause
This function builds a "WHERE" clause for SQL, including setting up the use of placeholder values
to prevent SQL injections.
This functionally lets us add parameters to a query - in otherwords, make a filtered query (instead of all tables)

3. get_geometry_column
This function gets passed a table name, cross-references the scheme registry created in step 1,
and returns the geometry column of a table
(later logic depends on knowing this column)

4. execute_scalar
Idk what it's called this, but this basically wraps the first half of a query
(made in our endpoints in `backend/query_helpers/main.py`)
and the WHERE class, made by the `build_where_clause` function,
slaps them together, then unwraps the weird way that SQL packages up JSONs/GeoJSONs.
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
from sqlalchemy import Connection, text

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
def load_schema_registry(conn: Connection) -> dict[str, dict[str, ColumnCategory]]:
    known_tables = list(KNOWN_TABLES) # get my known-tables-tuple, make into list
    with conn: # with-statement so it's not like, permanent on?
        rows = conn.execute(
            text("""
                SELECT table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = ANY(:known_tables)
            """),
            {"known_tables": known_tables},
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
    # example output:
    """
    {
        table_1: {
            col_1: type,
            col_2: type
        },
        table_2 {
            col_1: type,
            col_2: type
        }
    }
    """
    # NOTE: the output often looks weird, e.g.: {'weather_stations': {'geometry': <ColumnCategory.GEOMETRY: 'geometry'>}}
    # while there's weirdness in the way it stores and looks, it ALSO guarantees that all the column-types
    # are one of the 5 defined in: class ColumnCategory
    # and it still functions fine



########################################################################################################################
### section 2: build_where_clause



# def build_where_clause(table, filters, registry) -> tuple[str, list]: pass

def build_where_clause(
        table: str, # name of table - a basic string, which is then validated against the schema that `load_schema` made
        filters: dict[str, str], # requested filters in the form `"column__op": "value"`, which is later split into 3 parts: collumn, op, value
        registry: dict[str, dict[str, ColumnCategory]] # this imports the output of `load_schema`, but passed instead of called
    ) -> tuple[str, dict[str, str]]: # python returns an SQL-string and dictionary of placeholder values, packed together as a tuple

    """filters: {'column__op': 'value'} or {'column': 'value'}, e.g. {'break_date__gte': '2020-01-01'} or {'break_date': '2020-01-01'"""

    # remember that registry is the output of `load_schema_registry` so it's the full schema of valid items in my DB
    table_schema = registry.get(table) # .get() method retrieves value of key, but returns None instead of ERROR if key not found
    if table_schema is None: # however, we DO want an error if key not found, just a more explicit one lol
        raise FilterError(f"unknown table '{table}'")

    clauses: list[str] = [] # empty list for clauses that we'll `.join` together
    placeholders: dict[str, str] = {} # empty dict for placeholder values # NOTE: used to be called 'params'
    for i, (key, value) in enumerate(filters.items()):
        column, _, op = key.partition("__") # turn `column__op` into: `column="column"; _="__"; op="op"`
        # NOTE: in the case of `{'column': 'value'}`, `_` and `op` will equal "", or empty-string

        # set op to default equal 'eq' if it wasn't defined
        if op == '': op = 'eq' # could also do `op = op or "eq"`, but I understand the if-statement better
        # according to "API Query Design Choice" section in Backend_README.md, 
        # if a `column` name by itself (that does not include the '__op' portion),
        # then the operation is implicitly assumed to be equals, or `eq`

        column_category = table_schema.get(column)
        if column_category is None: # error if we can't find the column
            raise FilterError(f"unknown column '{column}' on '{table}'")
        if column_category == ColumnCategory.GEOMETRY: # we can't filter GEOM columns, so ERROR if it's passed one
            raise FilterError(f"column '{column}' is a geometry column, not filterable this way")
        if op not in OPERATORS_BY_COLUMN_CATEGORY[column_category]: # error if we aren't using a valid operator for the column-type
            raise FilterError(f"operator '{op}' not valid for column '{column}' (type={column_category})")

        # create portion of SQL-clause, using placeholder syntax to prevent SQL-injection
        temp_placeholder = f"p{i}"
        clauses.append(f"{column} {OPERATOR_TO_SQL_SYMBOL[op]} %s")  # column validated against registry above
        placeholders[temp_placeholder] = value
        # this sets things up for the SQLAlchemy Connection method for placeholders to prevent SQL-injections

        # NOTE: 
        # at this point, `column` has been confirmed to be an existing column in the registry
        # `op` has been confirmed to be valid operator for column type, and was translated to valid SQL symbol via OPERATOR_TO_SQL_SYMBOL

    where_sql = " AND ".join(clauses) if clauses else "TRUE"
    # `where_sql` becomes an sql string with placeholders in it, such as: `break_date >= %s AND status = %s` (remember %s are placeholders)
    # `placeholders` holds the list of values for the placeholders, in the same order they appear
    # this lets us sanitze our SQL-input - very important!
    return where_sql, placeholders # in python, a return statement with multiple objects packs them together into a tuple
    # NOTE: when calling the function, the easiest way to unpack it is calling it as: 
    # "where_sql, placeholders = build_where_clause(table, filters, registry)" 



########################################################################################################################
### section 3: get_geometry_column(table)
def get_geometry_column(
        table_name: str,
        registry: dict[str, dict[str, ColumnCategory]] # this imports the output of `load_schema`, but passed instead of called
    ) -> str:
    # remember that registry is the output of `load_schema_registry` so it's the full schema of valid items in my DB
    table_schema = registry.get(table_name) # .get() method retrieves value of key, but returns None instead of ERROR if key not found
    if table_schema is None: # however, we DO want an error if key not found, just a more explicit one lol
        raise FilterError(f"unknown table '{table_name}'")
    geometry_column = "" # placeholder for geometry column

    # loop through col-dict to find geometry column
    for key, value in registry.items():
        column_name = key
        column_category = value
        if column_category == ColumnCategory.GEOMETRY:
            geometry_column = column_name
            break # break once we find it
    # error message if not found
    if geometry_column == "": # this means its not found
            msg = f"Error: SchemaError: could not find GEOMETRY column for table {table_name}."
            logger.error(msg)
            raise SchemaError(msg)
    # return found geometry column
    return geometry_column



########################################################################################################################
### section 4: shorthand to execute SQL and extract JSON from JSONB-dict-thing

#def execute_scalar(conn, sql_command: str, params: Sequence | None = None) -> dict:
def execute_scalar(conn: Connection, sql_command: str, sql_placeholder_values: dict[str, str] | None = None) -> dict:
    with conn:
        row = conn.execute(
            text(sql_command), sql_placeholder_values
        ).fetchone() # NOTE: will return None if it doesn't found results
        # row = conn.fetchone() # NOTE: will return None if it doesn't found results
        return row[0] if row else {"type": "FeatureCollection", "features": []}
        if row: output = row[0] # output is `row[0]` assuming `fetchone` found something, and didn't return None
        else: output = {"type": "FeatureCollection", "features": []} # this is what we return if `fetchone` gave us None
        return output