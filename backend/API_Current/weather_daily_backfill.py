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

# custom modules!
from backend.helper_progress_bar import update_progress_bar
from backend.helper_error import CustomErrorMessage
from backend.helper.helper_SQL_tables import DAILY_WEATHER_PROPERTIES, DAILY_WEATHER_DATA_TYPES, \
    DailyWeatherCols, HourlyWeatherCols, DatabaseTables, HOURLY_WEATHER_PROPERTIES, \
    PRIMARY_STATION_ID, SECONDARY_STATION_ID, TERTIARY_STATION_ID, \
    SWOB_PROPERTIES, HOURLY_SWOB_CONVERSION
from backend.helper.helper_set_geojson_crs import set_geojson_crs



########################################################################################################################
### section 1: function to fetch weather for given year
def daily_MSC_GeoMet_weather_by_year(year: int, silent: bool=False):
    ids_clause = f"{PRIMARY_STATION_ID}, {SECONDARY_STATION_ID}, {TERTIARY_STATION_ID}"
    daily_weather_url = "https://api.weather.gc.ca/collections/climate-daily/items"
    daily_weather_params = {
        "limit": 1000,
        "filter": f"properties.{DailyWeatherCols.climate_identifier} IN ({ids_clause})",
        f"{DailyWeatherCols.local_year}": year,
    }


########################################################################################################################
### section 2: call the function for every year

#current_year = date.today().year
#print(current_year)
start_year = 1956
next_year = current_year = date.today().year + 1
for year in range(start_year, next_year):
    try: daily_MSC_GeoMet_weather_by_year(year)
    except: raise CustomErrorMessage(f"Error retrieving data for year {year} - aborting.")