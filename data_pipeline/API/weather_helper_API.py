"""
file name: weather_helper_API.py
author: William Hovdestad

This script contains helper functions for querying, filtering, and processing data from the Canada Weather API
Link: https://api.weather.gc.ca/openapi?f=html#

These functions are located in the API folder,
because they are specifically tailored to work with the Weather API data.
They were deemed to have a use-case that is too narrow and niche to meet the standards
of being a "helper" file in the "helper" folder.



# Section 1: function `fetch_weather_pages`
The first function contains the logic for actually making a HTTP GET request to the REST API to get data
it includes a preliminary query to count the number of results, and pagination through those results
It assumes it is passed a URL, and a parameters dictionary for the API call that includes a "limit" key



# Section 2: function `filter_stations_by_priority`
The second function contains logic for filtering weather stations,
with hard-coded weather-station-IDs and a hard-coded prioritization order based on the project requirements.
We want the date-time column of hourly-weather-records, and the date of daily-weather-records to be unique.
In other words, at any given time, we want to only have ONE weather record to look at.
However, when we query weather data, we are retrieving data from THREE weather-stations,
so the raw-data retrieved via API can have up to three records for each distinct date/datetime.
This function defines a prioritization for the three weather stations,
and drops all but the highest-priority record that exists for each distinct date/datetime.



# Section 3: function `hourlyWeatherAddTimezone`
The third function properly process the datetime columns (specifically the "LOCAL_DATE" and "UTC_DATE" columns)
for data/dataframes retrieved from the `climate-hourly` section of the Canada weather API.
(Basically, it goes "THIS IS A DATETIME" and "THIS IS THE TIME-ZONE FOR THAT DATETIME")
NOTE:
This function is not to be used on `SWOB-realtime` data, as that has seperate logic for addressing datetime columns.



########################################################################################################################
### section 3: function `hourlyWeatherAddTimezone`
### function adding proper timezone to hourly-weather-data retrieved from `climate-hourly` section of Canada weather API
### NOTE: Do not use on `SWOB-realtime` data, as that has seperate logic for addressing datetime columns.
"""



########################################################################################################################
### script-setup 1: project-root-setup

import os
import sys
from pathlib import Path

# set PROJECT_ROOT so libraries from cousin folders import properly
# note that I want the main directory and file is `scripts`, a sub-directory of main,
#  so I need great grand-parent folder instead of simply parent-folder
PROJECT_ROOT = Path(__file__).resolve().parents[2] 
# sets working directory to project root - there may be redundancy here but oh well lol
os.chdir(PROJECT_ROOT)
# Ensure repository code is importable when this wrapper is run directly.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))



########################################################################################################################
### script-setup 2: library imports
import httpx
import json
import pandas as pd
import geopandas as gpd
import logging


# custom libraries!
from data_pipeline.helper.helper_API_errors import APICountMismatchError, APIZeroCountError
from data_pipeline.helper.helper_set_geojson_crs import set_geojson_crs
from data_pipeline.helper.helper_API_try_except_job import try_except_weather_API
from data_pipeline.helper.helper_SQL_tables import PRIMARY_STATION_ID, SECONDARY_STATION_ID, TERTIARY_STATION_ID
from data_pipeline.helper.helper_SQL_tables import HourlyWeatherCols
from data_pipeline.helper.helper_timezones import AB_TIME, UTC_TIME



########################################################################################################################
### script-setup 3: logging config
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING) # STOP LOGGING EVERY API CALL DAMNIT



########################################################################################################################
### section 1: function `fetch_weather_pages` (function to fetch weather data)

