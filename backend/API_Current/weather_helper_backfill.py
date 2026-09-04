"""
file name: helper_fetch_API_page.py
author: William Hovdestad

This script to backfill my weather data, from from 1956 (first date in watermain break data) to current.
Takes, as input, a `fetch_year` function: 
this function takes an integer year as input, and returns a geodataframe
Also takes a bunch of other, slightly less relevant things lol
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
# from datetime import date, datetime, time, timedelta, timezone # for getting current date
from datetime import datetime # for getting current date
from zoneinfo import ZoneInfo
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import httpx
import json
import pandas as pd
import geopandas as gpd
import logging


# custom libraries!
from backend.helper.helper_timezones import AB_TIME, UTC_TIME
from backend.helper.helper_API_errors import DataPipelineError, APITimeoutError, APIConnectError, APIResponseError, \
    APIZeroCountError, APICountMismatchError, DataUniquenessConstraintViolation, DBError
from backend.helper.helper_set_geojson_crs import set_geojson_crs
from backend.helper.helper_PSQL_config import default_SQL_engine
from backend.helper.helper_DB_update import export_as_new_table, add_new_records_to_table
from backend.helper.helper_progress_bar import update_progress_bar



########################################################################################################################
### script-setup 3: logging config
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING) # STOP LOGGING EVERY API CALL DAMNIT



########################################################################################################################
### section 1
### Function to backfill years of weather data, from 1956 (first date in watermain break data) to current.
### Takes, as input, a `fetch_year` function: 
### this function takes an integer year as input, and returns a geodataframe
### Also takes a bunch of other, slightly less relevant things lol


# NOTE: syntax for function as an argument is:
# def my_function_name(secondary_function_local_name: Callable[[Int], Int]) -> None:
# I can call the "local" name of secondary function whatever I want, but I need `Callable` from
# from collections.abc import Callable
# and the syntax (if I want typehints) is `Callable[[input-data-type-1], output-data-type]
def backfill_weather_years(MSC_GeoMet_weather_by_year: Callable[[int], gpd.GeoDataFrame],
                           main_table_name: str, staging_table_name: str, datetimecol: str,
                           main_table_unique_constraint_name: str, staging_table_unique_constraint_name: str,
                           dtype_dictionary: dict, progress_bar_prefix: str) -> None:

    start_year = 1956 # first date in watermain break data
    TESTING_CODE = False
    if TESTING_CODE == True: start_year = 2025
    if start_year == 2025:
        warning_message = (
            "\n##################################################\nWARNING: START YEAR IS 2025 FOR TEST\n##################################################\n"
        )
        print(warning_message)
        logger.info(warning_message)

    #current_year = date.today().year
    current_year = datetime.now(AB_TIME).year # yeah I'm just being overly thorough with timezones lol
    stop_year = current_year + 1 # stop when we reach this year, BUT DO NOT PROCESS THIS YEAR

    failed_years = []

    # progress bar variables
    total_iterations = stop_year - start_year
    progress_bar_count = 0
    update_progress_bar(iteration=progress_bar_count, total=total_iterations, prefix=progress_bar_prefix) # first iteration is 0


    for year in range(start_year, stop_year):
        # print(f"year: {year}")
        
        logger.info(f"{progress_bar_prefix} for year: {year}")
        # since I'm already passing a nice starting prefix explaining what I'm doing lol

        try:
            gdf = MSC_GeoMet_weather_by_year(year)
        except APITimeoutError:
            logger.error(f"Network timeout for {year}")
            # NOTE: `logger.error` records the error message, without traceback to previous error messages;
            # because in this particular case, we know the whole story from the first message alone
            # traceback will give us more messages saying the same "OMG THE API TIMED OUT" and we don't need that in our lives
            failed_years.append(year)
            if year == start_year: break
            else: continue
        except APIConnectError:
            logger.exception(f"Error connecting to network for {year}")
            failed_years.append(year)
            if year == start_year: break
            else: continue
        except APIResponseError:
            logger.exception(f"Malformed response for {year}")
            # NOTE: `logger.exception` does traceback, so it records all the error messages that triggered/preceded this one as well
            # that's because we'll want to get more detail about WHAT, exactly, went wrong with the API call & response
            # was it a bad HTTP status? asking the API for non-existant properties? we want fo figure out what caused it
            # NOTE: this one is the same level as `logger.error`
            failed_years.append(year)
            if year == start_year: break
            else: continue
        except APIZeroCountError:
            logger.warning(f"No records found for {year}")
            # still no traceback, but we're not going "OMG SOMETHING WENT HORRIBLY WRONG" here
            # this is "user made a mistake and queried something with 0 results" instead of an incorrectly formatted query
            failed_years.append(year)
            if year == start_year: break
            else: continue
        except APICountMismatchError:
            logger.exception(f"Inconsistent number of records found for {year}")
            failed_years.append(year)
            if year == start_year: break
            else: continue
        except DataUniquenessConstraintViolation:
            logger.error(f"Dates not unique for daily-weather backfill, year: {year}")
            failed_years.append(year)
            if year == start_year: break
            else: continue
        except Exception as e:
            logger.error(f"Unexpected error while backfilling daily-weather-records: {e}")
            failed_years.append(year)
            if year == start_year: break
            else: continue

        # define variables for database updating
        gdf = gdf
        engine = default_SQL_engine()
        main_table_name = main_table_name
        staging_table_name = staging_table_name
        unique_column = datetimecol
        main_table_unique_constraint_name = main_table_unique_constraint_name
        staging_table_unique_constraint_name = staging_table_unique_constraint_name
        dtype_dictionary = dtype_dictionary

        if not year == start_year:
            # we want to update our table with new records if it's NOT the start year
            # def add_new_records_to_table(gdf, engine, main_table_name, staging_table_name,
                                         # unique_column, staging_table_unique_constraint_name,
                                         # dtype_dictionary)
            try:
                # because this is the backfill, we want to overwrite any records
                add_new_records_to_table(gdf=gdf, engine=engine, main_table_name=main_table_name,
                                         staging_table_name=staging_table_name, unique_column=unique_column,
                                         staging_table_unique_constraint_name=staging_table_unique_constraint_name,
                                         dtype_dictionary=dtype_dictionary, overwrite=True)
            except:
                logger.exception(f"DB write failed for {year}")
                failed_years.append(year)

        else:
            # Write gdf to main table, overwriting old results if any
            # def export_as_new_table(gdf, engine, main_table_name, dtype_dictionary, main_table_unique_constraint_name, unique_column):
            try:
                export_as_new_table(gdf=gdf, engine=engine, main_table_name=main_table_name, dtype_dictionary=dtype_dictionary,
                                    main_table_unique_constraint_name=main_table_unique_constraint_name, unique_column=unique_column)
            except DBError:
                error_message = f"Cannot create table for start year {year}; aborting backfill."
                logger.critical(error_message, exc_info=True)
                raise DBError(error_message) # this will end things script - but somethings gone HORRIBLY wrong if db connection fails...

        progress_bar_count += 1
        # NOTE: let's update progress bar AFTER iteration of loop is done...
        update_progress_bar(iteration=progress_bar_count, total=total_iterations, prefix=progress_bar_prefix)
        # NOTE: progress bar output isn't recorded by Python log! Woo!

    print("") # ending-newline-statement for progress bar lol
    logger.info(f"Number of failed years: {len(failed_years)}.")
    if len(failed_years) > 0:
        failed_years_string = ', '.join(failed_years)
        logger.error(f"Years failed: {failed_years_string}")