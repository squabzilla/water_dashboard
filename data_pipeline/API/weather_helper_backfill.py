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
from data_pipeline.helper.helper_SQL_tables import START_YEAR
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
### section 1 - function to determine if a year is valid or not 
### NOTE: includes `0` as valid input, which will be used to represent ALL years
def valid_year(year: int) -> None:
    if not type(year) is int:
        msg = f"Error: TypeError: Expecting an integer; got {year} which is a {type(year)}."
        raise TypeError(msg)
        # NOTE: since this is only expected to occur during command-line-argument usage, not logging the error
        # if there's an invalid year during regular backfill, another error will probably trigger lol
    start_year = START_YEAR
    current_year = datetime.now(AB_TIME).year # yeah I'm just being overly thorough with timezones lol
    # however, my API call is grabbing everything where LOCAL_YEAR = passed_year, so I want current_year in AB time lol
    stop_year = current_year + 1 # stop when we reach this year, BUT DO NOT PROCESS THIS YEAR
    valid_years = range(start_year, stop_year)
    #return(year in valid_years) # the statement `year in valid_years` will eval. to True or False
    if year not in [0, *valid_years]:
        msg = f"Error: ValueError: valid years are 0, or from {start_year} to {current_year} (inclusive). {year} not within that set."
        raise ValueError(msg)



########################################################################################################################
### section 2
"""
returns `year` value if single year failed
returns `0` otherwise
"""

def backfill_single_year(year: int, MSC_GeoMet_weather_by_year: Callable[[int], gpd.GeoDataFrame],
                         main_table_name: str, staging_table_name: str, datetimecol: str,
                         main_table_unique_constraint_name: str, staging_table_unique_constraint_name: str,
                         dtype_dictionary: dict) -> int:
    start_year = START_YEAR
    try:
        gdf = MSC_GeoMet_weather_by_year(year)
    except DataPipelineError: # NOTE: API errors logged by function that actually makes raw API calls
        if year == start_year:
            msg = f"Error: DataPipelineError: Cannot retrieve data for start year {year}; aborting backfill."
            logger.critical(msg)
            raise DataPipelineError(msg)
        return year
    except Exception as e:
        msg = f"Unexpected error while backfilling daily-weather-records: {e}"
        logger.critical(msg, exc_info=True)
        raise Exception(msg)
    
    # defining variables for database updating - putting multiple declaraions in one line because theres a lot lol
    gdf = gdf; engine = default_SQL_engine(); unique_column = datetimecol
    main_table_name=main_table_name; staging_table_name=staging_table_name; dtype_dictionary=dtype_dictionary
    main_table_unique_constraint_name=main_table_unique_constraint_name
    staging_table_unique_constraint_name=staging_table_unique_constraint_name
    

    if not year == start_year:
        try: # we want to update our table with new records if it's NOT the start year
            # because this is the backfill, we want to overwrite any records
            add_new_records_to_table(gdf=gdf, engine=engine, main_table_name=main_table_name,
                                        staging_table_name=staging_table_name, unique_column=unique_column,
                                        staging_table_unique_constraint_name=staging_table_unique_constraint_name,
                                        dtype_dictionary=dtype_dictionary, overwrite=True)
        except:
            logger.exception(f"Warning: DBError: DB write failed for {year}")
            return year

    else:
        try: # For first year only: Write gdf to main table, overwriting old results if any
            export_as_new_table(gdf=gdf, engine=engine, main_table_name=main_table_name, dtype_dictionary=dtype_dictionary,
                                main_table_unique_constraint_name=main_table_unique_constraint_name, unique_column=unique_column)
        except DBError:
            error_message = f"Error: DBError: Cannot create table for start year {year}; aborting backfill."
            logger.critical(error_message, exc_info=True)
            raise DBError(error_message) # this will end things script - but somethings gone HORRIBLY wrong if db connection fails here...
    
    return 0 # if we get here, return 0 suggesting status is good



########################################################################################################################
### section 3
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

    

    # local variables
    EXIT_CODE = 0 # exit code with 0 marking success, 1 marks that there was a problem
    start_year = START_YEAR # 1956 # first date in watermain break data
    current_year = datetime.now(AB_TIME).year # being overly thorough with timezones but API grabs things where `LOCAL_YEAR = passed_year` so want AB time
    stop_year = current_year + 1 # stop when we reach this year, BUT DO NOT PROCESS THIS YEAR
    failed_years = []

    # adding some logic just to be used during testing
    TESTING_CODE = False
    if TESTING_CODE == True:
        start_year = 2025
        warning_message = ("\n#############################################\nWARNING: START YEAR IS 2025 FOR TEST\n#############################################\n")
        logger.info(warning_message)

    # progress bar variables
    total_iterations = stop_year - start_year
    progress_bar_count = 0
    update_progress_bar(iteration=progress_bar_count, total=total_iterations, prefix=progress_bar_prefix) # first iteration is 0


    ###################### starting yearly backfill now

    for year in range(start_year, stop_year):
        # print(f"year: {year}")
        
        logger.info(f"{progress_bar_prefix} for year: {year}", extra={"console_exclude": True})
        # since I'm already passing a nice starting prefix explaining what I'm doing lol

        # run backfill single year, get exit code
        backfillExitCode = backfill_single_year(\
            year=year, MSC_GeoMet_weather_by_year=MSC_GeoMet_weather_by_year,
            main_table_name=main_table_name, staging_table_name=staging_table_name, datetimecol=datetimecol,
            main_table_unique_constraint_name=main_table_unique_constraint_name,
            staging_table_unique_constraint_name=staging_table_unique_constraint_name,
            dtype_dictionary=dtype_dictionary)
        # exit code will be the year if there was a problem; append the year to failed_years, set EXIT_CODE to 1
        if backfillExitCode != 0:
            failed_years.append(year)
            EXIT_CODE = 1

        # update progress bar AFTER iteration of loop is done...
        progress_bar_count += 1
        update_progress_bar(iteration=progress_bar_count, total=total_iterations, prefix=progress_bar_prefix)

    logger.info(f"Number of failed years: {len(failed_years)}.")
    if len(failed_years) > 0:
        failed_years_string = ', '.join(str(year) for year in failed_years)
        logger.error(f"Years failed: {failed_years_string}")

    # now we return the exit code
    return EXIT_CODE