def fetch_weather_pages(start_url: str, params: dict, job_title: str) -> gpd.GeoDataFrame:
    ##############################################################
    # section 1.1 - quick query to determine total number of items
    ##############################################################
    params_temp = params.copy()
    
    og_limit = params_temp["limit"]
    params_temp["limit"] = 1

    # logic to fetch page-count lol...
    job_name = f"fetching-page-count for job: {job_title}"
    response_output = try_except_weather_API(job_name=job_name, url=start_url, params=params_temp)

    params_temp["limit"] = og_limit # reset limit back to what it should be

    response_expected = response_output["numberMatched"] # get the number of matches
    # NOTE: fail here if API meta-data says we have no results
    if response_expected == 0:
        msg = f"Error: APIZeroCountError: no matches found in job: {job_name}. Aborting."
        logger.error(msg)
        raise APIZeroCountError(msg)
    page_count = (response_expected / params_temp["limit"]).__ceil__()


    ###########################################################
    # section 1.2 - pagination, with error messages!
    ###########################################################

    current_page = 0

    all_data = []
    url = start_url

    while url: # stops if url = None
        current_page += 1
        if current_page > page_count + 1:
            msg = f"Error: APICountMismatchError: max page count exceeded during job: {job_title}. Aborting."
            logger.error(msg)
            raise APICountMismatchError(msg)

        #response_output = _fetch_weather_page(url, params)
        job_name = f"paginating job: {job_title}, page: {current_page}"
        response_output = try_except_weather_API(job_name=job_name, url=url, params=params_temp)
        page = response_output.get("features",[])
        # get items from "features" key, returns empty list (square-brackets) is key missing
        all_data.extend(page)
        # add `page` to `all_data`, extend works better than append for REASONS
        
        # now we look for the URL of the "next" page, and call this function again if we find it
        params_temp = None # remove parameters, next-link URLs carry their own query params
        # set url = None, then see if we find one lol
        url = None

        links = response_output["links"]
        # setup for next page
        
        # code to find "next" link below:
        for item in links:
            if item["rel"] == "next":
                url = item["href"]
                # "rel" is like the key for the, uh, 'rank' of the link? as opposed to its title/name?
                break # break if we find it, I guess? Since we shouldn't find more than one lol

    # one more error message after this TRY-EXCEPT block
    if response_expected != len(all_data):
        expected_vs_actual_error =\
            f"Error: APICountMismatchError: Missmatch between expected number of results ({response_expected}) and actual number ({len(all_data)}) during {job_name}. Aborting."
        logger.error(expected_vs_actual_error)
        raise APICountMismatchError(expected_vs_actual_error)


    ###########################################################
    # section 1.2 - convert to gdf, add CRS, return it
    gdf = gpd.GeoDataFrame.from_features(all_data) # I already selected the "features" key while looping thru data
    gdf = set_geojson_crs(gdf)
    return gdf



########################################################################################################################
### section 2: function `filter_stations_by_priority` 
### (keep only the weather record with the highest weather-station-priority-order for each distinct date-time)

def filter_stations_by_priority(df: pd.DataFrame | gpd.GeoDataFrame, station_id_col: str="CLIMATE_IDENTIFIER",
                                datetime_col: str="LOCAL_DATE") -> pd.DataFrame | gpd.GeoDataFrame:
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
### section 3: function `hourlyWeatherAddTimezone`
### function adding proper timezone to hourly-weather-data retrieved from `climate-hourly` section of Canada weather API
### NOTE: Do not use on `SWOB-realtime` data, as that has seperate logic for addressing datetime columns.

def hourlyWeather_FixDatetimes(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    # NOTE: AB daylight-savings-time changes broke "LOCAL_DATE" which is actually "LOCAL_DATETIME"...

    # convert local date and utc date to datetime
    # gdf[HourlyWeatherCols.hwc_local_date] = pd.to_datetime(gdf[HourlyWeatherCols.hwc_local_date])
    gdf[HourlyWeatherCols.hwc_utc_date] = pd.to_datetime(gdf[HourlyWeatherCols.hwc_utc_date])

    # add time zones
    #gdf[HourlyWeatherCols.hwc_local_date] = gdf[HourlyWeatherCols.hwc_local_date].dt.tz_localize(AB_TIME)
    gdf[HourlyWeatherCols.hwc_utc_date] = gdf[HourlyWeatherCols.hwc_utc_date].dt.tz_localize(UTC_TIME)

    # okay, since timezone changes broke my "local_date" what if I just calc it from UTC time afterwards?
    gdf[HourlyWeatherCols.hwc_local_date] = gdf[HourlyWeatherCols.hwc_utc_date].dt.tz_convert(AB_TIME)

    # should re-order columns, since there's no way they're in "proper" order right now
    # get list for column order, but don't forget to include geometry column at start!
    col_order_list = ["geometry", *(col.value for col in HourlyWeatherCols)]
    # re-organize the columns
    gdf = gdf.reindex(columns=col_order_list)

    return gdf