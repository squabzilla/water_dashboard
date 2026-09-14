"""
file name: weatherData_updateDailyRecords_runDaily.py
author: William Hovdestad

This script is designed to call the `fetch_MSC_GeoMet_weather` from the `weather_APIlogic.py` file,
in order to update the daily-weather values in the PostGIS database; this script is intended to be run daily.

It grabs the `climate-daily` data from the Canada weather API
link: https://api.weather.gc.ca/openapi?f=html#/climate-daily

It will grab the last 14 days of data, and overwrite existing records.
Why? Because there's a possibility of some Canada Weather QA/QC process leading to records being changed,
and two weeks is both overkill, and also honestly a small number of records to change.
Especially since I want to run this daily at like 2am or something.

This data is designed to be used in tandem with Water-Main-Breaks data from the City-of-Calgary,
whose data can be found here: https://data.calgary.ca/Environment/Water-Main-Breaks/dpcu-jr23/data_preview
so this data fetches records starting at 1956-01-01 to match the Water-Main-Break records.
"""



########################################################################################################################
### script-setup 1: project-root-setup
import os
import sys
from pathlib import Path

# gets file-path, (hopefully) resolves relative path issues, great gets grand-parent folder
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# sets working directory to project root - there may be redundancy here but oh well lol
os.chdir(PROJECT_ROOT)
# Ensure repository code is importable when this wrapper is run directly.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))



########################################################################################################################
### script-setup 2: library imports
from datetime import datetime, timedelta # for getting date-time stuff
import psycopg # stuff needed to connect with postgis database
import sqlalchemy # stuff needed to connect with postgis database
import numpy as np # because I guess `np.nan` is better than `pd.NA` for no-data-values in Pandas?
import pandas as pd # just for merging dataframes, otherwise we use geopandas lol
import geopandas as gpd # geospatial library, used for GeoDataFrames
import httpx # used for calling API
import json # used for handling export of json data
import logging

# custom modules!
from data_pipeline.helper.helper_timezones import AB_TIME
from data_pipeline.helper.helper_SQL_tables import DAILY_WEATHER_PROPERTIES, DAILY_WEATHER_DATA_TYPES, DatabaseTables, \
    DailyWeatherCols, DAILY_WEATHER_STAGING_UNIQUE_DATE_CONSTRAINT
from data_pipeline.API.weather_helper_API import fetch_weather_pages, filter_stations_by_priority
from data_pipeline.helper.helper_API_errors import DataUniquenessConstraintViolation
from data_pipeline.helper.helper_SQL_tables import STN_IDS_STR_CSV_LIST
from data_pipeline.helper.helper_PSQL_config import default_SQL_engine
from data_pipeline.helper.helper_DB_update import add_new_records_to_table



########################################################################################################################
### script-setup 3: logging config
logfile = Path(PROJECT_ROOT) / "data_pipeline" / "API" / "log_files" / f"{Path(__file__).stem}.log" # base log name on file name
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[ # handles output stuff
        logging.FileHandler(logfile), # handles output file
        logging.StreamHandler() # writes log to a "stream" which by default is terminal/console
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

def _fetch_daily_MSC_GeoMet_daily_weather_last_14_days() -> gpd.GeoDataFrame:
    # get proper datetime string to use! first, get current time, make it a date, subtract 2 weeks from current date
    day_minus_14 = datetime.now(AB_TIME).date() - timedelta(days=14) # being very explicit with timezones here
    # now, convert it to proper parameter to API call
    datetime_param = str(day_minus_14) + "T00:00:00Z/.."

    # get the stations we want to work with
    # url of API
    daily_weather_url = "https://api.weather.gc.ca/collections/climate-daily/items"

    # setup parameters
    daily_weather_params = {
        "limit": 1000,
        "filter": f"properties.{DailyWeatherCols.dwc_climate_identifier} IN ({STN_IDS_STR_CSV_LIST})",
        "datetime": datetime_param,
        "properties": DAILY_WEATHER_PROPERTIES, # filter to specific properties I want from station
    }

    gdf = fetch_weather_pages(start_url=daily_weather_url, params=daily_weather_params,
                              job_title=f"last-14-daily-weather-records")

    gdf = filter_stations_by_priority(gdf, station_id_col=DailyWeatherCols.dwc_climate_identifier,
                                      datetime_col=DailyWeatherCols.dwc_local_date)

    # NOTE: dates should be unique now, so let's check that
    if not gdf[DailyWeatherCols.dwc_local_date].is_unique:
        msg = f"Error: DataUniquenessConstraintViolation: dates not unique on daily-update of daily-weather-values on day: {datetime.now().date()}"
        logger.error(msg)
        raise DataUniquenessConstraintViolation(msg)

    return gdf


########################################################################################################################
### section 2 - define main function to call local helper

def main() -> None:
    gdf = _fetch_daily_MSC_GeoMet_daily_weather_last_14_days()
    engine = default_SQL_engine()
    main_table_name = DatabaseTables.weather_daily
    staging_table_name = DatabaseTables.weather_daily_staging
    unique_column = DailyWeatherCols.dwc_local_date
    staging_table_unique_constraint_name = DAILY_WEATHER_STAGING_UNIQUE_DATE_CONSTRAINT
    dtype_dictionary = dict(DAILY_WEATHER_DATA_TYPES)

    add_new_records_to_table(gdf=gdf, engine=engine, main_table_name=main_table_name,
                                staging_table_name=staging_table_name, unique_column=unique_column,
                                staging_table_unique_constraint_name=staging_table_unique_constraint_name,
                                dtype_dictionary=dtype_dictionary, overwrite=True) # still want this one to overwrite!



########################################################################################################################
### section 3:  call main
# this function will run by itself if this script is called, including the start & end time pieces
if __name__ == "__main__":
    logger.info(f"Script: {__file__} started at {datetime.now()}")# print statement for start of script, and current time
    main()
    logger.info(f"Script: {__file__} completed at {datetime.now()}")# print statement for end of script, and current time