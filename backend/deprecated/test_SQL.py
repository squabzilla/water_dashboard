########################################################################################################################
# file name: weather_daily_backfill.py
# author: William Hovdestad
#
# This script is designed to call the `fetch_MSC_GeoMet_weather` from the `weather_APIlogic.py` file,
# in order to backfill the database with daily-weather-values.
#
# This data is designed to be used in tandem with Water-Main-Breaks data from the City-of-Calgary,
# whose data can be found here: https://data.calgary.ca/Environment/Water-Main-Breaks/dpcu-jr23/data_preview
# so this data fetches records starting at 1956-01-01 to match the Water-Main-Break records.



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
from sqlalchemy import create_engine # stuff needed to connect with postgis database
import numpy as np # because I guess `np.nan` is better than `pd.NA` for no-data-values in Pandas?
import pandas as pd # just for merging dataframes, otherwise we use geopandas lol
import geopandas as gpd # geospatial library, used for GeoDataFrames
#from shapely.geometry import Point # used to properly format lat/long values for use by GeoPandas
import httpx # used for calling API
#from dateutil.parser import parse # used for properly formatting DATE data into datetime variables
import json # used for handling export of json data
import logging

# custom modules!
from backend.helper.helper_progress_bar import update_progress_bar
#from backend.helper_error import CustomErrorMessage
from backend.helper.helper_SQL_tables import DAILY_WEATHER_PROPERTIES, DAILY_WEATHER_DATA_TYPES, \
    DailyWeatherCols, HourlyWeatherCols, DatabaseTables, HOURLY_WEATHER_PROPERTIES, \
    PRIMARY_STATION_ID, SECONDARY_STATION_ID, TERTIARY_STATION_ID, \
    SWOB_PROPERTIES, HOURLY_SWOB_CONVERSION, DAILY_WEATHER_UNIQUE_DATE_CONSTRAINT, DAILY_WEATHER_STAGING_UNIQUE_DATE_CONSTRAINT
from backend.helper.helper_set_geojson_crs import set_geojson_crs
from backend.API_Current.weather_helper_API import fetch_weather_pages, filter_stations_by_priority

from backend.helper.helper_API_errors import APITimeoutError, APIResponseError, APICountMismatchError, APIZeroCountError, \
    DataUniquenessConstraintViolation, DBError
from backend.helper.helper_SQL_tables import PRIMARY_STATION_ID, SECONDARY_STATION_ID, TERTIARY_STATION_ID
from backend.helper.helper_PSQL_config import default_SQL_engine
from backend.helper.helper_DB_update import export_as_new_table, add_new_records_to_table



########################################################################################################################
### section 1
from sqlalchemy import inspect

"""
class DatabaseTables(StrEnum):
    weather_daily = "weather_daily"
    # weather_data_daily_2 = "weather_data_daily_2"
    weather_daily_staging = "weather_daily_staging"
    weather_hourly = "weather_hourly"
    weather_hourly_staging = "weather_hourly_staging"
    weather_stations = "weather_stations"
    watermain_breaks = "watermain_breaks"
"""

daily_table = DatabaseTables.weather_daily
hours_table = "weather_data_hourly"

main_table = daily_table
unique_col = "LOCAL_DATE"
staging_table = main_table + "_STAGING"

engine = default_SQL_engine()
inspector = inspect(engine)
columns = [col["name"] for col in inspector.get_columns(main_table)]
update_columns = [col for col in columns if col != unique_col]

set_clause = ", ".join(
        f'\n"{col}" = EXCLUDED."{col}"' for col in update_columns
    )

sql_command_1 = (
        f"""INSERT INTO {main_table} \n"""
        f"""SELECT * FROM {staging_table} \n"""
        f"""ON CONFLICT ("{unique_col}") DO UPDATE SET """
        f"""{set_clause}; """
    )

#print(sql_command_1)
inspector = inspect(engine)
main_cols_list = [col["name"] for col in inspector.get_columns(main_table)]
# staging_cols = [col["name"] for col in inspector.get_columns(staging_table)]
staging_cols_list = [col["name"] for col in inspector.get_columns(main_table)]

# get a list of matching-columns that exist in BOTh tables, matching column order of main-table
all_cols_list = [col for col in main_cols_list if col in staging_cols_list]
# NOTE: this will silently remove columns that exist in the staging-table, but not the main table

# let's also get a list of columns to update - which is everything but the unique-column
update_cols_list = [col for col in all_cols_list if col != unique_col]

# fail if our list of matching-columns doesn't actually match the main table
if all_cols_list != main_cols_list: raise ValueError(f"ERROR - staging table is missing columns found in main table.")


# get comma-seperated cols
all_cols_csv_list = ", ".join(f'"{col}"' for col in all_cols_list)

# get our string of columns to update
update_clause_string = ", ".join(f'\n"{col}" = EXCLUDED."{col}"' for col in update_cols_list)
# NOTE: we're putting every `"col" = EXCLUDED."col"` on its own line for sanity's sake lol

sql_command_2 = (
    f"""INSERT INTO {main_table} ({all_cols_csv_list}) \n"""
    f"""SELECT {all_cols_csv_list} FROM {staging_table} \n"""
    f"""ON CONFLICT ("{unique_col}") DO UPDATE SET """
    f"""{update_clause_string}; """
)

#print(sql_command_1)
#print(sql_command_2)

unique_col

def build_upsert_statement(engine, main_table, staging_table, unique_column, overwrite=False):
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
        f"""ON CONFLICT ("{unique_column}") DO UPDATE SET """
        f"""ON CONFLICT ("{unique_column}") DO NOTHING; """
    )

    sql_command_overwrite = (
        f"""INSERT INTO {main_table} ({all_cols_csv_list}) \n"""
        f"""SELECT {all_cols_csv_list} FROM {staging_table} \n"""
        f"""ON CONFLICT ("{unique_column}") DO UPDATE SET """
        f"""{update_clause_string}; """
    )

    if overwrite == True: return sql_command_overwrite
    else: return sql_command_preserve_original


