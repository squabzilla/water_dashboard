########################################################################################################################
# file name: waterMainBreaks_APIlogic.py
# author: William Hovdestad
#
# The goal of this function is to create a function that backfills my watermain break data
# from the first recorded break to now
# and that if this script is called by itself, it execudes the script and backfills the database
# we explicitly keep the `:created_at` Socrata meta-data, so that we can later query the API
# and see if data has been updated since we last backfilled the database.
# This is done because the Socrata data has a full-replace of the data whenever the City wants to update the data,
# and Socrata's metadata column `created_at` is updated to reflect this time
# (Because it's all done at once, the values in this column are all identical)
# So if there's a discrepancy between my most recent `created_at` value, and Socrata's meta-data `:created_at` column,
# it's time to replace - we'll ALSO do a batch job of replacing all of our data.



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

# custom modules!
from backend.helper.helper_progress_bar import update_progress_bar
from backend.helper.helper_error import CustomErrorMessage

#from backend.helper_PSQL import default_SQL_engine, DATABASE_CONFIG, DatabaseTables, WatermainBreaksCols, WATERMAIN_BREAKS_DATA_TYPES, set_geojson_crs
from backend.helper.helper_PSQL_config import DATABASE_CONFIG, default_SQL_engine
from backend.helper.helper_SQL_tables import DatabaseTables, WatermainBreaksCols, WATERMAIN_BREAKS_DATA_TYPES
from backend.helper.helper_set_geojson_crs import set_geojson_crs


########################################################################################################################
### section 1: loop-through and fetch historical watermain-break data

# NOTE: first recorded watermain break is 1956/01/01

def waterMainBreaks_backfill(silent_function=False):
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

    # payload - basically the API parameters
    payload = {"query": soql_query, "includeSynthetic": False,}
    # `"includeSynthetic": False` prevents auto-generated, made-up columns from showing up, which are annoying

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
            row_count = response.json()[0]["COUNT"]
            row_count = int(row_count)
    page_count = (row_count / page_size).__ceil__()
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
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                GEOJSON_QUERY_URL,
                json=payload,
                headers={"X-App-Token": DATABASE_CONFIG.app_token.get_secret_value()},
                auth=(DATABASE_CONFIG.api_key.get_secret_value(),DATABASE_CONFIG.api_secret_key.get_secret_value(),),
                )
        response.raise_for_status()
        
        all_data.extend(response.json()['features'])
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
        print(f". Expected responses: {row_count}; actual: {len(gdf)}")
    # spit out an error if they don't
    expected_vs_actual_error =\
    f"ERROR - Missmatch between expected number of results ({row_count}) and actual number ({len(all_data)}). Aborting."
    if row_count != len(all_data): raise CustomErrorMessage(expected_vs_actual_error)


    ##########################################################
    # section 1.5 - process gdf, export to PostGIS
    ##########################################################

    # make 'break_date' a DATE column, instead of DATETIME column, with useless minute values
    gdf['break_date'] = pd.to_datetime(gdf['break_date']).dt.date # convert to datetime, then force it to just DATE

    # rename the `:created_at` column so I keep my sanity later...
    gdf = gdf.rename(columns={':created_at': 'created_at'})


    # set our SQL engine
    engine = default_SQL_engine()

    # return it    
    gdf.to_postgis(DatabaseTables.watermain_breaks, engine, if_exists="replace", index=False,
                   dtype=dict(WATERMAIN_BREAKS_DATA_TYPES) # unwrap to a regular dict for the function call
                   )


########################################################################################################################
### section 2 - logic for script to run by itself if called


# this function will run by itself if this script is called, including the start & end time pieces
if __name__ == "__main__":
    print(f"Script: {__file__} started at {datetime.now()}")# print statement for start of script, and current time
    waterMainBreaks_backfill(silent_function=False)
    print(f"Script: {__file__} completed at {datetime.now()}")# print statement for end of script, and current time