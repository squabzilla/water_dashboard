"""
file name: weather_helper_API.py
author: William Hovdestad

This script contains the logic for fetching the API response from a given request,
including paginating through results.
It assumes it is passed a url, and a parameters dictionary with a "limit" key
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
from backend.helper.helper_API_errors import APICountMismatchError, APIZeroCountError
from backend.helper.helper_set_geojson_crs import set_geojson_crs
from backend.helper.helper_API_try_except_job import try_except_weather_API


########################################################################################################################
### script-setup 3: logging config
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING) # STOP LOGGING EVERY API CALL DAMNIT



########################################################################################################################
### section 1: function to fetch weather

def fetch_weather_pages(start_url: str, params: dict, job_title: str) -> dict:
    ##############################################################
    # section 1.1 - quick query to determine total number of items
    ##############################################################
    
    og_limit = params["limit"]
    params["limit"] = 1

    # logic to fetch page-count lol...
    job_name = f"fetching-page-count for job: {job_title}"
    response_output = try_except_weather_API(job_name=job_name, url=start_url, params=params)

    params["limit"] = og_limit # reset limit back to what it should be

    response_expected = response_output["numberMatched"] # get the number of matches
    # NOTE: fail here if API meta-data says we have no results
    if response_expected == 0:
        raise APIZeroCountError(f"ERROR - no matches found in job: {job_name}. Aborting.")
    page_count = (response_expected / params["limit"]).__ceil__()


    ###########################################################
    # section 1.2 - pagination, with error messages!
    ###########################################################

    current_page = 0

    all_data = []
    url = start_url

    while url: # stops if url = None
        current_page += 1
        if current_page > page_count + 1: raise APICountMismatchError("Error: max page count exceeded")

        #response_output = _fetch_weather_page(url, params)
        job_name = f"paginating job: {job_title}, page: {current_page}"
        response_output = try_except_weather_API(job_name=job_name, url=url, params=params)
        page = response_output.get("features",[])
        # get items from "features" key, returns empty list (square-brackets) is key missing
        all_data.extend(page)
        # add `page` to `all_data`, extend works better than append for REASONS
        
        # now we look for the URL of the "next" page, and call this function again if we find it
        params = None # remove parameters, next-link URLs carry their own query params
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
            f"ERROR - Missmatch between expected number of results ({response_expected}) and actual number ({len(all_data)}) during {job_name}. Aborting."
        raise APICountMismatchError(expected_vs_actual_error)


    ###########################################################
    # section 1.2 - convert to gdf, add CRS, return it
    gdf = gpd.GeoDataFrame.from_features(all_data) # I already selected the "features" key while looping thru data
    gdf = set_geojson_crs(gdf)
    return gdf