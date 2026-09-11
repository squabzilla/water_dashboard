"""
Really simple function to just add timezone to hourly-weather-data, since local-date and UTC-date
are theoretically IN existing timezones, so now we just gotta tell Pandas or GeoPandas that
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
from datetime import datetime, timedelta # for getting date-time stuff
import psycopg # stuff needed to connect with postgis database
import sqlalchemy # stuff needed to connect with postgis database
import numpy as np # because I guess `np.nan` is better than `pd.NA` for no-data-values in Pandas?
import pandas as pd # just for merging dataframes, otherwise we use geopandas lol
import geopandas as gpd # geospatial library, used for GeoDataFrames
import httpx # used for calling API
import json # used for handling export of json data
import logging

# custom modules!
from data_pipeline.helper.helper_timezones import AB_TIME, UTC_TIME
from data_pipeline.helper.helper_SQL_tables import HourlyWeatherCols



########################################################################################################################
### section 1: function to add proper timezone to hourly-data gdf

def hourlyWeatherAddTimezone(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    # convert local date and utc date to datetime
    gdf[HourlyWeatherCols.hwc_local_date] = pd.to_datetime(gdf[HourlyWeatherCols.hwc_local_date])
    gdf[HourlyWeatherCols.hwc_utc_date] = pd.to_datetime(gdf[HourlyWeatherCols.hwc_utc_date])

    # add time zones
    gdf[HourlyWeatherCols.hwc_local_date] = gdf[HourlyWeatherCols.hwc_local_date].dt.tz_localize(AB_TIME)
    gdf[HourlyWeatherCols.hwc_utc_date] = gdf[HourlyWeatherCols.hwc_utc_date].dt.tz_localize(UTC_TIME)

    return gdf