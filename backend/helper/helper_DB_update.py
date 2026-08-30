########################################################################################################################
# file name: helper_DB_update.py
# author: William Hovdestad
#
# This script has two helper functions to be "exported"
# to help me connect and update/insert records into my PostGIS Database,
# as well as an "internal-use" function.
# It also has an "internal-use" function to help generate the SQL command to add records to the database,
# depending on if we want to overwrite existing records, or keep old ones, in the case of unique-column-conflict.
#
# The first function, `export_as_new_table`, is one of the ones to be "exported";
# it hashas the boiler-plate to export a GDF as a new table, including the code to reset the unique constraint.
#
# The second function, `_build_upsert_statement` is used to generate the SQL command to add records to the database,
# depending on if we want to overwrite existing records, or keep old ones, in the case of unique-column-conflict.
#
# The third function, `add_new_records_to_table`, has the boiler plate to export a GDF to a staging table, 
# add a unique constraint, and add new records to the database - using the `_build_upsert_statement` function
# to build the correct SQL command depending on if we want to overwrite data, or keep old records.



########################################################################################################################
### script-setup 1: project-root-setup
import os
import sys
from pathlib import Path

# gets file-path, (hopefully) resolves relative path issues, gets grand-parent folder
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# sets working directory to project root - there may be redundancy here but oh well lol
os.chdir(PROJECT_ROOT)
# Ensure repository code is importable when this wrapper is run directly.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))



########################################################################################################################
### script-setup 2: library imports
import argparse # used for adding command line arguments to script
from datetime import date, datetime, time, timedelta, timezone # for getting current date
import psycopg # stuff needed to connect with postgis database
import sqlalchemy # stuff needed to connect with postgis database
from sqlalchemy import text # make pylance happy by recognizing this as a keyword lol
from sqlalchemy import create_engine, Engine # stuff needed to connect with postgis database
from sqlalchemy import inspect # used to look at columns
import numpy as np # because I guess `np.nan` is better than `pd.NA` for no-data-values in Pandas?
import pandas as pd # just for merging dataframes, otherwise we use geopandas lol
import geopandas as gpd # geospatial library, used for GeoDataFrames
#from shapely.geometry import Point # used to properly format lat/long values for use by GeoPandas
import httpx # used for calling API
#from dateutil.parser import parse # used for properly formatting DATE data into datetime variables
import json # used for handling export of json data
import logging

"""
# NOTE: Probably don't need this stuff
# custom modules!
from backend.helper.helper_progress_bar import update_progress_bar
#from backend.helper_error import CustomErrorMessage
from backend.helper.helper_SQL_tables import DAILY_WEATHER_PROPERTIES, DAILY_WEATHER_DATA_TYPES, \
    DailyWeatherCols, HourlyWeatherCols, DatabaseTables, HOURLY_WEATHER_PROPERTIES, \
    PRIMARY_STATION_ID, SECONDARY_STATION_ID, TERTIARY_STATION_ID, \
    SWOB_PROPERTIES, HOURLY_SWOB_CONVERSION, DAILY_WEATHER_UNIQUE_DATE_CONSTRAINT, DAILY_WEATHER_STAGING_UNIQUE_DATE_CONSTRAINT
from backend.helper.helper_set_geojson_crs import set_geojson_crs
from backend.API_Current.weather_APIlogic import fetch_weather_pages, filter_stations_by_priority

from backend.helper.helper_API_errors import APITimeoutError, APIResponseError, APICountMismatchError, APIZeroCountError, DataUniquenessConstraintViolation
from backend.helper.helper_SQL_tables import PRIMARY_STATION_ID, SECONDARY_STATION_ID, TERTIARY_STATION_ID
from backend.helper.helper_PSQL_config import default_SQL_engine
"""
from backend.helper.helper_API_errors import DBError


########################################################################################################################
### section 1 - export as new table


def export_as_new_table(gdf: gpd.GeoDataFrame, engine: Engine,
                        main_table_name: str, dtype_dictionary: dict | None,
                        main_table_unique_constraint_name: str, unique_column: str) -> None:
    # Write gdf to main table, overwriting old results if any
    gdf.to_postgis(main_table_name, engine, if_exists="replace", index=False, 
                    dtype=dtype_dictionary # unwrap to a regular dict for the function call
                    # dtype=dict(DAILY_WEATHER_DATA_TYPES) # NOTE: REMEMBER THIS
                    )

    # sql command to add uniqueness constraint
    # get rid of it if it exists, then add it back lol
    sql_command = (
        f"""ALTER TABLE {main_table_name} """ # multi-line f-string - make sure we have trailing space at end to separate clauses
        f"""DROP CONSTRAINT IF EXISTS {main_table_unique_constraint_name}; """
        f"""ALTER TABLE {main_table_name} """
        f"""ADD CONSTRAINT {main_table_unique_constraint_name} UNIQUE ("{unique_column}"); """
    )
    try:
        with engine.begin() as conn: conn.execute(text(sql_command))
    except:
        raise DBError(f"Error with running the following SQL code through engine: {sql_command}")



