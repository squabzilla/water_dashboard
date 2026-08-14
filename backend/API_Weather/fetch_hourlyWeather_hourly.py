########################################################################################################################
# file name: fetch_hourlyWeather_hourly.py
# author: William Hovdestad
#
# The goal of this script is to retrieve hourly weather data from the following weather station:
# STATION_NAME: CALGARY INT'L CS; CLIMATE_IDENTIFIER: 3031094;
#
# This script will be using "Swob-realtime" from https://api.weather.gc.ca/openapi
#
# This data is raw and unfiltered, but should hopefully give us access to near-realtime-data,
# and this script will be run hourly to retrieve that data.



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
import geopandas as gpd # geospatial library, used for GeoDataFrames
#from shapely.geometry import Point # used to properly format lat/long values for use by GeoPandas
import httpx # used for calling API
#from dateutil.parser import parse # used for properly formatting DATE data into datetime variables
import json # used for handling export of json data

# custom modules!
from backend.helper_progress_bar import update_progress_bar
from backend.helper_error import CustomErrorMessage
from backend.helper_PSQL import default_SQL_engine, set_geojson_crs, STATION_NAME, \
    STATION_CLIMATE_IDENTIFIER, HOURLY_WEATHER_PROPERTIES, HOURLY_WEATHER_DATA_TYPES, HourlyWeatherCols, DatabaseTables



########################################################################################################################
### script-setup 3: print statement for start of script, and current time
print(f"Script: {__file__} started at {datetime.now()}")



########################################################################################################################
### script-setup 4: setup command line arguments for script
#
# We have a command-line argument for how many hours we look back

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("-s", "--silent", help="silence script output when running",
                    action="store_true")
args = parser.parse_args()
# if not args.silent: # this lets us turn off printing the progress bar if we add -s when running!
# stuff in this if-statement will only execute if the "-s" argument wasn't passed

DEFAULT_LOOKBACK_HOURS = 6


parser.add_argument(
    "-hb", "--hours_back",
    type=int,
    default=DEFAULT_LOOKBACK_HOURS,
    help=f"Lookback window in hours (default: {DEFAULT_LOOKBACK_HOURS}; "
    "use 48 for a fresh-deployment backfill)",
)
args = parser.parse_args()

print(f"args.hours-back: {args.hours_back}")



########################################################################################################################
### section 1: grab hourly weather data


########################################################
# section 1.1 - set up variables for the looped-API call
########################################################

# url of API
url = "https://api.weather.gc.ca/collections/swob-realtime/items"

# variable to store all of the data
all_data = []

# easier variable for how many hows back we're looking
hours_back = args.hours_back

# get start time in UTC
utc_current_time = datetime.now(timezone.utc)
utc_start_time = utc_current_time - timedelta(hours=hours_back)


swob_properties_list = [
    "stn_nam-value",
    "clim_id-value",
	"date_tm-value",
	"avg_air_temp_pst1hr",
	"air_temp",
	"air_temp_1",
	"air_temp_2",
	"air_temp_3",
	"pcpn_amt_pst1hr", # NOTE: unit is mm
	"rel_hum", # NOTE: relative humidity in percentage
	#"max_rel_hum_pst1hr",
	#"min_rel_hum_pst1hr",
	#"avg_wnd_dir_10m_pst1hr", # NOTE: in degrees, from 0-360
	#"avg_wnd_spd_10m_pst1hr", # NOTE: in km/hr
    #"obs_date_tm",
    #"wetblb_temp",
]

swob_properties_str_arr = ",".join(swob_properties_list)


# set parameters for API query
params = {
    "limit": hours_back * 90,
    #"stn_nam-value": STATION_NAME,
    "clim_id-value": STATION_CLIMATE_IDENTIFIER,
    "datetime": f"{utc_start_time.strftime('%Y-%m-%dT%H:%M:%SZ')}/{utc_current_time.strftime('%Y-%m-%dT%H:%M:%SZ')}",
    "sortby": "date_tm-value",
    "properties": swob_properties_str_arr, # filter to specific properties I want from station
}
print(f"datetime values:\n{params["datetime"]}")
print(f"station name: `{STATION_NAME}`")

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

print(f"responses expected: {response_expected}")

# loop thru results with pagination!


###########################
# section 1.3 - DO THE LOOP
###########################

# remember, we're paginating over the API results
total_iterations = page_count
prefix = "Fetching historical daily weather data"
current_page = 0
if not args.silent: # this lets us turn off printing the progress bar if we add -s when running!
    update_progress_bar(iteration=current_page, total=total_iterations, prefix=prefix)

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


#############################################
# section 1.4 - check results, convert to GDF
#############################################
# lets confirm our results match...
if not args.silent:
    print(f" Expected responses: {response_expected}; actual: {len(all_data)}")
# spit out an error if they don't
expected_vs_actual_error =\
f"ERROR - Missmatch between expected number of results ({response_expected}) and actual number ({len(all_data)}). Aborting."
if response_expected != len(all_data):
    raise CustomErrorMessage(expected_vs_actual_error)

# gdf = gpd.GeoDataFrame.from_features(response_output["features"]) # this apparently converts to geojson lol
gdf = gpd.GeoDataFrame.from_features(all_data) # I already selected the "features" key while looping thru data
del all_data # we don't need this anymore




###################################################
# section 1.5 - convert columns to match other data
###################################################
#print(f"gdf.head(1): {gdf.head(1)}")
#print(f"gdf.tail(1): {gdf.tail(1)}")

for item in gdf.columns: print(item)
"""
geometry
clim_id-value
date_tm-value

avg_air_temp_pst1hr




pcpn_amt_pst1hr
rel_hum
max_rel_hum_pst1hr
min_rel_hum_pst1hr
avg_wnd_dir_10m_pst1hr
avg_wnd_spd_10m_pst1hr
obs_date_tm
wetblb_temp

wkt_geom	CLIMATE_IDENTIFIER	UTC_DATE	LOCAL_DATE	TEMP	PRECIP_AMOUNT	RELATIVE_HUMIDITY	WINDCHILL	WIND_DIRECTION	WIND_SPEED	WEATHER_ENG_DESC	DATETIME_STATION
Point (-114.00029722222221551 51.10944722222222225)	3031094	2026-07-31T07:00:00.000	2026-07-31T00:00:00.000	16	0	79		31	8	NA	3031094-2026-07-31 00:00:00
"""

climateHourly_swobHourly_dict = {
	"CLIMATE_IDENTIFIER": "clim_id-value",
	"UTC_DATE": "date_tm-value",
	"LOCAL_DATE": "temp", # NOTE: convert something to this
	"TEMP": "air_temp", # "avg_air_temp_pst1hr", # NOTE: temperature I really want a current snap-shot of it
	"PRECIP_AMOUNT": "pcpn_amt_pst1hr",
	"RELATIVE_HUMIDITY": "rel_hum", # I'd prefer an hourly average, but I think we just have a snapshot, so that's what we get
	# "WINDCHILL": "temp", # NOTE: Omit, as it's derived measurement not available from raw data
	"WIND_DIRECTION": "avg_wnd_dir_10m_pst1hr",
	"WIND_SPEED": "avg_wnd_spd_10m_pst1hr",
	# "WEATHER_ENG_DESC": "temp", # NOTE: Omit, as it's derived measurement not available from raw data
}



###########################
# section 1.6 - process GDF
###########################