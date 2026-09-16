"""
file name: watermain_custom_GEOJSONs_import.py
author: William Hovdestad

During some preliminary work, I isolated the two main Bearspaw watermain-break events,
as well as the critical pipeline those breaks occurred on.

I isolated and saved both the watermain-break points, and the critical-pipeline line - as GeoJSONs.
This script imports those custom GeoJSONs into my PostGIS PSQL database.
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
import logging
from datetime import datetime # for getting date-time stuff
import psycopg # stuff needed to connect with postgis database
import sqlalchemy # stuff needed to connect with postgis database
import pandas as pd # dataframe library, for when I'm not ready to make the DataFrame all Geo quite yet
import geopandas as gpd # geospatial library, used for GeoDataFrames


# custom modules!
from data_pipeline.helper.helper_PSQL_config import default_SQL_engine
from data_pipeline.helper.helper_logging_config import setup_logging
from data_pipeline.helper.helper_SQL_tables import DatabaseTables, WATERMAIN_BREAKS_DATA_TYPES, WATER_PIPES_DATA_TYPES
from data_pipeline.helper.helper_API_errors import DBError



########################################################################################################################
### script-setup 3: logging config - now with a helper function!
# NOTE: 
# moved most logging config logic to `main()`, so we don't make duplicate `setup_logging` calls 
# in the case that waterMainBreaks_backfill() is called from another script
logger = logging.getLogger(__name__)



########################################################################################################################
### section 1: import custom GEOJSONs and slap them in database

def add_custom_geojsons():
    # get paths I want
    select_watermain_breaks = Path(PROJECT_ROOT) / "data_pipeline" / "custom_geojson" / "select_watermain_breaks.geojson"
    select_water_pipes = Path(PROJECT_ROOT) / "data_pipeline" / "custom_geojson" / "select_watermain.geojson"

    # make them GDFs
    gdf_select_breaks = gpd.read_file(select_watermain_breaks)
    gdf_select_pipes = gpd.read_file(select_water_pipes)

    # get sql engine
    engine = default_SQL_engine()

    # upload as new table to database
    try:
        gdf_select_breaks.to_postgis(DatabaseTables.select_watermain_breaks, engine, if_exists="replace", index=False,
                                     dtype=dict(WATERMAIN_BREAKS_DATA_TYPES)) # unwrap to a regular dict for the function call
    except Exception as e:
        msg = f"Error: DBError: could not upload 'select_watermain_breaks' to PostGIS Database: {e}"
        logger.error(msg, exc_info=True)
        raise DBError(msg) from e

    # upload as new table to database
    try:
        gdf_select_pipes.to_postgis(DatabaseTables.select_watermain_pipes, engine, if_exists="replace", index=False,
                                    dtype=dict(WATER_PIPES_DATA_TYPES)) # unwrap to a regular dict for the function call
    except Exception as e:
        msg = f"Error: DBError: could not upload 'select_watermain_pipes' to PostGIS Database: {e}"
        logger.error(msg, exc_info=True)
        raise DBError(msg) from e



########################################################################################################################
### section 4: setup and call main

def main() -> None:
    # setup logging in main
    logfile = Path(PROJECT_ROOT) / "data_pipeline" / "API" / "log_files" / f"{Path(__file__).stem}.log" # base log name on file name
    setup_logging(logfile) # NOTE: logging config already adds current time

    # log start
    logger.info(f"Script: {__file__} started.")# print statement for start of script, and current time

    # try fetch_all_layers, log error if fails
    try:
        add_custom_geojsons()
    except Exception as e:
        msg = f"Unexpected error while running {Path(__name__).name}: {e}"
        logger.critical(msg, exc_info=True)
        raise Exception(msg)

    # log end
    logger.info(f"Script: {__file__} completed.")# print statement for end of script, and current time


# call main
# this function will run by itself if this script is called, including the start & end time pieces
if __name__ == "__main__":
    main()