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

from data_pipeline.helper.helper_PSQL_config import default_SQL_engine
from data_pipeline.helper.helper_SQL_tables import \
    DatabaseTables, SWOBWeatherCols, HOURLY_SWOB_CONVERSION, HourlyWeatherCols
from backend.query_helpers.schema_errors import SchemaError, FilterError
from backend.query_helpers.schema_constants import \
    ColumnCategory, KNOWN_TABLES, PG_TYPE_TO_CATEGORY, OPERATORS_BY_COLUMN_CATEGORY, OPERATOR_TO_SQL_SYMBOL
from backend.query_helpers.query_builders import load_schema_registry

"""
try:
    with engine.begin() as conn: conn.execute(text(sql_command))
except:
    raise DBError(f"Error with running the following SQL code through engine: {sql_command}")
"""

sql_statement = \
"""
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = ANY(:known_tables)
"""
known_tables = list(KNOWN_TABLES)
known_tables = list(known_tables[0])
#print(known_tables)

engine = default_SQL_engine()
with engine.connect() as conn:
    rows = load_schema_registry(conn)
print(rows,"\n\n")
#for item in rows: print(item)

if False:
    with engine.connect() as conn:
        rows = conn.execute(text(sql_statement), {"known_tables": known_tables}).fetchall()
    #print(rows)

#print(PG_TYPE_TO_CATEGORY.get("integer"))

# print(HOURLY_SWOB_CONVERSION[SWOBWeatherCols.swob_station_name])