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
from datetime import date, datetime, time, timedelta, timezone # for getting current date
from zoneinfo import ZoneInfo # for time zones
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
    STATION_CLIMATE_IDENTIFIER, DAILY_WEATHER_PROPERTIES, DAILY_WEATHER_DATA_TYPES, \
        DailyWeatherCols, DatabaseTables, HOURLY_WEATHER_PROPERTIES



########################################################################################################################
### section 1: function to actually fetch weather lol

def fetch_MSC_GeoMet_weather(url, params, silent=False):

    ##############################################################
    # section 1.1 - quick query to determine total number of items
    ##############################################################
    
    og_limit = params["limit"]
    params["limit"] = 1
    response = httpx.get(url, params=params) # api call
    params["limit"] = og_limit # reset limit back to what it should be
    response.raise_for_status() # make sure status is good
    response_output = response.json() # turn results into json
    response_expected = response_output["numberMatched"] # get expected number of responses
    # NOTE: fail here if API meta-data says we have no results
    if response_expected == 0:
        raise CustomErrorMessage("ERROR - no matches found. Aborting.")
    page_count = (response_expected / params["limit"]).__ceil__()


    ##################################
    # section 1.2 - start progress bar
    ##################################
    
    total_iterations = page_count
    prefix = "Fetching weather data"
    current_page = 0
    if not silent:
        update_progress_bar(iteration=current_page, total=total_iterations, prefix=prefix)


    ###########################################################
    # section 1.3 - setup and actually start recursive API call
    ###########################################################
    
    # first, create empty variable to hold data
    all_data = []

    # HERE is the recursive function to paginate URL!
    def paginate_url(url, current_page, include_params=False, params=params):
    # recursive function, to be called by this function

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
        if not silent:
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


    ######################################################
    # section 1.4 - check results, convert to GDF, set CRS
    ######################################################
    
    # lets confirm our results match...
    if not silent:
        print(f" Expected responses: {response_expected}; actual: {len(all_data)}")
    # spit out an error if they don't
    expected_vs_actual_error =\
    f"ERROR - Missmatch between expected number of results ({response_expected}) and actual number ({len(all_data)}). Aborting."
    if response_expected != len(all_data):
        raise CustomErrorMessage(expected_vs_actual_error)

    # gdf = gpd.GeoDataFrame.from_features(response_output["features"]) # this apparently converts to geojson lol
    gdf = gpd.GeoDataFrame.from_features(all_data) # I already selected the "features" key while looping thru data
    
    # first, set the crs - NOTE: newer geojsons don't have a CRS, and assume EPSG 4326 is CRS
    gdf = set_geojson_crs(gdf)

    #################
    # return the data
    #################

    return gdf



########################################################################################################################
### section 2: preparing to test shit

################################################
# section 2.1 - parameters for all weather-calls
################################################

# NOTE: grab all 3 stations IDs - 3031092, 3031093, 3031094, order priority is: 3031094 > 3031092 > 3031093

STATION_CLIMATE_IDENTIFIERS = ("3031092", "3031093")
# CQL2 string values must be single-quoted
ids_clause = ", ".join(f"'{sid}'" for sid in STATION_CLIMATE_IDENTIFIERS)


############################################
# section 2.2 - parameters for daily-weather
############################################

daily_weather_url = "https://api.weather.gc.ca/collections/climate-daily/items"
daily_weather_params = {
    "limit": 1000,
    #"CLIMATE_IDENTIFIER": STATION_CLIMATE_IDENTIFIER,
    "filter": f"properties.CLIMATE_IDENTIFIER IN ({ids_clause})",
    "datetime": "2000-01-01T00:00:00Z/..", # per documentation, this should filter it to dates 1956-01-01 and higher
    "properties": DAILY_WEATHER_PROPERTIES,
}


#############################################
# section 2.3 - parameters for hourly-weather
#############################################

hourly_weather_url = "https://api.weather.gc.ca/collections/climate-hourly/items"

