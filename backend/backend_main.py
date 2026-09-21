"""
file name: main.y
author: William Hovdestad

basic main-file for running back-end of app, making sure my web-app can query my PostGIS database

the primary purpose of this script is to have "endpoints" that the front-end can call
in order to retrieve data from my PostGIS PSQL database

It also has like helper/supporting logic to aid this

ENDPOINT-1: Full table / spatial-layer-tables
this retrieves an entire GeoJSON - all of it - used for when we want the whole thing for our spatial/mapping layers

ENDPOINT-2: Filtered query
Kinda self-descriptive, used when we want to do some filtered-query of a DB
to search for a subset of data

ENDPOINT-3: `get_summary`
gets us some summary statistics of watermain breaks
has logic to filter it in different ways
TODO: can this filter by community, if we want stats of a particular community?
later problem, get V1 of this webapp to actually be a web-app people can view online
remember, having SOMETHING to show for your portfolio website
- no matter how unpolished - 
still puts you miles ahead of "we're working on it" portfolio project
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
from datetime import datetime, date # for getting date-time stuff
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
from backend.query_helpers.query_builders import get_geometry_column, execute_geojson_scalar,\
      build_where_clause, load_schema_registry, execute_json_scalar



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
### Section 2:
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
    return execute_geojson_scalar(conn, sql)

"""
NOTE: Explaining that SQL structure
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

jsonb_build_object(key_1,value_1, key_2,value_2, ..., key_n,value_n)
builds a json-structured-object for each line in the table;
doesn't *technically* need to actually grab table objects lol
each line is structured as {key_1:value_1, key_2:value_2, ..., key_n:value_n}
remember, this goes LINE-BY-LINE, and returns as many lines as the SQL query
{line1_keyA:line1_valueA, line1_keyB:line1_valueB}
{line2_keyA:line2_valueA, line2_keyB:line2_valueB}
etc.

jsonb_agg(jsonb_build_object())
takes a json_b_build_object, compresses all the lines in a single list
example:
[ {line1_keyA:line1_valueA, line1_keyB:line1_keyB}, {line2_keyA:line2_keyA, line2_keyB:line2_valueB} ]

ST_AsGeoJSON("INSERT_GEOMETRY_COLUMN_HERE")::jsonb
so first off, INSERT_GEOMETRY_COLUMN_HERE is a placeholder for the geometry column of a table lol
first half: `ST_AsGeoJSON("INSERT_GEOMETRY_COLUMN_HERE")`
returns the geometry column as text - but text means string, so formatting is fucky, 
so the second half: `::jsonb` converts it to proper JSON object
tbh, limited testing shows that `::jsonb` only really adds spaces, and might not be necessary?
on the other hand, it's more likely to break down the road if I don't do that conversion, so let's leave that in

'properties', to_jsonb(t) - '{geom_col}'
`to_jsonb(t)` converts entire row into JSON object - one key per column, right?
so for row X: {'col_name':''rowX_colValue'}, right
BUT when it hits the geometry column, because of how geometry is representing internally, it might look real fuck
so we add `- 'INSERT_GEOMETRY_COLUMN_HERE'` to remove it lol

now, let's talk about how GeoJSONs are structured
remember there's no separate meta-data in a JSON, but you can add more parts to add to fufill the role of metadata
So if we have a GeoJSON, we want to make sure we COMMUNICATE that it's a GeoJSON, right? So:
{"type": "FeatureCollection", "features": [...]} is the formatting for declaring that this is a GeoJSON,
and everything inside "features" is the actual content, while the top-level shit is all meta-data
also gives us more room to add more meta-data later

so let's go through the query:
SELECT jsonb_build_object(
            'type', 'FeatureCollection',
            'features', jsonb_agg([...])
        )
this part is the high level wrapper for the GeoJSON, with the value for 'features' being the actual data
note the value of: jsonb_agg([...]) 
so [...] is our representation of ANOTHER jsonb_build_object() - one with all the data - that we've compressed into a single list
that [...] is actually:
jsonb_build_object(
                    'type', 'Feature', # just some names and shit
                    'geometry', ST_AsGeoJSON("{geom_col}")::jsonb, # value is converting the geometry column to string, then converting to jsonb to be safe
                    'properties', to_jsonb(t) - '{geom_col}' # converts everything in row (mins '{geom_col}') into jsonb-object, with key-value pair of col:line-value
                )
which returns everything we've described earlier - but remember it applies that to every line of table,
so we need the jsonb_agg() to compress it into single list

HOPEFULLY this makes sense next time I read through it lol
"""



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
    return execute_geojson_scalar(conn, sql, params)



########################################################################################################################
### Endpoint 3: get_summary

@app.get("/api/summary")
def get_summary(
    start_date: date | None = None, # ensures this is a date, otherwise shit crashes
    end_date: date | None = None, # ensures this is a date, otherwise shit crashes
    conn: Connection = Depends(get_db_connection),
):
    filters: dict[str, str] = {}
    if start_date:
        filters["break_date__gte"] = start_date.isoformat() # converts date, time, datetime in string object formatted as ISO 8601 standard
    if end_date:
        filters["break_date__lte"] = end_date.isoformat() # converts date, time, datetime in string object formatted as ISO 8601 standard

    where_sql, params = build_where_clause(
        DatabaseTables.watermain_breaks.value, filters, app.state.schema_registry
    )

    sql = f"""
        SELECT jsonb_build_object(
            'total_breaks', COUNT(*),
            'earliest_break', MIN(break_date),
            'latest_break', MAX(break_date),
            'avg_breaks_per_year', ROUND(
                COUNT(*)::numeric / GREATEST(
                    (EXTRACT(YEAR FROM MAX(break_date)) - EXTRACT(YEAR FROM MIN(break_date)) + 1), 1
                ), 
                2
            )
        )
        FROM "{DatabaseTables.watermain_breaks.value}"
        WHERE {where_sql}
    """
    return execute_json_scalar(conn, sql, params)

"""
okay let's go over that SQL code lol

SELECT jsonb_build_object(
    'total_breaks', COUNT(*),
    'earliest_break', MIN(break_date),
    'latest_break', MAX(break_date),
    'avg_breaks_per_year', ROUND(
        COUNT(*)::numeric / GREATEST( -- we count the objects, make sure they're `numeric` and not `int`
            (EXTRACT(YEAR FROM MAX(break_date)) - EXTRACT(YEAR FROM MIN(break_date)) + 1), 1
            -- above line gets greatest of maxyear-minyear+1 and 1, ensuring we aren't dividing by 0 at any point
        ), 
        2 -- final part of ROUND, to 2 decimal places
    )
)

"""