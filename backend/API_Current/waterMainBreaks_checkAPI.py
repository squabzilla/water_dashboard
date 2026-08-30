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



########################################################################################################################
### script-setup 2: library imports
from datetime import datetime # used to get current time
import psycopg # stuff needed to connect with postgis database
import sqlalchemy # stuff needed to connect with postgis database
from sqlalchemy import text # make pylance happy by recognizing this as a keyword lol
from sqlalchemy.orm import Session
#from shapely.geometry import Point # used to properly format lat/long values for use by GeoPandas
import httpx # used for calling API
#from dateutil.parser import parse # used for properly formatting DATE data into datetime variables
import json # used for handling export of json data
import logging # for logging stuff
from tenacity import ( # for retrying APIs so a single timeout doesn't cause a crash
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

# custom modules!
#from backend.helper_PSQL import default_SQL_engine, DATABASE_CONFIG, DatabaseTables, WatermainBreaksCols, WATERMAIN_BREAKS_DATA_TYPES
from backend.API_Current.waterMainBreaks_backfill import waterMainBreaks_backfill
from backend.helper.helper_PSQL_config import DATABASE_CONFIG, default_SQL_engine
from backend.helper.helper_API_errors import DataPipelineError, APITimeoutError, APIResponseError, \
    APICountMismatchError, APIZeroCountError, DataUniquenessConstraintViolation, DBError
# def fetch_waterMainBreaks(starting_year, silent_function=False):


########################################################################################################################
### script-setup 3: logging config
logfile = Path(PROJECT_ROOT) / "backend" / "API_Current" / "log_files" / "waterMainBreaks_checkAPI.log"
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
### section 1 - local helper function

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
def _checkWaterMainBreaksAPI(JSON_QUERY_URL: str, payload: dict) -> dict:
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
        return response.json()


########################################################################################################################
### section 2 - check API, get new results if there are updates

def main() -> None:
    ### step 1 - log current time
    logger.info(f"Script: {__file__} started at {datetime.now()}")

    engine = default_SQL_engine()

    # 1. Define your raw SQL query
    query = text("SELECT break_date FROM watermain_breaks ORDER BY break_date LIMIT 1")
    query = text('SELECT created_at FROM watermain_breaks ORDER BY created_at LIMIT 1')

    # 2. Execute and fetch the results
    with engine.connect() as conn:
        result = conn.execute(query).scalars().all()
        sql_result = result[0]



    ### step 2 - get the latest `:created_at` value from the API

    JSON_QUERY_URL = "https://data.calgary.ca/api/v3/views/dpcu-jr23/query.json"

    soql_query = f"""SELECT `:created_at` ORDER BY `:created_at` LIMIT 1"""

    # payload - basically the API parameters
    payload = {"query": soql_query, "includeSynthetic": False,}

    ### step 3 - call the API
    try:
        response = _checkWaterMainBreaksAPI(JSON_QUERY_URL, payload)
    except httpx.TimeoutException as e:
            raise APITimeoutError(f"Timed out fetching {JSON_QUERY_URL} after retries") from e
    except httpx.ConnectError as e:
        raise APITimeoutError(f"Connection error fetching {JSON_QUERY_URL} after retries") from e
    except httpx.HTTPStatusError as e:
        raise APIResponseError(f"Bad status fetching {JSON_QUERY_URL}: {e.response.status_code}") from e
    except (KeyError, json.JSONDecodeError) as e:
        raise APIResponseError(f"Malformed page while paginating {JSON_QUERY_URL}: {e}") from e
    except Exception as e:
        raise DataPipelineError(f"Unexpected error while fetching json {JSON_QUERY_URL}: {e}") from e

    API_response = response[0][':created_at']

    if sql_result != API_response:
        logger.info("New results; updating watermain breaks...")
        waterMainBreaks_backfill()

    ### END - log end time
    logger.info(f"Script: {__file__} completed at {datetime.now()}")



########################################################################################################################
### section 2 - logic for script to run by itself if called

# call main
# this function will run by itself if this script is called, including the start & end time pieces
if __name__ == "__main__":
    main()