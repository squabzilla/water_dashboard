"""
file name: main.y
author: William Hovdestad

basic main-file for running back-end of app, making sure my web-app can query my PostGIS database
"""


########################################################################################################################
### script-setup 1: project-root-setup
import os
import sys
from pathlib import Path

# gets file-path, (hopefully) resolves relative path issues, gets grand-parent folder
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# sets working directory to project root - there may be redundancy here but oh well lol
os.chdir(PROJECT_ROOT)
# Ensure repository code is importable when this wrapper is run directly.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
# get path for environment so I can load it later



########################################################################################################################
### script-setup 2: library imports
from datetime import datetime # for getting date-time stuff
from fastapi import FastAPI, Request, HTTPException, Depends
import logging # for logging errors
import psycopg # stuff needed to connect with postgis database
import sqlalchemy # stuff needed to connect with postgis database
import httpx # used for calling API
import json # used for handling export of json data
from sqlalchemy import Connection
from contextlib import asynccontextmanager


from data_pipeline.helper.helper_SQL_tables import DatabaseTables
from data_pipeline.helper.helper_PSQL_config import default_SQL_engine
from backend.query_helpers.schema_constants import SPATIAL_LAYER_TABLES
from backend.query_helpers.schema_errors import FilterError
from backend.query_helpers.query_builders import get_geometry_column, execute_scalar, build_where_clause, load_schema_registry



########################################################################################################################
### script-setup 3: logging config - now with a helper function!
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING) # STOP LOGGING EVERY API CALL DAMNIT



########################################################################################################################
### section 1: create-engine, setup `app.state.schema_registry`, start app

# function to setup engine
engine = default_SQL_engine()

# setsup `app.state.schema_registry`
@asynccontextmanager
async def lifespan(app: FastAPI):
    with engine.connect() as conn:
        app.state.schema_registry = load_schema_registry(conn)
    yield

# start app
app = FastAPI(lifespan=lifespan)


########################################################################################################################
### setup get-db-connection function, as route-handlers shouldn't open connections themselves or reuse startup one
### each request needs its own
def get_db_connection():
    with engine.connect() as conn:
        yield conn

"""
NOTE: Depends
`Depends(get_db_connections)` tells FastAPI to run that generator before the route body,
hand the route what it `yield`s, then resume the generator after the route return
That's what closes the connection, automatically, after every request - success or failure.
"""


########################################################################################################################
### Endpoint 1: Full table / spatial-layer-tables

@app.get("/api/tables/{table}/full")
#def get_full_table(table: str):
def get_full_table(
    table: DatabaseTables, # Claude switched it to this from str - to make sure it only takes items from that table?
    conn: Connection = Depends(get_db_connection)): # use `Depends` because I should let FastAPI call it for me I guess???
    if table not in SPATIAL_LAYER_TABLES:
        raise HTTPException(403, f"table '{table}' not available for full retrieval")

    geom_col = get_geometry_column(table.value, app.state.schema_registry)  # look up from registry
    sql = f"""
        SELECT jsonb_build_object(
            'type', 'FeatureCollection',
            'features', jsonb_agg(
                jsonb_build_object(
                    'type', 'Feature',
                    'geometry', ST_AsGeoJSON("{geom_col}")::jsonb,
                    'properties', to_jsonb(t) - '{geom_col}'
                )
            )
        )
        FROM "{table.value}" t
    """
    # NOTE: TODO: figure out how the hell the above SQL query works lol
    return execute_scalar(conn, sql)



########################################################################################################################
### Endpoint 2: Filtered query

@app.get("/api/tables/{table}/query")
def query_table(
    table: DatabaseTables,  # Claude switched it to this from str - to make sure it only takes items from that table?
    request: Request,
    conn: Connection = Depends(get_db_connection)): # use `Depends` because I should let FastAPI call it for me I guess???

    filters = dict(request.query_params)  # e.g. ?break_date__gte=2020-01-01&status__eq=active
    try:
        where_sql, params = build_where_clause(table.value, filters, app.state.schema_registry)
    except FilterError as e:
        raise HTTPException(400, str(e))

    geom_col = get_geometry_column(table.value, app.state.schema_registry)
    sql = f"""
        SELECT jsonb_build_object(
            'type', 'FeatureCollection',
            'features', COALESCE(jsonb_agg(
                jsonb_build_object(
                    'type', 'Feature',
                    'geometry', ST_AsGeoJSON("{geom_col}")::jsonb,
                    'properties', to_jsonb(t) - '{geom_col}'
                )
            ), '[]'::jsonb)
        )
        FROM "{table.value}" t
        WHERE {where_sql}
    """
    # NOTE: TODO: figure out how the hell the above SQL query works lol
    return execute_scalar(conn, sql, params)