########################################################################################################################
### section 2.1 - function to build `upsert_statement` for sql to update table with new values
### this function has a boolean `overwrite` signifiying if the `upsert_statement` keeps old values, or uses new ones
### in the case of a conflict

def _build_upsert_statement(engine: Engine, main_table: str, staging_table: str,
                            unique_column: str, overwrite: bool=False) -> str:
    inspector = inspect(engine)
    main_cols_list = [col["name"] for col in inspector.get_columns(main_table)]
    # staging_cols = [col["name"] for col in inspector.get_columns(staging_table)]
    staging_cols_list = [col["name"] for col in inspector.get_columns(main_table)]

    # get a list of matching-columns that exist in BOTh tables, matching column order of main-table
    all_cols_list = [col for col in main_cols_list if col in staging_cols_list]
    # NOTE: this will silently remove columns that exist in the staging-table, but not the main table

    # let's also get a list of columns to update - which is everything but the unique-column
    update_cols_list = [col for col in all_cols_list if col != unique_column]

    # fail if our list of matching-columns doesn't actually match the main table
    if all_cols_list != main_cols_list: raise ValueError(f"ERROR - staging table is missing columns found in main table.")

    # get comma-seperated cols
    all_cols_csv_list = ", ".join(f'"{col}"' for col in all_cols_list)

    # get our string of columns to update
    update_clause_string = ", ".join(f'\n"{col}" = EXCLUDED."{col}"' for col in update_cols_list)
    # NOTE: we're putting every `"col" = EXCLUDED."col"` on its own line for sanity's sake lol

    sql_command_preserve_original = (
        f"""INSERT INTO {main_table} ({all_cols_csv_list}) \n"""
        f"""SELECT {all_cols_csv_list} FROM {staging_table} \n"""
        f"""ON CONFLICT ("{unique_column}") DO NOTHING; """
    )

    sql_command_overwrite = (
        f"""INSERT INTO {main_table} ({all_cols_csv_list}) \n"""
        f"""SELECT {all_cols_csv_list} FROM {staging_table} \n"""
        f"""ON CONFLICT ("{unique_column}") DO UPDATE SET """
        f"""{update_clause_string}; """
    )
    # NOTE: if I don't include the `unique_column` in the `all_cols_csv_list` string,
    # the `ON CONFLICT` clause will assign the default value to the `unique_column` when comparing them,
    # and assign NULL if there's no default value
    # this can cause problems and unexpected/undesired behaviour,
    # so I gotta include all relevant columns - INCLUDING the `unique_column` - in the column-list-portion

    if overwrite == True: return sql_command_overwrite
    else: return sql_command_preserve_original





########################################################################################################################
### section 2.2 - function to actually add records to table
### 




def add_new_records_to_table(gdf: gpd.GeoDataFrame, engine: Engine,
                             main_table_name: str, staging_table_name: str, unique_column: str, 
                             staging_table_unique_constraint_name: str, dtype_dictionary :str,
                             overwrite: bool) -> None:

    # write to staging table
    gdf.to_postgis(staging_table_name, engine, if_exists="replace", index=False, dtype=dtype_dictionary)
    # dtype=dict(DAILY_WEATHER_DATA_TYPES) # NOTE: REMEMBER THIS

    # add/reset uniqueness constraint on staging table
    #_add_unique_constraint(engine, table_name, unique_column, unique_constraint_name)
    sql_command = (
        f"""ALTER TABLE {staging_table_name} DROP CONSTRAINT IF EXISTS {staging_table_unique_constraint_name}; """
        f"""ALTER TABLE {staging_table_name} ADD CONSTRAINT {staging_table_unique_constraint_name} UNIQUE ("{unique_column}"); """
    )
    try:
        with engine.begin() as conn: conn.execute(text(sql_command))
    except:
        raise DBError(f"Error with running the following SQL code through engine: {sql_command}")

    
    # # SQL command to insert only rows from staging that doesn't exist in main table
    # sql_command = (
        # f"""INSERT INTO {main_table_name} """
        # f"""SELECT * FROM {staging_table_name} """
        # f"""ON CONFLICT ("{unique_column}") DO NOTHING; """
    # )
    # sql_command = f"""INSERT INTO {main_table_name} SELECT * FROM {staging_table_name} ON CONFLICT ("{unique_column}") DO NOTHING;"""
    # 
    # get sql-command to update database, depending of if `overwrite=True` or not
    sql_command = _build_upsert_statement(engine, main_table_name, staging_table_name, unique_column, overwrite)
    # def _build_upsert_statement(engine, main_table, staging_table, unique_column, overwrite=False):
    with engine.begin() as conn: conn.execute(text(sql_command))

    # SQL command to delete the staging table constraint, and then the entire staging table itself
    # Is that needed? I don't know. Probably not. But I don't wanna worry about ghost constraints lol
    sql_command = (
        f"""ALTER TABLE {staging_table_name} """
        f"""DROP CONSTRAINT IF EXISTS {staging_table_unique_constraint_name}; """
        f"""DROP TABLE IF EXISTS {staging_table_name}; """
    )
    try:
        with engine.begin() as conn: conn.execute(text(sql_command))
    except:
        raise DBError(f"Error with running the following SQL code through engine: {sql_command}")


