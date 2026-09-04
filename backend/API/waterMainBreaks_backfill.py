"""
file name: waterMainBreaks_APIlogic.py
author: William Hovdestad

The goal of this function is to create a function that backfills my watermain break data
from the first recorded break to now
and that if this script is called by itself, it execudes the script and backfills the database
we explicitly keep the `:created_at` Socrata meta-data, so that we can later query the API
and see if data has been updated since we last backfilled the database.
This is done because the Socrata data has a full-replace of the data whenever the City wants to update the data,
and Socrata's metadata column `created_at` is updated to reflect this time
(Because it's all done at once, the values in this column are all identical)
So if there's a discrepancy between my most recent `created_at` value, and Socrata's meta-data `:created_at` column,
it's time to replace - we'll ALSO do a batch job of replacing all of our data.
"""



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
from datetime import datetime # used to get current time
import psycopg # stuff needed to connect with postgis database
import sqlalchemy # stuff needed to connect with postgis database
from sqlalchemy import text # make pylance happy by recognizing this as a keyword lol
from sqlalchemy import create_engine # stuff needed to connect with postgis database
import pandas as pd # dataframe library, for when I'm not ready to make the DataFrame all Geo quite yet
import geopandas as gpd # geospatial library, used for GeoDataFrames
from shapely.geometry import shape # used to properly assign/set Geometry values for GeoDataFrame
#from shapely.geometry import Point # used to properly format lat/long values for use by GeoPandas
import httpx # used for calling API
#from dateutil.parser import parse # used for properly formatting DATE data into datetime variables
import json # used for handling export of json data
import logging # used to log stuff
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

# custom modules!
from backend.helper.helper_progress_bar import update_progress_bar
from backend.helper.helper_timezones import AB_TIME, UTC_TIME
#from backend.helper_PSQL import default_SQL_engine, DATABASE_CONFIG, DatabaseTables, WatermainBreaksCols, WATERMAIN_BREAKS_DATA_TYPES, set_geojson_crs
from backend.helper.helper_PSQL_config import DATABASE_CONFIG, default_SQL_engine
from backend.helper.helper_SQL_tables import DatabaseTables, WatermainBreaksCols, WATERMAIN_BREAKS_DATA_TYPES
from backend.helper.helper_set_geojson_crs import set_geojson_crs
from backend.helper.helper_API_try_except_job import try_except_city_API
from backend.helper.helper_API_errors import DataPipelineError, \
    APITimeoutError, APIResponseError, APICountMismatchError, APIZeroCountError, DBError


########################################################################################################################
### script-setup 3: logging config
logfile = Path(PROJECT_ROOT) / "backend" / "API" / "log_files" / "waterMainBreaks_backfill.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[ # handles output stuff
        logging.FileHandler(logfile), # handles output file
        logging.StreamHandler() # writes log to a "stream" which by default is terminal/console
        ],
    # NOTE: logging levels: affects labelling and filtering when looking through errors
    # like remember how I'd tell Python "idgaf about that warning just stop telling me"
    # but also not wanting to eliminate like SERIOUS errors?
    # that's what the logging levels let us do
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING) # STOP LOGGING EVERY API CALL DAMNIT
# LOGGING ORDER:
# debug
# info
# warning
# error
# critical



########################################################################################################################
### section 1:
### local helper function to count number of records,
### and local helper function to get single page

# NOTE: first recorded watermain break is 1956/01/01
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
def _get_record_count(JSON_QUERY_URL: str, payload: dict, page_size: int) -> int:
    with httpx.Client(timeout=30.0) as client:
            response = client.post(
                JSON_QUERY_URL,
                json=payload,
                headers={"X-App-Token": DATABASE_CONFIG.app_token.get_secret_value()},
                auth=(
                    DATABASE_CONFIG.api_key.get_secret_value(),
                    DATABASE_CONFIG.api_secret_key.get_secret_value(),
                ),
            )
            response.raise_for_status()
            record_count = response.json()[0]["COUNT"]
            record_count = int(record_count)
            if record_count == 0:
                raise APIZeroCountError("ERROR - no matches found. Aborting.")
    return record_count



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
def _fetchWaterMainBreakPage(GEOJSON_QUERY_URL: str, payload: dict) -> dict:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            GEOJSON_QUERY_URL,
            json=payload,
            headers={"X-App-Token": DATABASE_CONFIG.app_token.get_secret_value()},
            auth=(DATABASE_CONFIG.api_key.get_secret_value(),DATABASE_CONFIG.api_secret_key.get_secret_value(),),
            )
    response.raise_for_status()
    return response.json()
