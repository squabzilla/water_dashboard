########################################################################################################################
# file name: fetch_daily_weather.py
# author: William Hovdestad
#
# # The goal of this script is to fetch daily weather, to keep our PostGIS DailyWeather table up-to-date.
# This script is to be ran every day, to keep our data updated.
# It grabs the past 7 days just to be thorough (in case a day was missed somehow),
# but theoretically, only the past day should be needed.
# It should only insert data that does not already exist in the database.



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
# get path for environment so I can load it later
env_dir = os.path.expanduser(r"~/.config/water_dashboard/.env")



########################################################################################################################
### script-setup 2: library imports
from datetime import date, datetime, timedelta # for getting current date
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
    STATION_CLIMATE_IDENTIFIER, DAILY_WEATHER_PROPERTIES, DAILY_WEATHER_DATA_TYPES, DailyWeatherCols, DatabaseTables



########################################################################################################################
### script-setup 3: print statement for start of script, and current time
print(f"Script: {__file__} started at {datetime.now()}")



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
    "properties": DAILY_WEATHER_PROPERTIES, # filter to specific properties I want from station
}

# make the API call!
response = httpx.get(url, params=params, timeout=30.0) # api call
response.raise_for_status() # make sure status is good
response_output = response.json() # turn results into json

# convert to geojson
gdf = gpd.GeoDataFrame.from_features(response_output["features"]) # this apparently converts to geojson lol
# set CRS - newer geojsons don't have a CRS, and assume EPSG 4326 is CRS
gdf = set_geojson_crs(gdf)

# next, create unique column and double-check uniqueness
gdf[DailyWeatherCols.datetime_station] = \
    gdf[DailyWeatherCols.climate_identifier] + "-" + gdf[DailyWeatherCols.local_date] # merge stuff
if not gdf[DailyWeatherCols.datetime_station].is_unique: # check uniqueness:'
    raise CustomErrorMessage(f"ERROR - duplicate station-datetime combinations found in daily weather data. Aborting.")



########################################################################################################################
### section 2 - save our data, ensuring we only place in NEW values

# set engine
engine = default_SQL_engine()

# Write gdf_new to a temporary staging table
gdf.to_postgis(DatabaseTables.weather_data_daily_staging, engine, if_exists="replace", index=False,
                            dtype=dict(DAILY_WEATHER_DATA_TYPES) # unwrap to a regular dict for the function call
                            )

# add uniqueness constraint
sql_command = f"""
ALTER TABLE {DatabaseTables.weather_data_daily_staging}
DROP CONSTRAINT IF EXISTS uq_{DatabaseTables.weather_data_daily_staging}_{DailyWeatherCols.datetime_station};
ALTER TABLE {DatabaseTables.weather_data_daily_staging}
ADD CONSTRAINT uq_{DatabaseTables.weather_data_daily_staging}_{DailyWeatherCols.datetime_station} UNIQUE ("{DailyWeatherCols.datetime_station}");
"""
with engine.begin() as conn: conn.execute(text(sql_command))

# SQL command to insert only rows from staging that doesn't exist in main table
sql_command = f"""
INSERT INTO {DatabaseTables.weather_data_daily}
SELECT * FROM {DatabaseTables.weather_data_daily_staging}
ON CONFLICT ("{DailyWeatherCols.datetime_station}") DO NOTHING;
"""
with engine.connect() as conn:
    conn.execute(text(sql_command))
    conn.commit()
# NOTE: with `engine.connect()` you need to explicitly commit stuff, or changes aren't saved
# useful if I just want to read data, or test things without risking blowing up the database lol
# there's also advanced stuff you can do with a "non-default transaction isolation level" stuff

# SQL command to delete the staging table constraint, and then the entire staging table itself
# Is that needed? I don't know. Probably not. But I don't wanna worry about ghost constraints lol
sql_command = f"""
ALTER TABLE {DatabaseTables.weather_data_daily_staging}
DROP CONSTRAINT IF EXISTS uq_{DatabaseTables.weather_data_daily_staging}_{DailyWeatherCols.datetime_station};
DROP TABLE IF EXISTS {DatabaseTables.weather_data_daily_staging};
"""
with engine.begin() as conn: conn.execute(text(sql_command))
# NOTE: this one just executes and commits my changes to DB without needing to explicitly say so



########################################################################################################################
### END - print script finish statement
print(f"Script: {__file__} completed at {datetime.now()}")