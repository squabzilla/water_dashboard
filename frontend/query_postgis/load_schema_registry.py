"""
file name: main.y
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


########################################################################################################################
### script-setup 3: logging config
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING) # STOP LOGGING EVERY API CALL DAMNIT



########################################################################################################################
### section 1: setup some classes and stuff

# let's declare an error type for schema registry
class SchemaError(Exception):
    """Base class for backfill-related failures."""

# class containing all the data types I care about in Python code
class ColumnCategory(StrEnum):
    TEXT = "text"
    NUMERIC = "numeric"
    DATE = "date"
    BOOLEAN = "boolean"
    GEOMETRY = "geometry"

# a MappingProxyType, that maps all the various PostGres data types to my Python data-types
PG_TYPES_TO_COLUMN_CATEGORY: MappingProxyType[str, ColumnCategory] = MappingProxyType({
    "text": ColumnCategory.TEXT, "varchar": ColumnCategory.TEXT, "character varying": ColumnCategory.TEXT,
    "integer": ColumnCategory.NUMERIC, "bigint": ColumnCategory.NUMERIC, "numeric": ColumnCategory.NUMERIC,
    "double precision": ColumnCategory.NUMERIC, "real": ColumnCategory.NUMERIC,
    "date": ColumnCategory.DATE, "timestamp": ColumnCategory.DATE,
    "timestamp without time zone": ColumnCategory.DATE, "timestamp with time zone": ColumnCategory.DATE,
    "boolean": ColumnCategory.BOOLEAN,
    "USER-DEFINED": ColumnCategory.GEOMETRY,  # PostGIS geometry shows as USER-DEFINED
})

#   This function returns a nested-dict representing the schema of my database.
#   The keys on the outside-dict are all the valid tables in my database, 
# and the inner-dict is the values of the outer-dict.
#   The inner-dict keys are all the columns belonging to a given table
# and the values of the inner-dict are the (Python) data-types of a specific column
def load_schema_registry(conn) -> dict[str, dict[str, ColumnCategory]]:
    rows = conn.execute("""
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
    """).fetchall()

    # create empty registry
    # the type annotation here just reminds us what it's supposed to look like
    registry: dict[str, dict[str, ColumnCategory]] = {}

    for table_name, column_name, data_type in rows:
        # make sure table is in registry - add table_name as empty-dict if not there
        if table_name not in registry: registry[table_name] = {}
        # get data type of column
        ColCategory = PG_TYPES_TO_COLUMN_CATEGORY.get(data_type)
        # error and quit if bad data-type
        if ColCategory is None:
            msg = f"Error: SchemaError: table {table_name} column {column_name}: unknown data type."
            logger.error(msg)
            raise SchemaError(msg)
        # add column-name and column-type now
        registry[table_name][column_name] = ColCategory
    # done for-loop, now return registry
    return registry