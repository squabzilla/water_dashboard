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
#  so I need grand-parent folder instead of simply parent-folder
PROJECT_ROOT = Path(__file__).resolve().parents[2] # gets file-path, (hopefully) resolves relative path issues, gets great-grand-parent folder
# sets working directory to project root - there may be redundancy here but oh well lol
os.chdir(PROJECT_ROOT)
# Ensure repository code is importable when this wrapper is run directly.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))



########################################################################################################################
### script-setup 2: library imports
from collections.abc import Callable
import httpx
import json
import pandas as pd
import geopandas as gpd
import logging


# custom libraries!
from backend.helper.helper_API_errors import APITimeoutError, APIResponseError, APICountMismatchError, \
    APIZeroCountError, DataUniquenessConstraintViolation, DBError
from backend.helper.helper_set_geojson_crs import set_geojson_crs
from backend.helper.helper_PSQL_config import default_SQL_engine
from backend.helper.helper_DB_update import export_as_new_table, add_new_records_to_table
from backend.helper.helper_API_try_except_job import try_except_weather_API


########################################################################################################################
### script-setup 3: logging config
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING) # STOP LOGGING EVERY API CALL DAMNIT
#logging.getLogger("httpcore").setLevel(logging.WARNING)



########################################################################################################################
### section 1: function to fetch weather
"""
@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    # decorator itself, and the condition for retrying anything at all
    stop=stop_after_attempt(4), # tells tenacity when to give up - after 4 attemps (1 initial call, 3 retries)
    wait=wait_exponential(multiplier=1, min=2, max=30),
    # wait an increasing time between each attempt;
    # the `max` setting is redundant since we stop after attempt 4, but redundancy is good in this case
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
"""
#def _fetch_weather_page(url: str, params: dict | None) -> dict:
    #"""Fetch a single page. Retried individually on transient failures."""
    #response = httpx.get(url, params=params, timeout=30.0) # api call
    #response.raise_for_status() # make sure status is good
    #return response.json() # turn results into json



def fetch_weather_pages(start_url: str, params: dict, job_title: str) -> dict:
    ##############################################################
    # section 1.1 - quick query to determine total number of items
    ##############################################################
    
    og_limit = params["limit"]
    params["limit"] = 1

    # logic to fetch page-count lol...
    job_name = f"fetching-page-count for job: {job_title}"
    response_output = try_except_weather_API(job_name=job_name, url=start_url, params=params)
    """
    try:
        response_output = _fetch_weather_page(start_url, params)
    except httpx.TimeoutException as e:
            raise APITimeoutError(f"Timed out fetching fetching page-count from {start_url} after retries: {e}") from e
    except httpx.ConnectError as e:
        raise APITimeoutError(f"Connection error fetching page-count from {start_url} after retries: {e}") from e
    except httpx.HTTPStatusError as e:
        raise APIResponseError(f"Bad status fetching page-count from {start_url}: {e.response.status_code}") from e
    except (KeyError, json.JSONDecodeError) as e:
        raise APIResponseError(f"Malformed page while paginating page-count from {start_url}: {e}") from e
    except Exception as e:
        pass
    """

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

#    try:
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
        #url = None
        params = None # remove parameters, next-link URLs carry their own query params
        url = None

        links = response_output["links"]


        # setup for next page
        
        # code to find "next" link below:
        for item in links:
            if item["rel"] == "next":
                url = item["href"]
                # "rel" is like the key for the, uh, 'rank' of the link? as opposed to its title/name?
                break
    """
    except httpx.TimeoutException as e:
        raise APITimeoutError(f"Timed out fetching {start_url} after retries") from e
    except httpx.ConnectError as e:
        raise APITimeoutError(f"Connection error fetching {start_url} after retries") from e
    except httpx.HTTPStatusError as e:
        raise APIResponseError(f"Bad status fetching {start_url}: {e.response.status_code}") from e
    except (KeyError, json.JSONDecodeError) as e:
        raise APIResponseError(f"Malformed page while paginating {start_url}: {e}") from e
    """

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