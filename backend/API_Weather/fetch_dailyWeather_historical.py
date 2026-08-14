########################################################################################################################
# file name: fetch_historical_weather.py
# author: William Hovdestad
#
# The goal of this script is to retrieve daily weather data from the following weather station:
# STATION_NAME: CALGARY INTL A; CLIMATE-IDENTIFIERS: 3031092 (older) & 3031093 (newer)
# This script wants to fetch historical data from Jan-01-2000 up to current date.
# Because this is looking at daily data, we shouldn't need to worry about timezones.



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
import argparse # used for adding command line arguments to script
from datetime import datetime # used to get current time
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
from backend.helper_PSQL import default_SQL_engine, set_geojson_crs, STATION_NAME, \
    STATION_CLIMATE_IDENTIFIER, DAILY_WEATHER_PROPERTIES, DAILY_WEATHER_DATA_TYPES, DailyWeatherCols, DatabaseTables



########################################################################################################################
### script-setup 3: print statement for start of script, and current time
print(f"Script: {__file__} started at {datetime.now()}")



########################################################################################################################
### script-setup 4: setup command line arguments for script
parser = argparse.ArgumentParser()
parser.add_argument("-s", "--silent", help="silence script output when running",
                    action="store_true")
args = parser.parse_args()
# if not args.silent: # this lets us turn off printing the progress bar if we add -s when running!
# stuff in this if-statement will only execute if the "-s" argument wasn't passed



########################################################################################################################
### section 1: paginate through API, using recursive-function to paginate

#############################################
# section 1.0 - set up variables for API call
#############################################

# url of API
url = "https://api.weather.gc.ca/collections/climate-daily/items"

# STATION_NAME = "CALGARY INT'L A"


########################################################
# section 1.1 - create function for API call
########################################################

# def fetch_daily_climate_items(stn_name, url=url):
all_data = []
total_records = 1000 # arbitary total records thats higher then limit, properly set later
# put parameters together in one dictionary
params = {
    "limit": 1000,
    # "CLIMATE_IDENTIFIER": STATION_CLIMATE_IDENTIFIER,
    #"CLIMATE_IDENTIFIER": stn_clim_id,
    "STATION_NAME": STATION_NAME,
    "datetime": "2000-01-01T00:00:00Z/..", # per documentation, this should filter it to dates 1956-01-01 and higher
    # NOTE: first recorded watermain break is 1956/01/01
    "properties": DAILY_WEATHER_PROPERTIES, # filter to specific properties I want from station
}

STATION_CLIMATE_IDENTIFIERS = ("3031092", "3031093")
# CQL2 string values must be single-quoted
ids_clause = ", ".join(f"'{sid}'" for sid in STATION_CLIMATE_IDENTIFIERS)

params = {
    "limit": 1000,
    "filter": f"properties.CLIMATE_IDENTIFIER IN ({ids_clause})",
    "datetime": "2000-01-01T00:00:00Z/..", # per documentation, this should filter it to dates 1956-01-01 and higher
    "properties": DAILY_WEATHER_PROPERTIES,
}


####################################################################
# section 1.2 - run a quick query to determine total number of items
####################################################################
# NOTE:
# while our "quick call" limits the number of returned objects to just 1 (one),
# it still returns the meta-data information about how many total objects match our parameters

params["limit"] = 1 # set limit to 1 for our quick call
response = httpx.get(url, params=params) # api call
params["limit"] = 1000 # reset limit back to what it should be
response.raise_for_status() # make sure status is good
response_output = response.json() # turn results into json
response_expected = response_output["numberMatched"] # get expected number of responses
page_count = (response_expected / params["limit"]).__ceil__()

matches = response_output['numberMatched']
if matches == 0:
    raise CustomErrorMessage("ERROR - no matches found. Aborting.")

# loop thru results with pagination!


####################################################
# section 1.3 - setup variables for progress bar lol
####################################################

# remember, we're paginating over the API results
total_iterations = page_count
prefix = f"Fetching daily weather records..."
current_page = 0
if not args.silent: # this lets us turn off printing the progress bar if we add -s when running!
    update_progress_bar(iteration=current_page, total=total_iterations, prefix=prefix)


########################################################################################
# section 1.4 - setup recursive function, so it calls itself if there's more pages to go
########################################################################################

