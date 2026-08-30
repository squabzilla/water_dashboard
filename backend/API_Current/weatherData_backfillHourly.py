########################################################################################################################
# file name: weather_hourly_backfill.py
# author: William Hovdestad
#
# This script is designed to call the `fetch_MSC_GeoMet_weather` from the `weather_APIlogic.py` file,
# in order to backfill the database with hourly-weather-values.
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
from backend.helper.helper_SQL_tables import HOURLY_WEATHER_PROPERTIES, HOURLY_WEATHER_DATA_TYPES, \
    HourlyWeatherCols, DatabaseTables, PRIMARY_STATION_ID, SECONDARY_STATION_ID, TERTIARY_STATION_ID, \
        HOURLY_WEATHER_UNIQUE_DATETIME_CONSTRAINT, HOURLY_WEATHER__STAGING_UNIQUE_DATETIME_CONSTRAINT
from backend.helper.helper_set_geojson_crs import set_geojson_crs
from backend.API_Current.weather_helper_API import fetch_weather_pages
from backend.API_Current.weather_helper_filterStationPriority import filter_stations_by_priority
from backend.API_Current.weather_helper_backfill import backfill_weather_years
from backend.helper.helper_API_errors import APITimeoutError, APIResponseError, APICountMismatchError, APIZeroCountError, \
    DataUniquenessConstraintViolation, DBError
from backend.helper.helper_SQL_tables import PRIMARY_STATION_ID, SECONDARY_STATION_ID, TERTIARY_STATION_ID
from backend.helper.helper_PSQL_config import default_SQL_engine
from backend.helper.helper_DB_update import export_as_new_table, add_new_records_to_table



########################################################################################################################
### script-setup 3: logging config
logfile = Path(PROJECT_ROOT) / "backend" / "API_Current" / "log_files" / "weatherData_backfillHourly.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[ # handles output stuff
        logging.FileHandler(logfile), # handles output file
        # logging.StreamHandler() # writes log to a "stream" which by default is terminal/console # NOTE: turning this on breaks progress bar lol
        ],
    # NOTE: logging levels: affects labelling and filtering when looking through errors
    # like remember how I'd tell Python "idgaf about that warning just stop telling me"
    # but also not wanting to eliminate like SERIOUS errors?
    # that's what the logging levels let us do
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING) # STOP LOGGING EVERY API CALL DAMNIT
# LOGGING ORDER:
# debug
# info
# warning
# error
# critical



########################################################################################################################
### section 1: function to fetch weather for given year

# def filter_stations_by_priority(df, station_id_col="CLIMATE_IDENTIFIER", datetime_col="LOCAL_DATE"):

def hourly_MSC_GeoMet_weather_by_year(year: int) -> gpd.GeoDataFrame:
    ids_clause = f"{PRIMARY_STATION_ID}, {SECONDARY_STATION_ID}, {TERTIARY_STATION_ID}"
    daily_weather_url = "https://api.weather.gc.ca/collections/climate-hourly/items"
    daily_weather_params = {
        "limit": 1000,
        "filter": f"properties.{HourlyWeatherCols.climate_identifier} IN ({ids_clause})",
        f"{HourlyWeatherCols.local_year}": year,
        "properties": HOURLY_WEATHER_PROPERTIES, # filter to specific properties I want from station
    }
    gdf = fetch_weather_pages(start_url=daily_weather_url, params=daily_weather_params, job_title=f"historical-hourly-weather-records-year-{year}")

    gdf = filter_stations_by_priority(gdf, station_id_col=HourlyWeatherCols.climate_identifier, datetime_col=HourlyWeatherCols.local_date)
    # NOTE: dates should be unique now, so let's check that
    if not gdf[HourlyWeatherCols.local_date].is_unique:
        raise DataUniquenessConstraintViolation(f"ERROR: dates not unique for daily-weather backfill year {year}")
    return gdf



########################################################################################################################
### section 2: main-function to loop through years

