########################################################################################################################
# file name: fetch_city_shapes.py
# author: William Hovdestad
#
# The goal of this script is to have a consistent function for handling my API-try-except error-handling code
# so it's consistent and I don't need to check what the hell I want to do every time.



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
# get path for environment so I can load it later




########################################################################################################################
### script-setup 2: library imports
from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone # for getting current date
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import httpx
import json
import logging

# custom modules!
from backend.helper.helper_PSQL_config import DATABASE_CONFIG
from backend.helper.helper_API_errors import DataPipelineError, APITimeoutError, APIConnectError, APIResponseError, \
APIZeroCountError, APICountMismatchError, DataUniquenessConstraintViolation, DBError


########################################################################################################################
### script-setup 3: logging config
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING) # STOP LOGGING EVERY API CALL DAMNIT
#logging.getLogger("httpcore").setLevel(logging.WARNING)
# LOGGING ORDER:
# debug
# info
# warning
# error
# critical



########################################################################################################################
### step 1: try-except block for weather API

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
def _fetch_weather_page(url: str, params: dict | None) -> dict:
    """Fetch a single page. Retried individually on transient failures."""
    response = httpx.get(url, params=params, timeout=30.0) # api call
    response.raise_for_status() # make sure status is good
    return response.json() # turn results into json



def try_except_weather_API(job_name: str, url: str, params: dict | None) -> dict:
    try:
        response = _fetch_weather_page(url, params)
    except httpx.TimeoutException as e:
        msg = f"Timed out during '{job_name}' after retries"
        logger.error(msg)
        raise APITimeoutError(msg) from e
        # NOTE: we aren't including {e} in error message, as we already have relevant info, rest is likely noise
    except httpx.ConnectError as e:
        msg = f"Connection error during '{job_name}' after retries: {e}"
        logger.error(msg)
        raise APIConnectError(msg) from e
        # NOTE: {e} here typically tells you specific underlying failture: 
        # DNS, connection refused, network unreachable, etc. - so worth keeping
    except httpx.HTTPStatusError as e:
        msg = f"Bad status during '{job_name}': {e.response.status_code}"
        logger.error(msg)
        raise APIResponseError(msg) from e
        # NOTE: {e.response.status_code} will typically give us relevant information, 
        # while removing extraneous noise from error message by selecting SPECIFICALLY the status-code
    except (KeyError, json.JSONDecodeError) as e:
        msg = f"Malformed page while paginating '{job_name}': {e}"
        logger.error(msg)
        raise APIResponseError() from e
        # NOTE: {e} here tells you WHAT was malformed, so its good to have here
    except Exception as e:
        msg = f"Unexpected error during '{job_name}': {e}"
        logger.critical(msg, exc_info=True) # critical error since we aren't prepared for it, and we want ALL info
        raise DataPipelineError() from e
        # NOTE: since ANYTHING could have happened here, we want whole error lol
    return response



########################################################################################################################
### step 2: try-except block for city-of-calgary API

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
def _fetch_city_page(url: str, payload: dict) -> dict:
    """Fetch a single page. Retried individually on transient failures."""
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
             url,
             json=payload,
             headers={"X-App-Token": DATABASE_CONFIG.app_token.get_secret_value()},
             auth=(
                  DATABASE_CONFIG.api_key.get_secret_value(),
                  DATABASE_CONFIG.api_secret_key.get_secret_value(),
                  ),
                  )
        response.raise_for_status()
        return response.json() # turn results into json

def try_except_city_API(job_name: str, url: str, payload: dict | None) -> dict:
    try:
        response = _fetch_city_page(url, payload)
    except httpx.TimeoutException as e:
        msg = f"Timed out during '{job_name}' after retries"
        logger.error(msg)
        raise APITimeoutError() from e
        # NOTE: we aren't including {e} in error message, as we already have relevant info, rest is likely noise
    except httpx.ConnectError as e:
        msg = f"Connection error during '{job_name}' after retries: {e}"
        logger.error(msg)
        raise APIConnectError(msg) from e
        # NOTE: {e} here typically tells you specific underlying failture: 
        # DNS, connection refused, network unreachable, etc. - so worth keeping
    except httpx.HTTPStatusError as e:
        msg = f"Bad status during '{job_name}': {e.response.status_code}"
        logger.error(msg)
        raise APIResponseError() from e
        # NOTE: {e.response.status_code} will typically give us relevant information, 
        # while removing extraneous noise from error message by selecting SPECIFICALLY the status-code
    except (KeyError, json.JSONDecodeError) as e:
        msg = f"Malformed page while paginating '{job_name}': {e}"
        logger.error(msg)
        raise APIResponseError() from e
        # NOTE: {e} here tells you WHAT was malformed, so its good to have here
    except Exception as e:
        msg = f"Unexpected error while during '{job_name}': {e}"
        logger.critical(msg, exc_info=True) # critical error since we aren't prepared for it, and we want ALL info
        raise DataPipelineError() from e
        # NOTE: since ANYTHING could have happened here, we want whole error lol
    return response