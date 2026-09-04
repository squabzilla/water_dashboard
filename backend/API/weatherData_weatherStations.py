########################################################################################################################
# file name: fetch_weatherstation.py
# author: William Hovdestad
#
# The goal of this script is to retrieve daily weather data from the following weather station:
# STATION_NAME: CALGARY INT'L CS    CLIMATE_IDENTIFIER: 3031094
# STATION_NAME: CALGARY INTL A      CLIMATE_IDENTIFIER: 3031092
# STATION_NAME: CALGARY INT'L A     CLIMATE_IDENTIFIER: 3031093
# and store them in our PostGIS Database



########################################################################################################################
### script-setup 1: project-root-setup
import os
import sys
from pathlib import Path
#from dotenv import load_dotenv

# gets file-path, (hopefully) resolves relative path issues, gets great-grand-parent folder
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# sets working directory to project root - there may be redundancy here but oh well lol
os.chdir(PROJECT_ROOT)
# Ensure repository code is importable when this wrapper is run directly.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
# get path for environment so I can load it later
#env_dir = os.path.expanduser(r"~/.config/water_dashboard/.env")



########################################################################################################################
### script-setup 2: library imports
from datetime import datetime # used to get current time
import psycopg # stuff needed to connect with postgis database
import sqlalchemy # stuff needed to connect with postgis database
from sqlalchemy import text # make pylance happy by recognizing this as a keyword lol
from sqlalchemy import create_engine # stuff needed to connect with postgis database
import geopandas as gpd # geospatial library, used for GeoDataFrames
#from shapely.geometry import Point # used to properly format lat/long values for use by GeoPandas
import httpx # used for calling API
#from dateutil.parser import parse # used for properly formatting DATE data into datetime variables
import json # used for handling export of json data
import logging # used to log stuff
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

# custom modules!
# from backend.helper_PSQL import default_SQL_engine, set_geojson_crs, STATION_CLIMATE_IDENTIFIER, DatabaseTables
from backend.helper.helper_PSQL_config import default_SQL_engine
from backend.helper.helper_set_geojson_crs import set_geojson_crs
#from backend.helper.helper_SQL_tables import STATION_CLIMATE_IDENTIFIER, DatabaseTables, STATION_CLIMATE_IDENTIFIERS, DailyWeatherCols
from backend.helper.helper_SQL_tables import DailyWeatherCols, DatabaseTables, PRIMARY_STATION_ID, SECONDARY_STATION_ID, TERTIARY_STATION_ID
from backend.helper.helper_API_errors import APITimeoutError, APIResponseError, DBError
from backend.API.weather_helper_API import fetch_weather_pages
from backend.helper.helper_DB_update import export_as_new_table



########################################################################################################################
### script-setup 3: logging config
logfile = Path(PROJECT_ROOT) / "backend" / "API" / "log_files" / "weather_stations_backfill.log"
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
### section 1: local helper functions

# but first, a global variable:

"""
@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    # decorator itself, and the condition for retrying anything at all
    stop=stop_after_attempt(4), # tells tenacity when to give up - after 4 attemps (1 initial call, 3 retries)
    wait=wait_exponential(multiplier=1, min=2, max=30),
    # wait an increasing time between each attempt;
    # the `max` setting is redundant since we stop after attempt 4, but redundancy is good in this case
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _get_station() -> dict:
    # NOTE: IMPORANT: LINK I'M REFERENCING: https://api.weather.gc.ca/openapi?f=html#

    # url for API

    # actual API call - make request, do response.wait-for-update, return the response data
    ids_clause = f"{PRIMARY_STATION_ID}, {SECONDARY_STATION_ID}, {TERTIARY_STATION_ID}"
    params = {"filter": f"properties.{DailyWeatherCols.climate_identifier} IN ({ids_clause})",}

    # sends an HTTP GET request to the URL
    # NOTE: everything is stored in response - status code, headers, body
    response = httpx.get(WEATHER_STATION_URL, params=params, timeout=30.0)

    # checks that status code is "200" which means everything is ok
    response.raise_for_status()

    # turn raw response body text into Python dictionary
    response_output = response.json()
    return response_output
"""




########################################################################################################################
### section 2: main
"""
def main() -> None:
    try:
        response_output = _get_station()
    except httpx.TimeoutException as e:
            raise APITimeoutError(f"Timed out fetching {WEATHER_STATION_URL} after retries") from e
    except httpx.ConnectError as e:
        raise APITimeoutError(f"Connection error fetching {WEATHER_STATION_URL} after retries") from e
    except httpx.HTTPStatusError as e:
        raise APIResponseError(f"Bad status fetching {WEATHER_STATION_URL}: {e.response.status_code}") from e
    except (KeyError, json.JSONDecodeError) as e:
        raise APIResponseError(f"Malformed page while paginating {WEATHER_STATION_URL}: {e}") from e

    try:
        gdf_weather_station = gpd.GeoDataFrame.from_features(response_output["features"])
    except:
        raise APIResponseError("ERROR - response json in unexpected format, regular JSON parsing failed.")

    # NOTE: newer geojsons don't have a CRS, and assume EPSG 4326 is CRS
    gdf_weather_station = set_geojson_crs(gdf_weather_station)

    # actually save data to use later
    try:
        engine = default_SQL_engine()
        gdf_weather_station.to_postgis(DatabaseTables.weather_stations, engine, if_exists="replace", index=False)
    except:
        raise DBError("ERROR - could not upload weather stations to PostGIS Database.")
"""

def main() -> None:
    WEATHER_STATION_URL = "https://api.weather.gc.ca/collections/climate-stations/items"
    ids_clause = f"{PRIMARY_STATION_ID}, {SECONDARY_STATION_ID}, {TERTIARY_STATION_ID}"
    params = {
        "limit": 1000,
        "filter": f"properties.{DailyWeatherCols.climate_identifier} IN ({ids_clause})",
    }
    job_title = "fetching_weather_stations"
    gdf_weather_station = fetch_weather_pages(start_url=WEATHER_STATION_URL, params=params, job_title=job_title)
    engine = default_SQL_engine()
    try:
        engine = default_SQL_engine()
        gdf_weather_station.to_postgis(DatabaseTables.weather_stations, engine, if_exists="replace", index=False)
    except:
        raise DBError("ERROR - could not upload weather stations to PostGIS Database.")


"""
def export_as_new_table(gdf: gpd.GeoDataFrame, engine: Engine,
                        main_table_name: str, dtype_dictionary: dict,
                        main_table_unique_constraint_name: str, unique_column: str) -> None:
"""


# call main
# this function will run by itself if this script is called, including the start & end time pieces
if __name__ == "__main__":
    logger.info(f"Script: {__file__} started at {datetime.now()}")# print statement for start of script, and current time
    main()
    logger.info(f"Script: {__file__} completed at {datetime.now()}")# print statement for end of script, and current time