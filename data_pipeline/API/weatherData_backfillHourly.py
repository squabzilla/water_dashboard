"""
file name: weather_hourly_backfill.py
author: William Hovdestad

This script is used to backfill our PostGIS-PSQL database with hourly-weather-values.

This script can be used to backfill all years of daily-weather into our database,
or backfill a single year via command line arguments.
The command-line argument usage is as follows:
`uv run weather_hourly_backfill.py -y <year>`
where <year> is a valid integer for a valid-year to backfill.
Valid years are from 1956 to current year.

This script has two parts. The first is a function called `hourly_MSC_GeoMet_weather_by_year`
which is passed a year, and returns a geoDataFrame.
It calls the `fetch_MSC_GeoMet_weather` from the `weather_APIlogic.py` file in order to retrieve
the data from the API.

The second part: it calls either the `backfill_weather_years` function 
or `backfill_single_year` function from `weather_helper_backfill.py`.

The `backfill_single_year` function has the logic to backfill the database for a single given year.

The `backfill_weather_years` function contains the logic 
to loop through all of the relevant years for backfilling our database.
Note that the `backfill_weather_years` function is designed to TAKE a function as input -
a function that takes an integer YEAR as input.

The API in question:
This script uses the `climate-hourly` data from the Canada weather API
link: https://api.weather.gc.ca/openapi?f=html#/climate-hourly

This data is designed to be used in tandem with Water-Main-Breaks data from the City-of-Calgary,
whose data can be found here: https://data.calgary.ca/Environment/Water-Main-Breaks/dpcu-jr23/data_preview
so this data fetches records starting at 1956-01-01 to match the Water-Main-Break records.
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



########################################################################################################################
### script-setup 2: library imports
import argparse # used for adding command line arguments to script
from datetime import datetime # for getting date-time stuff
import psycopg # stuff needed to connect with postgis database
import sqlalchemy # stuff needed to connect with postgis database
import numpy as np # because I guess `np.nan` is better than `pd.NA` for no-data-values in Pandas?
import pandas as pd # just for merging dataframes, otherwise we use geopandas lol
import geopandas as gpd # geospatial library, used for GeoDataFrames
import httpx # used for calling API
import json # used for handling export of json data
import logging

# custom modules!
from data_pipeline.helper.helper_logging_config import setup_logging
from data_pipeline.helper.helper_timezones import AB_TIME
from data_pipeline.helper.helper_SQL_tables import HOURLY_WEATHER_PROPERTIES, HOURLY_WEATHER_DATA_TYPES, DatabaseTables, \
    HourlyWeatherCols, HOURLY_WEATHER_UNIQUE_DATETIME_CONSTRAINT, HOURLY_WEATHER_STAGING_UNIQUE_DATETIME_CONSTRAINT
from data_pipeline.API.weather_helper_API import fetch_weather_pages, filter_stations_by_priority, hourlyWeather_FixDatetimes
from data_pipeline.API.weather_helper_backfill import valid_year, backfill_single_year, backfill_weather_years
from data_pipeline.helper.helper_API_errors import DataUniquenessConstraintViolation
from data_pipeline.helper.helper_SQL_tables import STN_IDS_STR_CSV_LIST



########################################################################################################################
### script-setup 3: logging config - now with a helper function!
logger = logging.getLogger(__name__)



########################################################################################################################
### script-setup 4: setup command line arguments for script
#

parser = argparse.ArgumentParser(description=__doc__)

DEFAULT_YEARS = 0

# We have a command-line argument for how many hours we look back
parser.add_argument(
    "-y", "--years", # NOTE: `-h` is reserved for "help" lol
    type=int,
    default=DEFAULT_YEARS,
    help=f"Year we want to fill; the default, 0, backfills all relevant years. (Can leave CLI blank if we want all years.)",
)
args = parser.parse_args()



########################################################################################################################
### section 1: function to fetch weather for given year

def hourly_MSC_GeoMet_weather_by_year(year: int) -> gpd.GeoDataFrame:
    daily_weather_url = "https://api.weather.gc.ca/collections/climate-hourly/items"
    daily_weather_params = {
        "limit": 1000,
        "filter": f"properties.{HourlyWeatherCols.hwc_climate_identifier} IN ({STN_IDS_STR_CSV_LIST})",
        f"{HourlyWeatherCols.hwc_local_year}": year,
        "properties": HOURLY_WEATHER_PROPERTIES, # filter to specific properties I want from station
    }
    gdf = fetch_weather_pages(start_url=daily_weather_url, params=daily_weather_params, job_title=f"historical-hourly-weather-records-year-{year}")

    # add timezones # actually, fix datetimes since AB dropping daylight savings time broke everything
    gdf = hourlyWeather_FixDatetimes(gdf)

    gdf = filter_stations_by_priority(gdf, station_id_col=HourlyWeatherCols.hwc_climate_identifier, datetime_col=HourlyWeatherCols.hwc_local_date)
    # NOTE: dates should be unique now, so let's check that
    if not gdf[HourlyWeatherCols.hwc_local_date].is_unique:
        msg = f"Error: DataUniquenessConstraintViolation: dates not unique for daily-weather backfill year {year}"
        logger.error(msg)
        raise DataUniquenessConstraintViolation(msg)
    return gdf



########################################################################################################################
### section 2: main-function to either backfill all years, or fill a specific year (depending on CLI arguments)

def _backfill_hourly_weather(years_code:int = args.years) -> int:
    valid_year(years_code) # checks validity of entered year

    main_table_name = DatabaseTables.weather_hourly
    staging_table_name = DatabaseTables.weather_hourly_staging
    unique_column = HourlyWeatherCols.hwc_local_date
    main_table_unique_constraint_name = HOURLY_WEATHER_UNIQUE_DATETIME_CONSTRAINT
    staging_table_unique_constraint_name = HOURLY_WEATHER_STAGING_UNIQUE_DATETIME_CONSTRAINT
    dtype_dictionary = dict(HOURLY_WEATHER_DATA_TYPES)
    progress_bar_prefix = "Backfilling hourly weather records"

    if years_code == 0: # NOTE: this means we do all years
        EXIT_CODE = backfill_weather_years( \
            MSC_GeoMet_weather_by_year=hourly_MSC_GeoMet_weather_by_year,
            main_table_name=main_table_name, staging_table_name=staging_table_name, 
            datetimecol=unique_column, main_table_unique_constraint_name=main_table_unique_constraint_name,
            staging_table_unique_constraint_name=staging_table_unique_constraint_name,
            dtype_dictionary=dtype_dictionary, progress_bar_prefix=progress_bar_prefix
        )
    else:
        EXIT_CODE = backfill_single_year( \
            year=years_code, MSC_GeoMet_weather_by_year=hourly_MSC_GeoMet_weather_by_year,
            main_table_name=main_table_name, staging_table_name=staging_table_name, datetimecol=unique_column,
            main_table_unique_constraint_name=main_table_unique_constraint_name,
            staging_table_unique_constraint_name=staging_table_unique_constraint_name, dtype_dictionary=dtype_dictionary
        )
    return EXIT_CODE



########################################################################################################################
### section 3:  call main
# this function will run by itself if this script is called, including the start & end time pieces

def main() -> None:
    # setup logging in main, when its run by itself
    logfile = Path(PROJECT_ROOT) / "data_pipeline" / "API" / "log_files" / f"{Path(__file__).stem}.log" # base log name on file name
    setup_logging(logfile) # NOTE: logging config already adds current time

    # log start
    logger.info(f"Script: {__file__} started.")# print statement for start of script, and current time

    # try _backfill_hourly_weather, log error if fails
    try:
        EXIT_CODE = _backfill_hourly_weather() # let's get our exit code
    except Exception as e:
        msg = f"Unexpected error while running {Path(__name__).name}: {e}"
        logger.critical(msg, exc_info=True)
        raise Exception(msg)

    # log end
    logger.info(f"Script: {__file__} completed with EXIT_CODE({EXIT_CODE}).")# print statement for end of script, and current time
    sys.exit(EXIT_CODE) # exit with exit code - important for making if a single year failed, but we continued onwards

if __name__ == "__main__":
    main()