# NOTE:
# the first time we query the API, we include our parameters in the query
# however, once we start paginating, we query the API using the "next" link,
# and DON'T include the parameters!
# since the "next" link has all the relevant parameters, including pagination, already built in
def paginate_url(url, current_page, include_params=False, params=params):

    # Set page number, emergency-return if over page number
    current_page += 1 # increase the page-count to current page - note that we should START at `current_page = 0`
    if current_page > page_count: return 0 # emergency return just-in-case

    ## API call - note the if/else statement for if we want to include OUR parameters or not
    if include_params == True: response = httpx.get(url, params=params, timeout=60.0)
    # api-call with parameters, if include_params = True - for first API call
    else:  response = httpx.get(url, timeout=60.0) # api call
    # api-call WITHOUT parameters, if include_params = False - for second API call & onwards

    # rest of the API call
    response.raise_for_status() # make sure status is good
    response_output = response.json() # turn results into json

    # get data from API call
    data = response_output.get("features",[])
    # get items from "features" key, returns empty list (square-brackets) is key missing
    all_data.extend(data)
    # add `data` to `all_data`, extend works better than append for REASONS

    # now let's increase our progress bar, since we just added some data
    if not args.silent:
        update_progress_bar(iteration=current_page, total=total_iterations, prefix=prefix)

    # now we look for the URL of the "next" page, and call this function again if we find it
    links = response_output["links"]
    for item in links:
        if item["rel"] == "next":
        # "rel" is like the key for the, uh, 'rank' of the link? as opposed to its title/name?
            new_url = item["href"]
            paginate_url(new_url, current_page)

# whew, all that is done! now we can actually CALL our function
paginate_url(url, current_page=0, include_params=True)


##########################################################
# section 1.5 - check results, convert to GDF, process GDF
##########################################################
# lets confirm our results match...
if not args.silent:
    print(f" Expected responses: {response_expected}; actual: {len(all_data)}")
# spit out an error if they don't
expected_vs_actual_error =\
f"ERROR - Missmatch between expected number of results ({response_expected}) and actual number ({len(all_data)}). Aborting."
if response_expected != len(all_data):
    raise CustomErrorMessage(expected_vs_actual_error)

# gdf = gpd.GeoDataFrame.from_features(response_output["features"]) # this apparently converts to geojson lol
gdf_daily_weather_data = gpd.GeoDataFrame.from_features(all_data) # I already selected the "features" key while looping thru data
del all_data # we don't need this anymore

# first, set the crs - NOTE: newer geojsons don't have a CRS, and assume EPSG 4326 is CRS
gdf_daily_weather_data = set_geojson_crs(gdf_daily_weather_data)

print(f"Number of records: {len(gdf_daily_weather_data)}")
print("head:")
print(gdf_daily_weather_data.head(1))
print(f"'STATION_NAME' values & counts:\n{gdf_daily_weather_data['STATION_NAME'].value_counts()}\n")
print(f"'CLIMATE_IDENTIFIER' values & counts:\n{gdf_daily_weather_data['CLIMATE_IDENTIFIER'].value_counts()}\n")
print(f"'STN_ID' values & counts:\n{gdf_daily_weather_data['STN_ID'].value_counts()}\n")



########################################################################################################################
### section 2 - actually save our data to use later
# set engine
engine = default_SQL_engine()

if False:
    # Add daily-weather-data to PostGIS
    # NOTE: not setting dtype on the weather station; I only really care about dtype if I need to prevent a type-mismatch
    # when adding new hourly/daily data to an existing database table
    gdf_daily_weather_data.to_postgis(DatabaseTables.weather_data_daily_2, engine, if_exists="replace", index=False,
                                dtype=dict(DAILY_WEATHER_DATA_TYPES) # unwrap to a regular dict for the function call
                                )

    # add uniqueness constraint to `TABLE_COLS.datetime_station` after table creation
    # NOTE: remove that DATETIME_STATION unique constraint just in case it's still there...
    sql_command = f"""
    ALTER TABLE {DatabaseTables.weather_data_daily}
    DROP CONSTRAINT IF EXISTS uq_{DatabaseTables.weather_data_daily}_DATETIME_STATION;
    ALTER TABLE {DatabaseTables.weather_data_daily}
    DROP CONSTRAINT IF EXISTS uq_{DatabaseTables.weather_data_daily}_{DailyWeatherCols.datetime_station};
    ALTER TABLE {DatabaseTables.weather_data_daily_2}
    ADD CONSTRAINT uq_{DatabaseTables.weather_data_daily_2}_{DailyWeatherCols.datetime_station} UNIQUE ("{DailyWeatherCols.datetime_station}");
    """
    with engine.begin() as conn: conn.execute(text(sql_command))



    ########################################################################################################################
    ### END - print script finish statement
    print(f"Script: {__file__} completed at {datetime.now()}")