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
### section 1: errors
class BackfillError(Exception):
    """Base class for backfill-related failures."""

class WeatherAPITimeoutError(BackfillError):
    """Network timeout calling the GeoMet API."""

class WeatherAPIResponseError(BackfillError):
    """API responded, but the payload was malformed or unexpected."""

class WeatherDBError(BackfillError):
    """DB write failed (constraint violation, connection issue, etc.)."""



########################################################################################################################
### section 2: get_hourly_weather
def hourly_MSC_GeoMet_weather_by_year(year: int) -> None:
    try:
        raw = fetch_hourly_data(year)          # httpx call
    except httpx.TimeoutException as e:
        raise WeatherAPITimeoutError(f"Timed out fetching {year}") from e
    except httpx.HTTPStatusError as e:
        raise WeatherAPIResponseError(f"Bad status for {year}: {e.response.status_code}") from e
    except:
        raise CustomErrorMessage("soup")

    try:
        gdf = parse_and_validate(raw)           # JSON/schema parsing
    except (json.JSONDecodeError, KeyError, ValidationError) as e:
        raise WeatherAPIResponseError(f"Malformed response for {year}: {e}") from e

    try:
        upload_to_postgis(gdf)                  # staging + upsert
    except IntegrityError as e:
        raise WeatherDBError(f"Constraint violation for {year}: {e}") from e

hourly_MSC_GeoMet_weather_by_year(2020)