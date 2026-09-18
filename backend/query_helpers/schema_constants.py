"""
Name: schema_constants.py
Author: William Hovdestad

Purpose:
This file holds constant values for any of my scheme and query logic functions
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



########################################################################################################################
### section 1: setup some classes and stuff

# class containing all the data types I care about in Python code
class ColumnCategory(StrEnum):
    TEXT = "text"
    NUMERIC = "numeric"
    DATE = "date"
    BOOLEAN = "boolean"
    GEOMETRY = "geometry"

# a MappingProxyType, that maps all the various PostGres data types to my Python data-types
PG_TYPE_TO_CATEGORY: MappingProxyType[str, ColumnCategory] = MappingProxyType({
    "text": ColumnCategory.TEXT, "varchar": ColumnCategory.TEXT, "character varying": ColumnCategory.TEXT,
    "integer": ColumnCategory.NUMERIC, "bigint": ColumnCategory.NUMERIC, "numeric": ColumnCategory.NUMERIC,
    "double precision": ColumnCategory.NUMERIC, "real": ColumnCategory.NUMERIC,
    "date": ColumnCategory.DATE, "timestamp": ColumnCategory.DATE,
    "timestamp without time zone": ColumnCategory.DATE, "timestamp with time zone": ColumnCategory.DATE,
    "boolean": ColumnCategory.BOOLEAN,
    "USER-DEFINED": ColumnCategory.GEOMETRY,  # PostGIS geometry shows as USER-DEFINED
})

OPERATORS_BY_COLUMN_CATEGORY: MappingProxyType[ColumnCategory, frozenset[str]] = MappingProxyType({
    ColumnCategory.TEXT: frozenset({"eq", "ilike"}),
    ColumnCategory.NUMERIC: frozenset({"eq", "gt", "gte", "lt", "lte"}),
    ColumnCategory.DATE: frozenset({"eq", "gt", "gte", "lt", "lte"}),
    ColumnCategory.BOOLEAN: frozenset({"eq"}),
})


OPERATOR_TO_SQL_SYMBOL: MappingProxyType[str, str] = MappingProxyType({
    "eq": "=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "ilike": "ILIKE",
})

KNOWN_TABLES = tuple(table.value for table in DatabaseTables) # hey I'm using a tuple, I don't want this to be changing!

ALLOWED_FULL_TABLES: frozenset[DatabaseTables] = frozenset({
    DatabaseTables.city_boundary,
    DatabaseTables.city_districts,
    DatabaseTables.hydrology,
    DatabaseTables.watermain_pipes,
    DatabaseTables.watermain_breaks,
    DatabaseTables.select_watermain_breaks,
    DatabaseTables.select_watermain_pipes,
    DatabaseTables.weather_stations,
})