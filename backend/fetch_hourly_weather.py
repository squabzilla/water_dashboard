########################################################################################################################
# file name: fetch_hourly_weather.py
# author: William Hovdestad
#
# The goal of this script is to retrieve hourly weather data from the following weather station:
# STATION_NAME: CALGARY INT'L CS; CLIMATE_IDENTIFIER: 3031094;
# We only want data for the past week, meaning the most recent 7 * 24 = 168 readings.
#
# Ideally this script will be ran every hour, and update our database with the results.
# However, currently we are just fetching the data, and saving it as GeoJSON.
# Once this step is complete, we'll focus on the logic for bringing it into the database.

"""
NOTE:
Given that I can't find an API to give us up-to-date climate data, with the available API seeming to cutoff
at 23:00hrs the previous day, I'm just not going to include hourly data in the MVP.

Again, it's something to look at incorporating later, but I can make the project MVP without it.

Remember, I can always add-on to the project later.
"""



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
    STATION_CLIMATE_IDENTIFIER, HOURLY_WEATHER_PROPERTIES, TABLE_NAMES, TABLE_COLS, HOURLY_CLIMATE_DATA_TYPES



########################################################################################################################
### section 1: grab weather data - copying some stuff from `fetch_historical_weather.py`

# url of API
url = "https://api.weather.gc.ca/collections/climate-hourly/items"

# get proper datetime string to use! first, subtract 1 week from current date
day_minus_seven = date.today() - timedelta(days=7)
# now, convert it to proper parameter to API call
datetime_param = str(day_minus_seven) + "T00:00:00Z/.."
# now, setup my parameters variable
params = {
    "limit": 200, # 8 * 25 = 200, I'm getting at most last 8 days * 24 hrs, so this should be good
    "CLIMATE_IDENTIFIER": STATION_CLIMATE_IDENTIFIER,
    "datetime": datetime_param,
    "properties": HOURLY_WEATHER_PROPERTIES, # filter to specific properties I want from station
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
    raise CustomErrorMessage(f"ERROR - duplicate station-datetime combinations found in hourly weather data. Aborting.")



########################################################################################################################
### section 2 - save our data, ensuring we only place in NEW values
"""
# set engine
engine = default_SQL_engine()

# Write gdf_new to a temporary staging table
gdf.to_postgis(TABLE_NAMES.weather_data_hourly_staging, engine, if_exists="replace", index=False,
                            dtype=dict(DAILY_CLIMATE_DATA_TYPES) # unwrap to a regular dict for the function call
                            )"""

keys_list = list(HOURLY_CLIMATE_DATA_TYPES)
#print(keys_list)

#output = Path(PROJECT_ROOT) / "backend" / "z_test_geojson.geojson"

#gdf.to_file(output, driver="GeoJSON")

print(len(gdf))