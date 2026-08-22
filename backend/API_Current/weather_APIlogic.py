########################################################################################################################
# file name: weather_APIlogic.py
# author: William Hovdestad
#
# This script contains the main logic for retrieving data from the `MSC GeoMet - GeoMet-OGC-API`
# Link: https://api.weather.gc.ca/openapi?f=html
# The point of this script is to create a function called `fetch_MSC_GeoMet_weather` that handles most of the API-logic
# for paginating through the `MSC GeoMet - GeoMet-OGC-API`, and return the data in GeoDataFrame format.
# This function is to be used as the structural backfone for the scripts:
#   `weather_daily_backfill.py`  
#   `weather_hourly_backfill.py`  
#   `weather_hourly_runDaily.py`  
#   `weather_hourly_runHourly.py`  
#
# This file starts off with a function called `filter_stations_by_priority` 
# which will be called by the function `fetch_MSC_GeoMet_weather`
# So that when it returns the GeoDataFrame, the column filtering/prioritizing is already done.
#
# It is worth noting that this function is designed assuming that it is used as intended/expected.
# It is unfortunately not very robust when it comes to error-handling, or improper use.



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



########################################################################################################################
### script-setup 2: library imports
import argparse # used for adding command line arguments to script
from datetime import date, datetime, time, timedelta, timezone # for getting current date
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
from backend.helper.helper_SQL_tables import DAILY_WEATHER_PROPERTIES, DAILY_WEATHER_DATA_TYPES, \
    DailyWeatherCols, HourlyWeatherCols, DatabaseTables, HOURLY_WEATHER_PROPERTIES, \
    PRIMARY_STATION_ID, SECONDARY_STATION_ID, TERTIARY_STATION_ID, \
    SWOB_PROPERTIES, HOURLY_SWOB_CONVERSION
from backend.helper.helper_set_geojson_crs import set_geojson_crs



########################################################################################################################
### script-setup 3: pandas print options
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.width', 1000)
pd.set_option('display.max_colwidth', None)



########################################################################################################################
### section 1: some error-functions
#class Error_APItimeout



########################################################################################################################
### section 1: filter stations by priority
def filter_stations_by_priority(df, station_id_col="CLIMATE_IDENTIFIER", datetime_col="LOCAL_DATE"):
    df = df.copy()
    STATION_PRIORITY_COL = "station_priority"
    STATION_PRIORITY_ORDER = {
        PRIMARY_STATION_ID: 1,
        SECONDARY_STATION_ID: 2,
        TERTIARY_STATION_ID: 3,
    }
    df[STATION_PRIORITY_COL] = df[station_id_col].map(STATION_PRIORITY_ORDER)
    df = ( # operation we're doing to df
        df # start with df
        .sort_values([datetime_col, STATION_PRIORITY_COL]) # order df by DATETIME, then STATION-PRIORITY
        .drop_duplicates(subset=datetime_col, keep="first") # drop duplicate datetimes - keep only first record
        .sort_values(datetime_col) # let's resort stuff by date
        .reset_index(drop=True) # nasty shit happens if you do operations like this and don't reset index lol
    )
    df = df.drop(columns=[STATION_PRIORITY_COL]) # we don't need this column anymore, lets remove it
    return df



########################################################################################################################
### section 2: function to actually fetch weather lol

