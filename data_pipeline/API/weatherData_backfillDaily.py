"""
file name: weather_daily_backfill.py
author: William Hovdestad

This script is used to backfill our PostGIS-PSQL database with daily-weather-values.

This script has two parts. The first is a function called `daily_MSC_GeoMet_weather_by_year`
which is passed a year, and returns a geoDataFrame.
It calls the `fetch_MSC_GeoMet_weather` from the `weather_APIlogic.py` file in order to retrieve
the data from the API.

The second part: it calls the `backfill_weather_years` function from `weather_helper_backfill.py`,
as that script contains the logic to loop through all of the relevant years for backfilling our database.
Note that the `backfill_weather_years` function is designed to TAKE a function as input -
a function that takes an integer YEAR as input.

The API in question:
This script uses the `climate-daily` data from the Canada weather API
link: https://api.weather.gc.ca/openapi?f=html#/climate-daily

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
from datetime import datetime # for getting date-time stuff
import psycopg # stuff needed to connect with postgis database
import sqlalchemy # stuff needed to connect with postgis database
from sqlalchemy import text # make pylance happy by recognizing this as a keyword lol
from sqlalchemy import create_engine # stuff needed to connect with postgis database
import numpy as np # because I guess `np.nan` is better than `pd.NA` for no-data-values in Pandas?
import pandas as pd # just for merging dataframes, otherwise we use geopandas lol
import geopandas as gpd # geospatial library, used for GeoDataFrames
import httpx # used for calling API
import json # used for handling export of json data
import logging

# custom modules!
from data_pipeline.helper.helper_timezones import AB_TIME
from data_pipeline.helper.helper_SQL_tables import DAILY_WEATHER_PROPERTIES, DAILY_WEATHER_DATA_TYPES, \
    DailyWeatherCols, DatabaseTables, DAILY_WEATHER_UNIQUE_DATE_CONSTRAINT, DAILY_WEATHER_STAGING_UNIQUE_DATE_CONSTRAINT
from data_pipeline.API.weather_helper_API import fetch_weather_pages
from data_pipeline.API.weather_helper_filterStationPriority import filter_stations_by_priority
from data_pipeline.API.weather_helper_backfill import backfill_weather_years
from data_pipeline.helper.helper_API_errors import DataUniquenessConstraintViolation
from data_pipeline.helper.helper_SQL_tables import STN_IDS_STR_CSV_LIST



########################################################################################################################
### script-setup 3: logging config
logfile = Path(PROJECT_ROOT) / "data_pipeline" / "API" / "log_files" / f"{Path(__file__).stem}.log" # base log name on file name
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[ # handles output stuff
        logging.FileHandler(logfile), # handles output file
        #logging.StreamHandler() # writes log to a "stream" which by default is terminal/console
        # NOTE: turning this on breaks my progress bar lol
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

def daily_MSC_GeoMet_weather_by_year(year: int) -> gpd.GeoDataFrame:
    daily_weather_url = "https://api.weather.gc.ca/collections/climate-daily/items"

    daily_weather_params = {
        "limit": 1000,
        "filter": f"properties.{DailyWeatherCols.dwc_climate_identifier} IN ({STN_IDS_STR_CSV_LIST})",
        f"{DailyWeatherCols.dwc_local_year}": year,
        "properties": DAILY_WEATHER_PROPERTIES, # filter to specific properties I want from station
    }

    gdf = fetch_weather_pages(start_url=daily_weather_url, params=daily_weather_params,
                              job_title=f"historical-daily-weather-records-year-{year}")

    gdf = filter_stations_by_priority(gdf, station_id_col=DailyWeatherCols.dwc_climate_identifier,
                                      datetime_col=DailyWeatherCols.dwc_local_date)

    # NOTE: dates should be unique now, so let's check that
    if not gdf[DailyWeatherCols.dwc_local_date].is_unique:
        msg = f"Error: DataUniquenessConstraintViolation: dates not unique for daily-weather backfill year {year}"
        logger.error(msg)
        raise DataUniquenessConstraintViolation(msg)

    return gdf



########################################################################################################################
### section 2: main-function to loop through years

def main() -> None:
    main_table_name = DatabaseTables.weather_daily
    staging_table_name = DatabaseTables.weather_daily_staging
    unique_column = DailyWeatherCols.dwc_local_date
    main_table_unique_constraint_name = DAILY_WEATHER_UNIQUE_DATE_CONSTRAINT
    staging_table_unique_constraint_name = DAILY_WEATHER_STAGING_UNIQUE_DATE_CONSTRAINT
    dtype_dictionary = dict(DAILY_WEATHER_DATA_TYPES)
    progress_bar_prefix = "Backfilling daily weather records"

    backfill_weather_years(MSC_GeoMet_weather_by_year=daily_MSC_GeoMet_weather_by_year,
                           main_table_name=main_table_name, staging_table_name=staging_table_name, 
                           datetimecol=unique_column, main_table_unique_constraint_name=main_table_unique_constraint_name,
                           staging_table_unique_constraint_name=staging_table_unique_constraint_name,
                           dtype_dictionary=dtype_dictionary, progress_bar_prefix=progress_bar_prefix)



########################################################################################################################
### section 2:  call main
# this function will run by itself if this script is called, including the start & end time pieces
if __name__ == "__main__":
    logger.info(f"Script: {__file__} started at {datetime.now(AB_TIME)}")# print statement for start of script, and current time
    main()
    logger.info(f"Script: {__file__} completed at {datetime.now(AB_TIME)}")# print statement for end of script, and current time