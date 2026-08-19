########################################################################################################################
# file name: waterMainBreaks_APIlogic.py
# author: William Hovdestad
#
# This script checks the watermainbreak API to see if our latest `created_at` value in our water main breaks table
# matches the latest `:created_at` value from Socrata's metadata on the watermain breaks page.
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
# get path for environment so I can load it later
env_dir = os.path.expanduser(r"~/.config/water_dashboard/.env")



########################################################################################################################
### script-setup 2: library imports
from datetime import datetime # used to get current time
import psycopg # stuff needed to connect with postgis database
import sqlalchemy # stuff needed to connect with postgis database
from sqlalchemy import text # make pylance happy by recognizing this as a keyword lol
#from shapely.geometry import Point # used to properly format lat/long values for use by GeoPandas
import httpx # used for calling API
#from dateutil.parser import parse # used for properly formatting DATE data into datetime variables
import json # used for handling export of json data

# custom modules!
#from backend.helper_PSQL import default_SQL_engine, DATABASE_CONFIG, DatabaseTables, WatermainBreaksCols, WATERMAIN_BREAKS_DATA_TYPES
from backend.API_Current.waterMainBreaks_backfill import waterMainBreaks_backfill
from backend.helper.helper_PSQL_config import DATABASE_CONFIG, default_SQL_engine
# def fetch_waterMainBreaks(starting_year, silent_function=False):



########################################################################################################################
### script-setup 3: print statement for start of script, and current time
print(f"Script: {__file__} started at {datetime.now()}")


########################################################################################################################
### section 1 - get the latest `created_at` time from our waterMainBreaks table or whateves I called it

from sqlalchemy import text
from sqlalchemy.orm import Session

engine = default_SQL_engine()

# 1. Define your raw SQL query
query = text("SELECT break_date FROM watermain_breaks ORDER BY break_date LIMIT 1")
query = text('SELECT created_at FROM watermain_breaks ORDER BY created_at LIMIT 1')

# 2. Execute and fetch the results
with engine.connect() as conn:
    result = conn.execute(query).scalars().all()
    sql_result = result[0]



########################################################################################################################
### section 2 - get the latest `:created_at` value from the API

JSON_QUERY_URL = "https://data.calgary.ca/api/v3/views/dpcu-jr23/query.json"

soql_query = f"""SELECT `:created_at` ORDER BY `:created_at` LIMIT 1"""

# payload - basically the API parameters
payload = {"query": soql_query, "includeSynthetic": False,}

# call the API
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
    response = response.json()
    API_response = response[0][':created_at']

if sql_result != API_response:
    print("New results; updating watermain breaks...")
    waterMainBreaks_backfill()

########################################################################################################################
### END - print script finish statement
print(f"Script: {__file__} completed at {datetime.now()}")