def fetch_MSC_GeoMet_weather(url, params, silent=False):

    ##############################################################
    # section 2.1 - quick query to determine total number of items
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
    # section 2.2 - start progress bar
    ##################################
    
    total_iterations = page_count
    prefix = "Fetching weather data"
    current_page = 0
    if not silent:
        update_progress_bar(iteration=current_page, total=total_iterations, prefix=prefix)
    


    ###########################################################
    # section 2.3 - setup and actually start recursive API call
    ###########################################################
    # NOTE: let's try to make it a while-loop lol
    
    # first, create empty variable to hold data
    all_data = []

    # first page
    current_page += 1
    response = httpx.get(url, params=params, timeout=60.0)
    response.raise_for_status() # make sure status is good
    response_output = response.json() # turn results into json# get data from API call

    data = response_output.get("features",[])
    # get items from "features" key, returns empty list (square-brackets) is key missing
    all_data.extend(data)
    # add `data` to `all_data`, extend works better than append for REASONS
    
    # now let's increase our progress bar, since we just added some data
    if not silent:
        update_progress_bar(iteration=current_page, total=total_iterations, prefix=prefix)

    # now we look for the URL of the "next" page, and call this function again if we find it
    next_url = None
    links = response_output["links"]
    for item in links:
        if item["rel"] == "next":
        # "rel" is like the key for the, uh, 'rank' of the link? as opposed to its title/name?
            next_url = item["href"]

    while next_url:
        current_page += 1
        if current_page > page_count: break # emergency exit just-in-case

        response = httpx.get(next_url, timeout=60.0) # api call
        response.raise_for_status() # make sure status is good
        response_output = response.json() # turn results into json# get data from API call

        data = response_output.get("features",[])
        # get items from "features" key, returns empty list (square-brackets) is key missing
        all_data.extend(data)
        # add `data` to `all_data`, extend works better than append for REASONS
        
        # now let's increase our progress bar, since we just added some data
        if not silent:
            update_progress_bar(iteration=current_page, total=total_iterations, prefix=prefix)

        # now we look for the URL of the "next" page, and call this function again if we find it
        next_url = None
        links = response_output["links"]
        for item in links:
            if item["rel"] == "next":
            # "rel" is like the key for the, uh, 'rank' of the link? as opposed to its title/name?
                next_url = item["href"]
    """
    # HERE is the recursive function to paginate URL!
    all_data = []
    current_page = 0
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
                print(f"next url: {new_url}")
                paginate_url(new_url, current_page)

    # whew, all that is done! now we can actually CALL our function
    paginate_url(url, current_page=0, include_params=True)
    """


    ######################################################
    # section 2.4 - check results, convert to GDF, set CRS
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


    ##########################################################################
    # section 2.5 - call our function to filter the stations by their priority
    ##########################################################################

    # filter_stations_by_priority(df, station_id_col, datetime_col)
    gdf = filter_stations_by_priority(gdf)

    #################
    # return the data
    #################

    return gdf



########################################################################################################################
### section 2: daily weather

# NOTE: grab all 3 stations IDs - 3031092, 3031093, 3031094, order priority is: 3031094 > 3031092 > 3031093
# def fetch_MSC_GeoMet_weather(url, params, silent=False):
def daily_MSC_GeoMet_weather_by_year(year: int = 2025, silent=False):
    #return 0

    ids_clause = f"{PRIMARY_STATION_ID}, {SECONDARY_STATION_ID}, {TERTIARY_STATION_ID}"
    #ids_clause = f"{PRIMARY_STATION_ID}"
    #ids_clause = f"{SECONDARY_STATION_ID}"

    daily_weather_url = "https://api.weather.gc.ca/collections/climate-daily/items"
    daily_weather_params = {
        "limit": 1000,
        #"CLIMATE_IDENTIFIER": STATION_CLIMATE_IDENTIFIER,
        "filter": f"properties.{DailyWeatherCols.climate_identifier} IN ({ids_clause})",
        # "datetime": "1956-01-01T00:00:00Z/..", # per documentation, this should filter it to dates 1956-01-01 and higher
        #"datetime": f"{start_year}-01-01T00:00:00Z/..", # per documentation, this should filter it to dates {start_year} and higher
        f"{DailyWeatherCols.local_year}": year,
        "properties": DAILY_WEATHER_PROPERTIES,
    }

    print("fetching daily weather...")
    gdf_daily = fetch_MSC_GeoMet_weather(url=daily_weather_url, params=daily_weather_params, silent=True)

    gdf_daily[DailyWeatherCols.local_date] = pd.to_datetime(gdf_daily[DailyWeatherCols.local_date]).dt.date # convert to datetime, then force it to just DATE

    # let's filter it by our column priority now
    gdf_daily = filter_stations_by_priority(gdf_daily,\
                                            station_id_col=DailyWeatherCols.climate_identifier,\
                                            datetime_col=DailyWeatherCols.local_date)

    #print(gdf_daily.dtypes)

    #print("head:")
    #print(gdf_daily.head())
    #print("tail:")
    #print(gdf_daily.tail())
    # NOTE: confirmed to work
    return gdf_daily

