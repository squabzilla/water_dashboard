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

# gets file-path, (hopefully) resolves relative path issues, gets great grand-parent folder
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# sets working directory to project root - there may be redundancy here but oh well lol
os.chdir(PROJECT_ROOT)
# Ensure repository code is importable when this wrapper is run directly.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))



########################################################################################################################
### script-setup 2: library imports
from datetime import datetime # for getting date-time stuff
import psycopg # stuff needed to connect with postgis database
import sqlalchemy # stuff needed to connect with postgis database
from sqlalchemy import text # make pylance happy by recognizing this as a keyword lol
from sqlalchemy import create_engine # stuff needed to connect with postgis database
import pandas as pd # dataframe library, for when I'm not ready to make the DataFrame all Geo quite yet
import geopandas as gpd # geospatial library, used for GeoDataFrames
from shapely.geometry import shape # used to properly assign/set Geometry values for GeoDataFrame
import httpx # used for calling API
import json # used for handling export of json data
import logging # used to log stuff


# custom modules!
from backend.helper.helper_progress_bar import update_progress_bar
from backend.helper.helper_timezones import AB_TIME
from backend.helper.helper_PSQL_config import default_SQL_engine
from backend.helper.helper_SQL_tables import DatabaseTables, WatermainBreaksCols, WATERMAIN_BREAKS_DATA_TYPES
from backend.helper.helper_set_geojson_crs import set_geojson_crs
from backend.helper.helper_API_try_except_job import try_except_city_API
from backend.helper.helper_API_errors import APICountMismatchError, APIZeroCountError, DBError


########################################################################################################################
### script-setup 3: logging config
logfile = Path(PROJECT_ROOT) / "backend" / "API" / "log_files" / f"{Path(__file__).stem}.log" # base log name on file name
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
### section 1: loop-through and fetch historical watermain-break data

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

    job_name = "counting-water-main-break-records"
    record_count_response = try_except_city_API(job_name=job_name, url=JSON_QUERY_URL, payload=payload)
    record_count = record_count_response[0]["COUNT"]
    record_count = int(record_count)
    if record_count == 0:
        msg = f"Error: APIZeroCountError: No matches found during {job_name}. Aborting."
        logger.error(msg)
        raise APIZeroCountError(msg)
    page_count = (record_count / page_size).__ceil__()
        

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
        response_data = response_data['features']
        all_data.extend(response_data)
        # add `response.json()` to `all_data`, extend works better than append for REASONS

        # update progress bar
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
    if not silent_function:
        print(f". Expected responses: {record_count}; actual: {len(gdf)}")

    # spit out an error if they don't
    if record_count != len(all_data):
        expected_vs_actual_error =\
        f"Error: APICountMismatchError: Missmatch between expected number of results ({record_count}) and actual number ({len(all_data)}). Aborting."
        logger.error(expected_vs_actual_error)
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
        msg = f"Error: DBError: could not upload to PostGIS Database: {e}"
        logger.error(msg)
        raise DBError(msg) from e


########################################################################################################################
### section 3 - logic for script to run by itself if called

def main() -> None:
    logger.info(f"Script: {__file__} started at {datetime.now(AB_TIME)}")# print statement for start of script, and current time
    waterMainBreaks_backfill(silent_function=False)
    logger.info(f"Script: {__file__} completed at {datetime.now(AB_TIME)}")# print statement for end of script, and current time


# call main - this function will run by itself if this script is called, including the start & end time pieces
if __name__ == "__main__":
    main()