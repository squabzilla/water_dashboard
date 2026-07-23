########################################################################################################################
# file name: fetch_weatherstation.py
# author: William Hovdestad
#
# The goal of this script is to retrieve daily weather data from the following weather station:
# STATION_NAME: CALGARY INT'L CS; CLIMATE_IDENTIFIER: 3031094;



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
from backend.helper_progress_bar import update_progress_bar
from backend.helper_error import CustomErrorMessage
from backend.helper_PSQL import default_SQL_engine, set_geojson_crs,\
    STATION_CLIMATE_IDENTIFIER, DAILY_WEATHER_PROPERTIES, DAILY_WEATHER_DATA_TYPES, DailyWeatherCols, DatabaseTables#, CUSTOM_TABLE_COLS



########################################################################################################################
### section 1: function that grabs all data for relevant station

### ALSO: LINK I'M USING:
# NOTE: IMPORANT: LINK I'M REFERENCING: https://api.weather.gc.ca/openapi?f=html#

# url for API
url = "https://api.weather.gc.ca/collections/climate-stations/items"

# actual API call - make request, do response.wait-for-update, return the response data
params = {"CLIMATE_IDENTIFIER": STATION_CLIMATE_IDENTIFIER}

# sends an HTTP GET request to the URL
# NOTE: everything is stored in response - status code, headers, body
response = httpx.get(url, params=params, timeout=30.0)

# checks that status code is "200" which means everything is ok
response.raise_for_status()

# turn raw response body text into Python dictionary
response_output = response.json()

# grab only items from "features" in said dictionary for GeoDataFrame,
# since API returns a GeoJSON `FeatureCollection` that wraps actualy data inside "features" key,
# and the data I ACTUALLY care about is inside "properties" inside of "features"
# station = response_output["features"]
# NOTE: could also do that in one step
# station = response.json()["features"]["properties"]
gdf_weather_station = gpd.GeoDataFrame.from_features(response_output["features"]) # this apparently converts to geojson lol

# NOTE: newer geojsons don't have a CRS, and assume EPSG 4326 is CRS
gdf_weather_station = set_geojson_crs(gdf_weather_station)



########################################################################################################################
### section 3 - actually save our data to use later

# set engine
engine = default_SQL_engine()

# add weather station data to PostGIS
gdf_weather_station.to_postgis(DatabaseTables.weather_stations, engine, if_exists="replace", index=False)