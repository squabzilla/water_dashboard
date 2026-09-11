"""
file name: fetch_weatherstation.py
author: William Hovdestad

The goal of this script is to retrieve daily weather data from the following weather station:
STATION_NAME: CALGARY INT'L CS    CLIMATE_IDENTIFIER: 3031094
STATION_NAME: CALGARY INTL A      CLIMATE_IDENTIFIER: 3031092
STATION_NAME: CALGARY INT'L A     CLIMATE_IDENTIFIER: 3031093
and store them in our PostGIS Database
"""



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



########################################################################################################################
### script-setup 2: library imports
from datetime import datetime # for getting date-time stuff
import psycopg # stuff needed to connect with postgis database
import sqlalchemy # stuff needed to connect with postgis database
import geopandas as gpd # geospatial library, used for GeoDataFrames
import httpx # used for calling API
import json # used for handling export of json data
import logging # used to log stuff


# custom modules!
from data_pipeline.helper.helper_PSQL_config import default_SQL_engine
from data_pipeline.helper.helper_SQL_tables import DatabaseTables, PRIMARY_STATION_ID, SECONDARY_STATION_ID, TERTIARY_STATION_ID
from data_pipeline.helper.helper_API_errors import DBError
from data_pipeline.API.weather_helper_API import fetch_weather_pages



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
### section 1: main - script that gets weather stations

def main() -> None:
    WEATHER_STATION_URL = "https://api.weather.gc.ca/collections/climate-stations/items"
    ids_clause = f"{PRIMARY_STATION_ID}, {SECONDARY_STATION_ID}, {TERTIARY_STATION_ID}"
    params = {
        "limit": 1000,
        "filter": f"properties.CLIMATE_IDENTIFIER IN ({ids_clause})",
    }
    job_title = "fetching_weather_stations"
    gdf_weather_station = fetch_weather_pages(start_url=WEATHER_STATION_URL, params=params, job_title=job_title)
    engine = default_SQL_engine()
    try:
        engine = default_SQL_engine()
        gdf_weather_station.to_postgis(DatabaseTables.weather_stations, engine, if_exists="replace", index=False)
    except:
        msg = "Error: DBError: could not upload weather stations to PostGIS Database."
        logger.error(msg)
        raise DBError(msg)



########################################################################################################################
### section 2 - call main

# this function will run by itself if this script is called, including the start & end time pieces

if __name__ == "__main__":
    logger.info(f"Script: {__file__} started at {datetime.now()}")# print statement for start of script, and current time
    main()
    logger.info(f"Script: {__file__} completed at {datetime.now()}")# print statement for end of script, and current time