def get_hourly_weather_datetime_param():
    # get proper datetime string to use! first, subtract 1 week from current date
    my_time_zone = ZoneInfo("America/Edmonton")
    today_date = datetime.now(my_time_zone).date() # gets today's date as datetime so I can include timezone, then make it date
    day_minus_seven = today_date - timedelta(days=7) # subtract 7 days from current date
    # now, convert it to proper parameter to API call
    datetime_param = str(day_minus_seven) + "T00:00:00Z/.."
    # NOTE: This gives me 12:00am from 7 days ago
    return datetime_param

hourly_weather_params = {
    "limit": 250, # 8 * 25 = 200, I'm getting at most last 8 days * 24 hrs, so this should be good
    #"CLIMATE_IDENTIFIER": STATION_CLIMATE_IDENTIFIER,
    "filter": f"properties.CLIMATE_IDENTIFIER IN ({ids_clause})",
    "datetime": get_hourly_weather_datetime_param(),
    "properties": HOURLY_WEATHER_PROPERTIES, # filter to specific properties I want from station
}


######################################################
# section 2.4 - parameters for real-time weather query
######################################################

#STATION_CLIMATE_IDENTIFIERS = ("3031092", "3031093")
STATION_CLIMATE_IDENTIFIERS = ("3031094",)
ids_clause = ", ".join(f"'{sid}'" for sid in STATION_CLIMATE_IDENTIFIERS)

# url of API
real_time_weather_url = "https://api.weather.gc.ca/collections/swob-realtime/items"

# get "star-time" variable we need for real-time weather API query
hours_back = 6

# get start time in UTC
utc_current_time = datetime.now(timezone.utc)
utc_start_time = utc_current_time - timedelta(hours=hours_back)

swob_properties_list = [
    "stn_nam-value",
    "clim_id-value",
	"date_tm-value",
	"avg_air_temp_pst1hr", # NOTE: should be celcius
	#"air_temp", # NOTE: can cut these ones
	#"air_temp_1", # NOTE: can cut these ones
	#"air_temp_2", # NOTE: can cut these ones
	#"air_temp_3", # NOTE: can cut these ones
	"pcpn_amt_pst1hr", # NOTE: unit is mm
]
swob_properties_str_arr = ",".join(swob_properties_list)

# set parameters for API query
# NOTE: this is the "main" one I'm using
STATION_CLIMATE_IDENTIFIER = "3031094"
real_time_weather_params = {
    "limit": 1000,
    #"clim_id-value": STATION_CLIMATE_IDENTIFIER,
    "filter": f'"properties.clim_id-value" IN ({ids_clause})',
    # NOTE: gods, I need to start the f-string with single quotes, so I can put double quotes inside it, around the whole properties value...
    "datetime": f"{utc_start_time.strftime('%Y-%m-%dT%H:%M:%SZ')}/{utc_current_time.strftime('%Y-%m-%dT%H:%M:%SZ')}",
    "sortby": "date_tm-value",
    "properties": swob_properties_str_arr, # filter to specific properties I want from station
}


########################################################################################################################
### section 3: actually testing shit

# print("fetching daily weather...")
# gdf_daily = fetch_MSC_GeoMet_weather(url=daily_weather_url, params=daily_weather_params)
# NOTE: confirmed to work

# print("fetching hourly weather...")
# gdf_daily = fetch_MSC_GeoMet_weather(url=hourly_weather_url, params=hourly_weather_params)
# NOTE: confirmed to work

print("fetching real-time weather data...")
# gdf_real_time = fetch_MSC_GeoMet_weather(url=real_time_weather_url, params=real_time_weather_params)
gdf_real_time = fetch_MSC_GeoMet_weather(url=real_time_weather_url, params=real_time_weather_params)
print("head")
print(gdf_real_time.head())
print("tail")
print(gdf_real_time.tail())
print(gdf_real_time.columns)