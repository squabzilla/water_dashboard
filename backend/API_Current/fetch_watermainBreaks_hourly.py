########################################################################################################################
# file name: fetch_watermainBreaks_historical.py
# author: William Hovdestad
#
# The goal of this script is to fetch historical watermain breaks, from Jan 01 2000 forward.
# That's the historical water-main-break data we want to update our PostGIS database with.
# ...honestly, considering that the real-database might update the status of watermainbreaks
#    days, or potentially weeks after they occur, I could just run THIS script daily to make sure it's updated lol



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
import pandas as pd # dataframe library, for when I'm not ready to make the DataFrame all Geo quite yet
import geopandas as gpd # geospatial library, used for GeoDataFrames
from shapely.geometry import shape # used to properly assign/set Geometry values for GeoDataFrame
#from shapely.geometry import Point # used to properly format lat/long values for use by GeoPandas
import httpx # used for calling API
#from dateutil.parser import parse # used for properly formatting DATE data into datetime variables
import json # used for handling export of json data

# custom modules!
from backend.helper_progress_bar import update_progress_bar
from backend.helper_error import CustomErrorMessage
from backend.helper_PSQL import default_SQL_engine, DATABASE_CONFIG, DatabaseTables, WatermainBreaksCols, WATERMAIN_BREAKS_DATA_TYPES



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
### section 1: loop-through and fetch historical watermain-break data


########################################################
# section 1.1 - set up variables for the looped-API call
########################################################

# url of API
url = "https://data.calgary.ca/api/v3/views/dpcu-jr23/query.json"

#### set variables to help use pagination to get all data ####
limit = 100
#next_year = datetime.now().year + 1 # variable for start of next year
start_year = 2000
all_data = []

date_column_name = WatermainBreaksCols.break_date
page_size = 1000


# years = range(2000, next_year) # years from 2000 thru current-year (stops when it hits `next_year` value)
# months = range(1,13) # months from 1 thru 12 (stops at 13)




#### set API variables 
CALGARY_APP_TOKEN = DATABASE_CONFIG.app_token
CALGARY_API_KEY = DATABASE_CONFIG.api_key               # Key ID -> Basic Auth username -> api-key
CALGARY_API_SECRET = DATABASE_CONFIG.api_secret_key     # Key Secret -> Basic Auth password -> api-secret-key

QUERY_URL = "https://data.calgary.ca/api/v3/views/dpcu-jr23/query.json"


##############################################################
# section 1.2 - get total count of records we want to retrieve
##############################################################

# query to get a count of the data
soql_query = f"""SELECT COUNT(*) WHERE date_extract_y(`{date_column_name}`) >= {start_year}"""

# payload - basically the API parameters
payload = {"query": soql_query, "includeSynthetic": False,}
# `"includeSynthetic": False` prevents auto-generated, made-up columns from showing up, which are annoying

with httpx.Client(timeout=30.0) as client:
        response = client.post(
            QUERY_URL,
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


###########################
# section 1.3 - DO THE LOOP
###########################

# setup progress bar first tho
total_iterations = page_count
prefix = "Fetching watermain breaks"
if not args.silent: # this lets us turn off printing the progress bar if we add -s when running!
    update_progress_bar(iteration=0, total=total_iterations, prefix=prefix) # first iteration is 0

# query to get the actual data itself
soql_query = f"""SELECT * WHERE date_extract_y(`{date_column_name}`) >= {start_year} ORDER BY `{date_column_name}`"""

# now we loop through our paginated API
for i in range(page_count):
    page_number = i + 1 # since I want this 1-indexed, not 0-indexed
    # payload - basically the API parameters
    payload = {"query": soql_query,
               "page": {"pageNumber": page_number, "pageSize": page_size},
               "includeSynthetic": False, }
                # `"includeSynthetic": False` prevents auto-generated, made-up columns from showing up
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
             QUERY_URL,
             json=payload,
             headers={"X-App-Token": DATABASE_CONFIG.app_token.get_secret_value()},
             auth=(DATABASE_CONFIG.api_key.get_secret_value(),DATABASE_CONFIG.api_secret_key.get_secret_value(),),
             )
    response.raise_for_status()
    all_data.extend(response.json())
    # add `response.json()` to `all_data`, extend works better than append for REASONS

    # update progress bar
    if not args.silent:
        update_progress_bar(iteration=page_number, total=total_iterations, prefix=prefix)

# done loop

# NOTE:
# example return output:
# [
#   {
#       'break_date': '2025-01-04T00:00:00.000', 'break_type': 'DS', 'status': 'ACTIVE',
#       'point':    {
#                      'type': 'Point', 'coordinates': [-114.1023903, 51.1297841]
#                   }
#   }
# ]


##########################################################
# section 1.5 - check results, convert to GDF, process GDF
##########################################################
# lets confirm our results match...
if not args.silent:
    print(f" Expected responses: {row_count}; actual: {len(all_data)}")
# spit out an error if they don't
expected_vs_actual_error =\
f"ERROR - Missmatch between expected number of results ({row_count}) and actual number ({len(all_data)}). Aborting."
if row_count != len(all_data):
    raise CustomErrorMessage(expected_vs_actual_error)


# turn our stuff into a pandas dataframe, while we fix it up for GeoDataFrame conversion
df_all_data = pd.DataFrame(all_data)
del all_data # we don't need this anymore


df_all_data[WatermainBreaksCols.point] = df_all_data[WatermainBreaksCols.point].apply(shape)
# converts objects in `point` column into shapely Point objects,
# assuming objects are formatted in a way that shapely can recognize,
# and stores those new Point objects in a new "geometry" column


# now we can turn it into a proper geojson
gdf_all_data = gpd.GeoDataFrame(df_all_data, geometry=WatermainBreaksCols.point, crs="EPSG:4326")
# NOTE: newer geojsons don't have a CRS, and assume EPSG 4326 is CRS
del df_all_data # we don't need this anymore


# add columns for X/Y values of coordinates
gdf_all_data[WatermainBreaksCols.x] = gdf_all_data[WatermainBreaksCols.point].x
gdf_all_data[WatermainBreaksCols.y] = gdf_all_data[WatermainBreaksCols.point].y


# get rid of unnecessary auto-generated columns
keep_cols = [col for col in WatermainBreaksCols] # this is what we need to convert `strenum` to list
keep_cols = [col for col in WATERMAIN_BREAKS_DATA_TYPES]
gdf_all_data = gdf_all_data[keep_cols]
"""print("Filtered cols:")
print(gdf_all_data.columns,"\n")"""


# check uniqueness of dates
# NOTE: while it was interesting to note all dates are unique, it doesn't seem relevant right now
# if not gdf_all_data[WatermainBreaksCols.break_date].is_unique: print("all dates unique")
# else: print("overlapping dates")



########################################################################################################################
### section 2 - actually save our data to use later

# set engine
engine = default_SQL_engine()


# Add daily-weather-data to PostGIS
# NOTE: not setting dtype on the weather station; I only really care about dtype if I need to prevent a type-mismatch
# when adding new hourly/daily data to an existing database table
gdf_all_data.to_postgis(DatabaseTables.watermain_breaks, engine, if_exists="replace", index=False,
                        dtype=dict(WATERMAIN_BREAKS_DATA_TYPES) # unwrap to a regular dict for the function call
                        )

#gdf_all_data.to_postgis(DatabaseTables.watermain_breaks, engine, if_exists="replace", index=False)
#print(gdf_all_data.head(1))



########################################################################################################################
### END - print script finish statement
print(f"Script: {__file__} completed at {datetime.now()}")