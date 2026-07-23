########################################################################################################################
# file name: fetch_hourly_weather.py
# author: William Hovdestad
#
# The goal of this script is to retrieve hourly weather data from the following weather station:
# STATION_NAME: CALGARY INT'L CS; CLIMATE_IDENTIFIER: 3031094;
# We only want data for the past week, meaning the most recent 7 * 24 = 168 readings.
#
# This script is designed to insert data into an existing PostGIS table in our database.
# Said table should have been created by `fetch_weather_hourly_historical.py`
# Specifically, it will insert the data into a temporary staging table, merge the staging-table with the "real" table,
# then delete the temporary staging table.
#
# Note that both of these use the same logic to retrieve raw data - the only difference 
# is whether the GeoDataFrame of the data is exported as a new table in PostGIS,
# or the data is inserted into an existing table.
# This is because it's easier to initialize a table in PostGIS by just exporting a GDF to POSTGIS
# then it is to create a table with specifications that precisely match our GDF.



########################################################################################################################
### API NOTES                                                                                                        ###

# NOTE: the API we call doesn't have current dates data
# so we get data for previous 7 days, but not current date
#
# Ideally this script will be ran every hour, and update our database with the results.
# However, currently we are just fetching the data, and saving it as GeoJSON.
# Once this step is complete, we'll focus on the logic for bringing it into the database.

"""
NOTE 1:

This API doesn't actually give me data of CURRENT date - it only goes up to date prior to current.

Given that I can't find an API to give us up-to-date climate data, with the available API seeming to cutoff
at 23:00hrs the previous day, I'm just not going to include hourly data in the MVP.

Again, it's something to look at incorporating later, but I can make the project MVP without it.

Remember, I can always add-on to the project later.
"""

"""
NOTE 2:

Testing has confirmed that the API takes the local date, so I don't need to worry about UTC conversion stuff.

I think there IS a way to use the UTC date, but that would add unnecessary work.

However, I should probably explicitly tell all my timezone stuff to use the edmonton timezone
Otherwise I might have problems if I deploy it, and the deployment server ends up being in a different timezone...
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
from datetime import date, datetime, time, timedelta # for getting current date
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
    STATION_CLIMATE_IDENTIFIER, HOURLY_WEATHER_PROPERTIES, HOURLY_WEATHER_DATA_TYPES, HourlyWeatherCols, DatabaseTables



########################################################################################################################
### section 1: grab hourly weather data

# url of API
url = "https://api.weather.gc.ca/collections/climate-hourly/items"

# get proper datetime string to use! first, subtract 1 week from current date
my_time_zone = ZoneInfo("America/Edmonton")
today_date = datetime.now(my_time_zone).date() # gets today's date as datetime so I can include timezone, then make it date
day_minus_seven = today_date - timedelta(days=7) # subtract 7 days from current date
# now, convert it to proper parameter to API call
datetime_param = str(day_minus_seven) + "T00:00:00Z/.."
# NOTE: This gives me 12:00am from 7 days ago

### NOTE: Testing shit
day_minus_nine = today_date - timedelta(days=9) # subtract 7 days from current date
datetime_param = str(day_minus_nine) + "T00:00:00Z/.."


# now, setup my parameters variable
params = {
    "limit": 250, # 8 * 25 = 200, I'm getting at most last 8 days * 24 hrs, so this should be good
    "CLIMATE_IDENTIFIER": STATION_CLIMATE_IDENTIFIER,
    "datetime": datetime_param,
    "properties": HOURLY_WEATHER_PROPERTIES, # filter to specific properties I want from station
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
gdf[HourlyWeatherCols.datetime_station] = gdf[HourlyWeatherCols.climate_identifier] + "-" + gdf[HourlyWeatherCols.local_date] # merge stuff
# if not gdf["DATETIME_STATION"].is_unique: # check uniqueness:'
if not gdf[HourlyWeatherCols.datetime_station].is_unique: # check uniqueness:'
    raise CustomErrorMessage(f"ERROR - duplicate station-datetime combinations found in hourly weather data. Aborting.")

### NOTE: if I want to print number of records
#print(gdf.shape[0]) # print number of records


########################################################################################################################
### section 2 - save our data, ensuring we only place in NEW values

# set engine
engine = default_SQL_engine()

# Write gdf_new to a temporary staging table

gdf.to_postgis(DatabaseTables.weather_data_hourly_staging, engine, if_exists="replace", index=False,
                            dtype=dict(HOURLY_WEATHER_DATA_TYPES) # unwrap to a regular dict for the function call
                            )
# make sure column is unique
sql_command = f"""
ALTER TABLE {DatabaseTables.weather_data_hourly_staging}
DROP CONSTRAINT IF EXISTS uq_{DatabaseTables.weather_data_hourly_staging}_{HourlyWeatherCols.datetime_station};
ALTER TABLE {DatabaseTables.weather_data_hourly_staging}
ADD CONSTRAINT uq_{DatabaseTables.weather_data_hourly_staging}_{HourlyWeatherCols.datetime_station} UNIQUE ("{HourlyWeatherCols.datetime_station}");
"""
with engine.begin() as conn: conn.execute(text(sql_command))


# SQL command to insert only rows from staging that doesn't exist in main table
sql_command = f"""
INSERT INTO {DatabaseTables.weather_data_hourly}
SELECT * FROM {DatabaseTables.weather_data_hourly_staging}
ON CONFLICT ("{HourlyWeatherCols.datetime_station}") DO NOTHING;
"""
with engine.begin() as conn: conn.execute(text(sql_command))

# SQL command to delete the staging table constraint, and then the entire staging table itself
# Is that needed? I don't know. Probably not. But I don't wanna worry about ghost constraints lol
sql_command = f"""
ALTER TABLE {DatabaseTables.weather_data_hourly_staging}
DROP CONSTRAINT IF EXISTS uq_{DatabaseTables.weather_data_hourly_staging}_{HourlyWeatherCols.datetime_station};
DROP TABLE IF EXISTS {DatabaseTables.weather_data_hourly_staging};
"""
with engine.begin() as conn: conn.execute(text(sql_command))

# SQL command to delete rows from main table prior to days_minus_seven
# note - it's easier to just have up to a day of extra info, rather than delete records from over PRECISELY 7 * 24hrs ago

cutoff_date = datetime.combine(day_minus_seven, time.min) # gets min time on days_minus_seven, so 12:00am


sql_command = f"""
DELETE FROM {DatabaseTables.weather_data_hourly}
WHERE "{HourlyWeatherCols.local_date}" < '{cutoff_date}';
"""
# NOTE: are you fucking me sideways with a jellyfish why in gods name does the type of fucking quotation mark matter in sql you drunk dumbfuck squirrel
# NOTE 2: "In PostgreSQL, single quotes (') are used for string literals (text values), while double quotes (") are used for identifiers (table and column names)"
with engine.begin() as conn: conn.execute(text(sql_command))