"""








########################################################################################################################
### section 2: loop-through and fetch historical watermain-break data

# NOTE: first recorded watermain break is 1956/01/01

def waterMainBreaks_backfill(silent_function: bool=False) -> None:
    ########################################################
    # section 1.1 - set up variables for the looped-API call
    ########################################################

    # NOTE: first recorded watermain break is 1956/01/01
    starting_year = 1956
    all_data = []

    date_column_name = WatermainBreaksCols.break_date
    page_size = 1000


    JSON_QUERY_URL = "https://data.calgary.ca/api/v3/views/dpcu-jr23/query.json"
    GEOJSON_QUERY_URL = "https://data.calgary.ca/api/v3/views/dpcu-jr23/query.geojson"


    ##############################################################
    # section 1.2 - get total count of records we want to retrieve
    ##############################################################

    # query to get a count of the data
    soql_query = f"""SELECT COUNT(*) WHERE date_extract_y(`{date_column_name}`) >= {starting_year}"""
    # because this is a COUNT(*), I don't care about the limit

    # payload - basically the API parameters
    payload = {"query": soql_query, "includeSynthetic": False,}
    # `"includeSynthetic": False` prevents auto-generated, made-up columns from showing up, which are annoying
    """
    try:
        record_count = _get_record_count(JSON_QUERY_URL, payload, page_size)
    except httpx.TimeoutException as e:
            raise APITimeoutError(f"Timed out fetching json {JSON_QUERY_URL} after retries") from e
    except httpx.ConnectError as e:
        raise APITimeoutError(f"Connection error fetching json {JSON_QUERY_URL} after retries") from e
    except httpx.HTTPStatusError as e:
        raise APIResponseError(f"Bad status fetching json {JSON_QUERY_URL}: {e.response.status_code}") from e
    except (KeyError, json.JSONDecodeError) as e:
        raise APIResponseError(f"Malformed page while paginating json {JSON_QUERY_URL}: {e}") from e
    except Exception as e:
        raise DataPipelineError(f"Unexpected error while fetching json {JSON_QUERY_URL}: {e}") from e
    """

    job_name = "count water-main-break-records"
    record_count_response = try_except_city_API(job_name=job_name, url=JSON_QUERY_URL, payload=payload)
    record_count = record_count_response[0]["COUNT"]
    record_count = int(record_count)
    if record_count == 0:
        raise APIZeroCountError(f"ERROR - no matches found during {job_name}. Aborting.")
    page_count = (record_count / page_size).__ceil__()
        
    #print(f"Page count: {page_count}")


    #############################################
    # section 1.3 - Loop through all of our pages
    #############################################

    # setup progress bar first tho
    total_iterations = page_count
    prefix = "Fetching watermain breaks"
    # if not args.silent: # this lets us turn off printing the progress bar if we add -s when running!
    if not silent_function:
        update_progress_bar(iteration=0, total=total_iterations, prefix=prefix) # first iteration is 0

    # query to get the actual data itself
    soql_query = f"SELECT `break_date`, `break_type`, `status`, `point`, `:created_at` WHERE date_extract_y(`{date_column_name}`) >= {starting_year} ORDER BY `{date_column_name}`"
    # fun fact, geojsons get weird about the geometry, it treats it special, so I can't do a simple SELECT *, I gotta name each column individually
    # but I STILL gotta tell it to grab the geometry column, or just returns a regular json without geometry...

    # now we loop through our paginated API
    for i in range(page_count):
        page_number = i + 1 # since I want this 1-indexed, not 0-indexed
        # payload - basically the API parameters
        payload = {"query": soql_query,
                "page": {"pageNumber": page_number, "pageSize": page_size},
                "includeSynthetic": False,
                # `"includeSynthetic": False` prevents auto-generated, made-up columns from showing up
        }
        job_name = f"fetch-water-main-break-records-page-{page_number}"
        response_data = try_except_city_API(job_name=job_name, url=GEOJSON_QUERY_URL, payload=payload)
        """
        try:
            response_data = _fetchWaterMainBreakPage(GEOJSON_QUERY_URL, payload)
        except httpx.TimeoutException as e:
                raise APITimeoutError(f"Timed out fetching geojson {GEOJSON_QUERY_URL} after retries") from e
        except httpx.ConnectError as e:
            raise APITimeoutError(f"Connection error fetching geojson {GEOJSON_QUERY_URL} after retries") from e
        except httpx.HTTPStatusError as e:
            raise APIResponseError(f"Bad status fetching geojson {GEOJSON_QUERY_URL}: {e.response.status_code}") from e
        except (KeyError, json.JSONDecodeError) as e:
            raise APIResponseError(f"Malformed page while paginating geojson {GEOJSON_QUERY_URL}: {e}") from e
        except Exception as e:
            raise DataPipelineError(f"Unexpected error while fetching geojson {GEOJSON_QUERY_URL}: {e}") from e
        """
        response_data = response_data['features']
        all_data.extend(response_data)
        # add `response.json()` to `all_data`, extend works better than append for REASONS

        # update progress bar
        #if not args.silent:
        if not silent_function:
            update_progress_bar(iteration=page_number, total=total_iterations, prefix=prefix)

    # done loop


    #############################################
    # section 1.4 - convert to GDF, check results
    #############################################

    # GeoPandas function to properly get features from geojson
    gdf = gpd.GeoDataFrame.from_features(all_data)
    # custom function to set it to default geojson crs
    gdf = set_geojson_crs(gdf)

    # lets confirm our results match...
    #if not args.silent:
    if not silent_function:
        #print(f" Expected responses: {row_count}; actual: {len(all_data)}")
        print(f". Expected responses: {record_count}; actual: {len(gdf)}")
    # spit out an error if they don't
    expected_vs_actual_error =\
    f"ERROR - Missmatch between expected number of results ({record_count}) and actual number ({len(all_data)}). Aborting."
    if record_count != len(all_data):
        raise APICountMismatchError(expected_vs_actual_error)


    ##########################################################
    # section 1.5 - process gdf, export to PostGIS
    ##########################################################

    # make 'break_date' a DATE column, instead of DATETIME column, with useless minute values
    gdf['break_date'] = pd.to_datetime(gdf['break_date']).dt.date # convert to datetime, then force it to just DATE

    # rename the `:created_at` column so I keep my sanity later...
    gdf = gdf.rename(columns={':created_at': 'created_at'})


    # set our SQL engine
    engine = default_SQL_engine()

    # upload as new table to database
    try:
        gdf.to_postgis(DatabaseTables.watermain_breaks, engine, if_exists="replace", index=False,
                       dtype=dict(WATERMAIN_BREAKS_DATA_TYPES) # unwrap to a regular dict for the function call
                       )
    except Exception as e:
        raise DBError(f"Error - could not upload to PostGIS Database: {e}") from e


########################################################################################################################
### section 3 - logic for script to run by itself if called

def main() -> None:
    logger.info(f"Script: {__file__} started at {datetime.now(AB_TIME)}")# print statement for start of script, and current time
    waterMainBreaks_backfill(silent_function=False)
    logger.info(f"Script: {__file__} completed at {datetime.now(AB_TIME)}")# print statement for end of script, and current time


# call main
# this function will run by itself if this script is called, including the start & end time pieces
if __name__ == "__main__":
    main()