if True:
    year = 2023
    gdf = daily_MSC_GeoMet_weather_by_year(year)
    print(gdf.head())
    #output_path = Path(PROJECT_ROOT) / "backend" / "API_Current" / f"daily_{year}_stn_{SECONDARY_STATION_ID}_test.csv"
    #gdf.to_csv(output_path, index=False)
"""
#############################################
# section 2.3 - parameters for hourly-weather
#############################################
# NOTE: grab all 3 stations IDs - 3031092, 3031093, 3031094, order priority is: 3031094 > 3031092 > 3031093

hourly_weather_url = "https://api.weather.gc.ca/collections/climate-hourly/items"


def hourly_MSC_GeoMet_weather_by_year(year: int = 1956, silent=False):
    ids_clause = f"{PRIMARY_STATION_ID}, {SECONDARY_STATION_ID}, {TERTIARY_STATION_ID}"
    hourly_weather_url = "https://api.weather.gc.ca/collections/climate-hourly/items"
    hourly_weather_params = {
        "limit": 1000,
        "filter": f"properties.{HourlyWeatherCols.climate_identifier} IN ({ids_clause})",
        f"{HourlyWeatherCols.local_year}": year,
        #"properties": HOURLY_WEATHER_PROPERTIES, # filter to specific properties I want from station
    }

    print("fetching hourly weather...")
    gdf_hourly = fetch_MSC_GeoMet_weather(url=hourly_weather_url, params=hourly_weather_params)

    # let's filter it by our column priority now
    gdf_hourly = filter_stations_by_priority(gdf_hourly,
                                             station_id_col=DailyWeatherCols.climate_identifier,
                                             datetime_col=DailyWeatherCols.local_date)

    return gdf_hourly


if False:
    gdf = hourly_MSC_GeoMet_weather_by_year()
    output_path = Path(PROJECT_ROOT) / "backend" / "API_Current" / "hrly_1955_test.csv"
    #print(gdf['geometry'].head())
    #print(gdf.tail())
    gdf.to_csv(output_path, index=False)

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
print(f"swob_properties_str_arr v1:\n{swob_properties_str_arr}\n")
swob_properties_str_arr = SWOB_PROPERTIES
print(f"swob_properties_str_arr v2:\n{swob_properties_str_arr}")

swob_properties_list = [
    "stn_nam-value",
    "clim_id-value",
    "avg_air_temp_pst1hr", "avg_air_temp_pst1hr-uom",
    "pcpn_amt_pst1hr", "pcpn_amt_pst1hr-uom",
    "avg_rel_hum_pst1hr", "avg_rel_hum_pst1hr-uom",
    "stn_pres", "stn_pres-uom",
    "avg_wnd_spd_10m_pst1hr", "avg_wnd_spd_10m_pst1hr-uom",
    "avg_wnd_dir_10m_pst1hr", "avg_wnd_dir_10m_pst1hr_1-uom",
    "avg_dwpt_temp_pst1hr", "avg_dwpt_temp_pst1hr-uom"
]
#swob_properties_str_arr = ",".join(swob_properties_list)


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
print("fetching real-time weather data...")
# gdf_real_time = fetch_MSC_GeoMet_weather(url=real_time_weather_url, params=real_time_weather_params)
if True:
    gdf = fetch_MSC_GeoMet_weather(url=real_time_weather_url, params=real_time_weather_params)
    gdf = gdf.rename(columns=dict(HOURLY_SWOB_CONVERSION))
    #print(gdf.tail())
    #print(type(gdf)) # okay so it is geodataframe
    #print(gdf[HourlyWeatherCols.UTC_date].tail(1))
    print(gdf.columns[gdf.columns.duplicated()])
    gdf[HourlyWeatherCols.UTC_date] = pd.to_datetime(gdf[HourlyWeatherCols.UTC_date])
    gdf[HourlyWeatherCols.local_date] = gdf[HourlyWeatherCols.UTC_date].dt.tz_convert("America/Edmonton")
    gdf[HourlyWeatherCols.local_year] = gdf[HourlyWeatherCols.local_date].dt.year
    #gdf_real_time['date_tm-value']
    #print(gdf_real_time.head(1))
    print(gdf.tail(1))
    print(gdf.columns)
    output_path = Path(PROJECT_ROOT) / "backend" / "API_Current" / "SWOB_test.csv"
    gdf.to_csv(output_path, index=False)


"""