def main() -> None:

    main_table_name = DatabaseTables.weather_hourly
    staging_table_name = DatabaseTables.weather_hourly_staging
    unique_column = HourlyWeatherCols.local_date
    main_table_unique_constraint_name = HOURLY_WEATHER_UNIQUE_DATETIME_CONSTRAINT
    staging_table_unique_constraint_name = HOURLY_WEATHER__STAGING_UNIQUE_DATETIME_CONSTRAINT
    dtype_dictionary = dict(HOURLY_WEATHER_DATA_TYPES)
    progress_bar_prefix = "Backfilling hourly weather records"

    backfill_weather_years(MSC_GeoMet_weather_by_year=hourly_MSC_GeoMet_weather_by_year,
                               main_table_name=main_table_name, staging_table_name=staging_table_name, 
                               datetimecol=unique_column, main_table_unique_constraint_name=main_table_unique_constraint_name,
                               staging_table_unique_constraint_name=staging_table_unique_constraint_name,
                               dtype_dictionary=dtype_dictionary, progress_bar_prefix=progress_bar_prefix)

    """
    start_year = 1956 # first date in watermain break data
    start_year = 2025
    current_year = date.today().year

    failed_years = []


    for year in range(start_year, current_year + 1):
        print(f"year: {year}")
        try:
            gdf = hourly_MSC_GeoMet_weather_by_year(year)
        except APITimeoutError:
            logger.error(f"Network timeout for {year}")
            # NOTE: `logger.error` records the error message, without traceback to previous error messages;
            # because in this particular case, we know the whole story from the first message alone
            # traceback will give us more messages saying the same "OMG THE API TIMED OUT" and we don't need that in our lives
            failed_years.append(year)
        except APIResponseError:
            logger.exception(f"Malformed response for {year}")
            # NOTE: `logger.exception` does traceback, so it records all the error messages that triggered/preceded this one as well
            # that's because we'll want to get more detail about WHAT, exactly, went wrong with the API call & response
            # was it a bad HTTP status? asking the API for non-existant properties? we want fo figure out what caused it
            # NOTE: this one is the same level as `logger.error`
            failed_years.append(year)
        except APIZeroCountError:
            logger.warning(f"No records found for {year}")
            # still no traceback, but we're not going "OMG SOMETHING WENT HORRIBLY WRONG" here
            # this is "user made a mistake and queried something with 0 results" instead of an incorrectly formatted query
            failed_years.append(year)
        except APICountMismatchError:
            logger.exception(f"Inconsistent number of records found for {year}")
            failed_years.append(year)
        except DataUniquenessConstraintViolation:
            logger.error(f"Dates not unique for daily-weather backfill, year: {year}")
            failed_years.append(year)


        # define variables for database updating
        gdf = gdf
        engine = default_SQL_engine()
        main_table_name = DatabaseTables.weather_hourly
        staging_table_name = DatabaseTables.weather_hourly_staging
        unique_column = HourlyWeatherCols.local_date
        main_table_unique_constraint_name = HOURLY_WEATHER_UNIQUE_DATETIME_CONSTRAINT
        staging_table_unique_constraint_name = HOURLY_WEATHER__STAGING_UNIQUE_DATETIME_CONSTRAINT
        dtype_dictionary = dict(HOURLY_WEATHER_DATA_TYPES)


        if not year == start_year:
            # we want to update our table with new records if it's NOT the start year
            # def add_new_records_to_table(gdf, engine, main_table_name, staging_table_name,
                                         # unique_column, staging_table_unique_constraint_name,
                                         # dtype_dictionary)
            try:
                add_new_records_to_table(gdf=gdf, engine=engine, main_table_name=main_table_name,
                                         staging_table_name=staging_table_name, unique_column=unique_column,
                                         staging_table_unique_constraint_name=staging_table_unique_constraint_name,
                                         dtype_dictionary=dtype_dictionary)
            except:
                logger.exception(f"DB write failed for {year}")
                failed_years.append(year)

        else:
            # Write gdf to main table, overwriting old results if any
            # def export_as_new_table(gdf, engine, main_table_name, dtype_dictionary, main_table_unique_constraint_name, unique_column):
            try:
                export_as_new_table(gdf=gdf, engine=engine, main_table_name=main_table_name, dtype_dictionary=dtype_dictionary,
                                    main_table_unique_constraint_name=main_table_unique_constraint_name, unique_column=unique_column)
            except:
                error_message = f"Cannot create table for start year {year}; aborting backfill."
                logger.critical(error_message, exc_info=True)
                raise DBError(error_message)
    """


########################################################################################################################
### section 2:  call main
# this function will run by itself if this script is called, including the start & end time pieces
if __name__ == "__main__":
    logger.info(f"Script: {__file__} started at {datetime.now()}")# print statement for start of script, and current time
    main()
    logger.info(f"Script: {__file__} completed at {datetime.now()}")# print statement for end of script, and current time