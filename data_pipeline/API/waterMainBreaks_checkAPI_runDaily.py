"""
file name: waterMainBreaks_APIlogic.py
author: William Hovdestad

This script checks the watermainbreak API to see if our latest `created_at` value in our water main breaks table
matches the latest `:created_at` value from Socrata's metadata on the watermain breaks page.
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
import httpx # used for calling API
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
from data_pipeline.helper.helper_logging_config import setup_logging
from data_pipeline.helper.helper_timezones import AB_TIME
from data_pipeline.API.waterMainBreaks_backfill import waterMainBreaks_backfill
from data_pipeline.helper.helper_PSQL_config import DATABASE_CONFIG, default_SQL_engine
from data_pipeline.helper.helper_API_errors import DataPipelineError, APITimeoutError, APIConnectError, APIResponseError, APIStatusError


########################################################################################################################
### script-setup 3: logging config  - now with a helper function!
logfile = Path(PROJECT_ROOT) / "data_pipeline" / "API" / "log_files" / f"{Path(__file__).stem}.log" # base log name on file name
setup_logging(logfile)
logger = logging.getLogger(__name__)



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
    logger.info(f"Script: {__file__} started.")

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
        msg = f"Error: APITimeoutError: Timed out fetching {JSON_QUERY_URL} after retries"
        logger.error(msg)
        raise APITimeoutError(msg) from e
    except httpx.ConnectError as e:
        msg = f"Error: APIConnectError: Connection error fetching {JSON_QUERY_URL} after retries"
        logger.error(msg)
        raise APIConnectError(msg) from e
    except httpx.HTTPStatusError as e:
        msg = f"Error: APIStatusError: Bad status fetching {JSON_QUERY_URL}: {e.response.status_code}"
        logger.error(msg)
        raise APIStatusError(msg) from e
    except (KeyError, json.JSONDecodeError) as e:
        msg = f"Error: APIResponseError: Malformed page while paginating {JSON_QUERY_URL}: {e}"
        logger.error(msg)
        raise APIResponseError(msg) from e
    except Exception as e:
        msg = f"Error: DataPipelineError: CRITICAL ERROR: Unexpected error while fetching json {JSON_QUERY_URL}: {e}"
        logger.critical(msg, exc_info=True) # critical error since we aren't prepared for it, and we want ALL info
        raise DataPipelineError(msg) from e

    API_response = response[0][':created_at']
    # convert API response to proper datetime variable, so I can compare the two objects properly
    API_response = datetime.fromisoformat(API_response)

    if sql_result != API_response:
        logger.info("New results; updating watermain breaks...")
        waterMainBreaks_backfill()

    ### END - log end time
    logger.info(f"Script: {__file__} completed.")



########################################################################################################################
### section 2 - logic for script to run by itself if called

# call main
# this function will run by itself if this script is called, including the start & end time pieces
if __name__ == "__main__":
    main()