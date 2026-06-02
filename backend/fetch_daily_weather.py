########################################################################################################################
# file name: fetch_daily_weather.py
# author: William Hovdestad
#
# The goal of this script is to fetch daily weather for the past 7 days.
# This script is to be ran every day, to keep our data updated.
# It grabs the past 7 days just to be thorough (in case a day was missed somehow),
# but realistically only the past day is needed.
# It should only insert data that does not already exist in the database.



########################################################################################################################
### script-setup 1: project-root-setup
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# gets file-path, (hopefully) resolves relative path issues, gets grand-parent folder
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# sets working directory to project root - there may be redundancy here but oh well lol
os.chdir(PROJECT_ROOT)
# Ensure repository code is importable when this wrapper is run directly.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
# get path for environment so I can load it later
env_dir = os.path.expanduser(r"~/.config/water_dashboard/.env")



########################################################################################################################
### script-setup 2: library imports
from datetime import date, timedelta # for getting current date
from zoneinfo import ZoneInfo # for time zones
import psycopg # stuff needed to connect with postgis database
import sqlalchemy # stuff needed to connect with postgis database
from sqlalchemy import text # make pylance happy by recognizing this as a keyword lol
from sqlalchemy import create_engine # stuff needed to connect with postgis database
import geopandas as gpd # geospatial library, used for GeoDataFrames
#from shapely.geometry import Point # used to properly format lat/long values for use by GeoPandas
import httpx # used for calling API
#from dateutil.parser import parse # used for properly formatting DATE data into datetime variables
import json # used for handling export of json data

# custom modules!
from backend.helper_error import CustomErrorMessage
from backend.helper_PSQL import default_SQL_engine, set_geojson_crs,\
    STATION_CLIMATE_IDENTIFIER, WEATHER_PROPERTIES, TABLE_NAMES, TABLE_COLS, DAILY_CLIMATE_DATA_TYPES



########################################################################################################################
### section 1: grab weather data - copying some stuff from `fetch_historical_weather.py`

# url of API
url = "https://api.weather.gc.ca/collections/climate-daily/items"

# get proper datetime string to use! first, subtract 1 week from current date
day_minus_seven = date.today() - timedelta(days=7)
# now, convert it to proper parameter to API call
datetime_param = str(day_minus_seven) + "T00:00:00Z/.."
# now, setup my parameters variable
params = {
    "limit": 100, # this should actually be irrelevant since theoretically I'm only getting like 8 items
    "CLIMATE_IDENTIFIER": STATION_CLIMATE_IDENTIFIER,
    "datetime": datetime_param,
    "properties": WEATHER_PROPERTIES, # filter to specific properties I want from station
}

# make the API call!
response = httpx.get(url, params=params) # api call
response.raise_for_status() # make sure status is good
response_output = response.json() # turn results into json

# convert to geojson
gdf = gpd.GeoDataFrame.from_features(response_output["features"]) # this apparently converts to geojson lol
# set CRS - newer geojsons don't have a CRS, and assume EPSG 4326 is CRS
gdf = set_geojson_crs(gdf)

# next, create unique column and double-check uniqueness
gdf[TABLE_COLS.datetime_station] = gdf["CLIMATE_IDENTIFIER"] + "-" + gdf["LOCAL_DATE"] # merge stuff
if not gdf["DATETIME_STATION"].is_unique: # check uniqueness:'
    raise CustomErrorMessage(f"ERROR - duplicate station-datetime combinations found in weather data. Aborting.")



########################################################################################################################
### section 2 - save our data, ensuring we only place in NEW values

# set engine
engine = default_SQL_engine()

# Write gdf_new to a temporary staging table
gdf.to_postgis(TABLE_NAMES.weather_data_staging, engine, if_exists="replace", index=False,
                            dtype=dict(DAILY_CLIMATE_DATA_TYPES) # unwrap to a regular dict for the function call
                            )

# SQL command to insert only rows from staging that doesn't exist in main table
sql_command = f"""
INSERT INTO {TABLE_NAMES.weather_data}
SELECT * FROM {TABLE_NAMES.weather_data_staging}
ON CONFLICT ("{TABLE_COLS.datetime_station}") DO NOTHING;
"""
with engine.connect() as conn:
    conn.execute(text(sql_command))
    conn.commit()
# NOTE: with `engine.connect()` you need to explicitly commit stuff, or changes aren't saved
# useful if I just want to read data, or test things without risking blowing up the database lol
# there's also advanced stuff you can do with a "non-default transaction isolation level" stuff

# SQL command to delete staging table
sql_command = f"""
DROP TABLE IF EXISTS {TABLE_NAMES.weather_data_staging};
"""
with engine.begin() as conn:
    conn.execute(text(sql_command))
# NOTE: this one just executes and commits my changes to DB without needing to explicitly say so

# SQL commands to be used in QGIS-testing
# first one deletes 3 most recent records
# second one selects 3 most recent records
# so I can select 3 most recent records, then delete 3 most recent records, select 3 most recent records again to observe change
sql_command = f"""
DELETE FROM "public"."weather_data" WHERE "LOCAL_DATE" IN (
SELECT "LOCAL_DATE" FROM "public"."weather_data" ORDER BY "LOCAL_DATE" DESC LIMIT 3
)

SELECT * FROM "public"."weather_data" ORDER BY "LOCAL_DATE" DESC LIMIT 3
"""