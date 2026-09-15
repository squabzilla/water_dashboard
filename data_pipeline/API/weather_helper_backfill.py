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
#  so I need great grand-parent folder instead of simply parent-folder
PROJECT_ROOT = Path(__file__).resolve().parents[2] 
# sets working directory to project root - there may be redundancy here but oh well lol
os.chdir(PROJECT_ROOT)
# Ensure repository code is importable when this wrapper is run directly.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))



########################################################################################################################
### script-setup 2: library imports
from collections.abc import Callable
from datetime import datetime # for getting current date
import httpx
import json
import pandas as pd
import geopandas as gpd
import logging


# custom libraries!
from data_pipeline.helper.helper_timezones import AB_TIME
from data_pipeline.helper.helper_API_errors import APITimeoutError, APIConnectError, APIResponseError, \
    APIZeroCountError, APICountMismatchError, DataUniquenessConstraintViolation, DBError, DataPipelineError
from data_pipeline.helper.helper_PSQL_config import default_SQL_engine
from data_pipeline.helper.helper_DB_update import export_as_new_table, add_new_records_to_table
from data_pipeline.helper.helper_progress_bar import update_progress_bar



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
                           dtype_dictionary: dict, progress_bar_prefix: str) -> int:

    start_year = 1956 # first date in watermain break data

    EXIT_CODE = 0
    # NOTE: I want to manually define and return the exit code,
    # so that the scripts that call this one can end themselves with that code
    # that way, if there's an error, the script can exit with a non-zero error code
    # and then when bash runs it, it can identify that the error code is not-zero, meaning THERE BE A PROBLEM GUYS
    # so if I hit any of my exceptions, the exit code becomes 1

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
        except DataPipelineError:
            EXIT_CODE = 1
            # this catches every subset of datapipeline error, so I don't need to specify each one!
            failed_years.append(year)
            if year == start_year: break
        except Exception as e:
            EXIT_CODE = 1
            msg = f"Unexpected error while backfilling daily-weather-records: {e}"
            logger.critical(msg, exc_info=True)
            break

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
                logger.exception(f"Warning: DBError: DB write failed for {year}")
                failed_years.append(year)

        else:
            # Write gdf to main table, overwriting old results if any
            # def export_as_new_table(gdf, engine, main_table_name, dtype_dictionary, main_table_unique_constraint_name, unique_column):
            try:
                export_as_new_table(gdf=gdf, engine=engine, main_table_name=main_table_name, dtype_dictionary=dtype_dictionary,
                                    main_table_unique_constraint_name=main_table_unique_constraint_name, unique_column=unique_column)
            except DBError:
                error_message = f"Error: DBError: Cannot create table for start year {year}; aborting backfill."
                logger.critical(error_message, exc_info=True)
                raise DBError(error_message) # this will end things script - but somethings gone HORRIBLY wrong if db connection fails here...

        progress_bar_count += 1
        # NOTE: let's update progress bar AFTER iteration of loop is done...
        update_progress_bar(iteration=progress_bar_count, total=total_iterations, prefix=progress_bar_prefix)
        # NOTE: progress bar output isn't recorded by Python log! Woo!

    logger.info(f"Number of failed years: {len(failed_years)}.")
    if len(failed_years) > 0:
        failed_years_string = ', '.join(failed_years)
        logger.error(f"Years failed: {failed_years_string}")

    # now we return the exit code
    return EXIT_CODE