########################################################################################################################
# file name: weather_helper_API.py
# author: William Hovdestad
#
# This script contains the logic to filter my weather stations based on my defined station-priority
# (see `API_Readme.md` for more details)



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
import pandas as pd
import geopandas as gpd
import logging


# custom libraries!
from backend.helper.helper_API_errors import APITimeoutError, APIResponseError, APICountMismatchError, \
    APIZeroCountError, DataUniquenessConstraintViolation, DBError
from backend.helper.helper_SQL_tables import PRIMARY_STATION_ID, SECONDARY_STATION_ID, TERTIARY_STATION_ID
from backend.helper.helper_set_geojson_crs import set_geojson_crs
from backend.helper.helper_PSQL_config import default_SQL_engine
from backend.helper.helper_DB_update import export_as_new_table, add_new_records_to_table


########################################################################################################################
### script-setup 3: logging config
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING) # STOP LOGGING EVERY API CALL DAMNIT
#logging.getLogger("httpcore").setLevel(logging.WARNING)



########################################################################################################################
### section 1: filter stations by priority
def filter_stations_by_priority(df: pd.DataFrame | gpd.GeoDataFrame, station_id_col: str="CLIMATE_IDENTIFIER",
                                datetime_col: str="LOCAL_DATE") -> pd.DataFrame | gpd.GeoDataFrame:
    df = df.copy()
    STATION_PRIORITY_COL = "station_priority"
    STATION_PRIORITY_ORDER = {
        PRIMARY_STATION_ID: 1,
        SECONDARY_STATION_ID: 2,
        TERTIARY_STATION_ID: 3,
    }
    df[STATION_PRIORITY_COL] = df[station_id_col].map(STATION_PRIORITY_ORDER)
    df = ( # operation we're doing to df
        df # start with df
        .sort_values([datetime_col, STATION_PRIORITY_COL]) # order df by DATETIME, then STATION-PRIORITY
        .drop_duplicates(subset=datetime_col, keep="first") # drop duplicate datetimes - keep only first record
        .sort_values(datetime_col) # let's resort stuff by date
        .reset_index(drop=True) # nasty shit happens if you do operations like this and don't reset index lol
    )
    df = df.drop(columns=[STATION_PRIORITY_COL]) # we don't need this column anymore, lets remove it
    return df