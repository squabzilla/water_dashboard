########################################################################################################################
# file name: helper_SQL_tables.py
# author: William Hovdestad
#
# The purpose of this file is for standardized "constant" variables for my PSQL postgis table names.
# That way, I can ensure consistency in the use of table names across all the various Python files.



########################################################################################################################
### script-setup 1: project-root-setup
import os
import sys
from pathlib import Path

# gets file-path, (hopefully) resolves relative path issues, gets great-grand-parent folder
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# sets working directory to project root - there may be redundancy here but oh well lol
os.chdir(PROJECT_ROOT)
# Ensure repository code is importable when this wrapper is run directly.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))



########################################################################################################################
### script-setup 2: library imports
#from dotenv import load_dotenv # used for loading environment variables
#from dataclasses import dataclass # for making immutable classes, used for my CONFIG variables (user, login, API, etc.)
from types import MappingProxyType # for making immutable dicts, used for making immutable dict of column-types

from enum import StrEnum # Base class for creating enumerated constants that are also subclasses of str. (Notes)
# https://docs.python.org/3/library/enum.html#enum.StrEnum

import psycopg # stuff needed to connect with postgis database
import sqlalchemy # stuff needed to connect with postgis database
from geoalchemy2 import Geometry # used for "POINT" type
from sqlalchemy import text # make pylance happy by recognizing this as a keyword lol
from sqlalchemy import create_engine # stuff needed to connect with postgis database
from sqlalchemy import String, Date, DateTime, SmallInteger, Integer, Float, Boolean
import geopandas as gpd # geospatial library, used for GeoDataFrames

# setup environment directory which contains the `.env` file
env_dir = os.path.expanduser(r"~/.config/water_dashboard/.env")



########################################################################################################################
### section 1: variables for tables, and main station for weather data
"""
STATIONA FOR REFERENCE
| STATION_NAME     | CLIMATE_IDENTIFIER   | DLY_FIRST_DATE | DLY_LAST_DATE | HLY_FIRST_DATE | HLY_LAST_DATE | source-of-truth |
| ---------------- | -------------------- | ---------------| ------------- | -------------- | ------------- | --------------- |
| CALGARY INT'L CS | 3031094              | 1999-05-01     | *(current)*   | 2008-12-22     | *(current)*   | **Primary**     |
| CALGARY INTL A   | 3031092              | 2012-07-12     | *(current)*   | 2012-07-09     | *(current)*   | **Secondary**   |
| CALGARY INT'L A  | 3031093              | 1881-10-01     | 2012-07-11    | 1953-01-01     | 2012-07-12    | **Tertiary**    |
"""

PRIMARY_STATION_ID = "3031094"
SECONDARY_STATION_ID = "3031092"
TERTIARY_STATION_ID = "3031093"

STATION_CLIMATE_IDENTIFIERS = (PRIMARY_STATION_ID, SECONDARY_STATION_ID, TERTIARY_STATION_ID)


class DatabaseTables(StrEnum):
    weather_daily = "weather_daily"
    # weather_data_daily_2 = "weather_data_daily_2"
    weather_daily_staging = "weather_daily_staging"
    weather_hourly = "weather_hourly"
    weather_hourly_staging = "weather_hourly_staging"
    weather_stations = "weather_stations"
    watermain_breaks = "watermain_breaks"



########################################################################################################################
### section 2: variables related to daily-weather

# setup DatabaseCols class, initialize default variables so its less work to add more later
# note that I'm only putting columns in here if I need to use those columns in code somewhere
# basically helps me reference specific column names without using magic numbers

# NOTE: Explanation of what the hell I'm doing
# I'm making a custom class with the columns for each table, setting default values in class definition,
# and declaring an object of that class
#
# Would it be better to make a more general class definition for table-columns (like, in general),
# and declare an object of that class - with values matching the specific table-columns you're using?
# I mean, honestly, probably
# BUT that's not what I'm doing here
#
# ANYWAYS, this means I'm not relying on "magic strings"
# and that I'll get syntax errors if I mess up column references, 
# instead of potential confusion where I try to reference the same column with two ALMOST-BUT-NOT-QUITE identical names

class DailyWeatherCols(StrEnum):
    station_name = "STATION_NAME"
    climate_identifier = "CLIMATE_IDENTIFIER"
    local_date = "LOCAL_DATE"
    mean_temperature = "MEAN_TEMPERATURE"
    max_temperature = "MAX_TEMPERATURE"
    min_temperature = "MIN_TEMPERATURE"
    total_precipitation = "TOTAL_PRECIPITATION"
    total_rain = "TOTAL_RAIN"
    total_snow = "TOTAL_SNOW"

# now we want the list of values in that DAILY_WEATHER_COLS class/object I have, as a comma-seperated text-string
DAILY_WEATHER_PROPERTIES = ','.join(DailyWeatherCols)


# okay, I need to define the types for these; 
# this site: https://api.weather.gc.ca/openapi?f=html#/climate-daily/getClimate-dailySchema 
# gets me the info, I just need to make a dict - or mapping-proxy-type so its immutable

# class of DailyWeatherCols data-types
DAILY_WEATHER_DATA_TYPES = MappingProxyType({
    DailyWeatherCols.station_name: String(30), # name should be string less than 30 chars
    DailyWeatherCols.climate_identifier: Integer,
    DailyWeatherCols.local_date: Date,
    DailyWeatherCols.mean_temperature: Float,
    DailyWeatherCols.max_temperature: Float,
    DailyWeatherCols.min_temperature: Float,
    DailyWeatherCols.total_precipitation: Float,
    DailyWeatherCols.total_rain: Float,
    DailyWeatherCols.total_snow: Float,
})
# NOTE: I could generate this from API call, but it's probably easier to do it manually
# I'm not querying enough different APIs that have a separate schema API to be worth automating it
# I just need to set dtypes when I need to make sure that newly-queried hourly/daily data matches existing historical data
# especially if there's no data for that period, so GeoPandas arbitrarily decides what to assign a column with NULL



########################################################################################################################
### section 3: variables related to hourly-weather

# class of HourlyWeatherCols column-names
# NOTE: adding `DATETIME_STATION: String,` to end, for custom unique-identifier of table
class HourlyWeatherCols(StrEnum):
    station_name = "STATION_NAME"
    climate_identifier = "CLIMATE_IDENTIFIER"
    local_date = "LOCAL_DATE"
    utc_date = "UTC_DATE"
    temp = "TEMP"
    precip_amount = "PRECIP_AMOUNT"
    #relative_humidity = "RELATIVE_HUMIDITY"
    # NOTE: because daily-weather only has min and max humidity,
    # we're not including it in MVP - as otherwise we'd want to calculate avg daily humidity from hrly records,
    # and that's just outside the scope of MVP product

# create comma-seperated text of HourlyWeatherCols
HOURLY_WEATHER_PROPERTIES=','.join(HourlyWeatherCols)

# mapping-proxy-type of HourlyWeatherCols data-types
HOURLY_WEATHER_DATA_TYPES = MappingProxyType({
    HourlyWeatherCols.station_name: String(30), # name should be string less than 30 chars
    HourlyWeatherCols.climate_identifier: Integer,
    HourlyWeatherCols.utc_date: DateTime(timezone=False), # turns out this is a datetime variable???
    HourlyWeatherCols.local_date: DateTime(timezone=False), # turns out this is a datetime variable???
    HourlyWeatherCols.temp: Float,
    HourlyWeatherCols.precip_amount: Float,
    #HourlyWeatherCols.relative_humidity: Float,
})



########################################################################################################################
### section 4: variables related to WatermainBreaks
"""
EXAMPLE:
                      geometry  break_date break_type  status                         unique_key
0  POINT (-114.10588 51.01059)  2026-01-05         AC  ACTIVE  114.1058803 51.0105865 2026-01-05
"""

# class of WatermainBreaksCols column-names - at least ones I'll care about at end
class WatermainBreaksCols(StrEnum):
    break_date = "break_date"
    break_type = "break_type"
    status = "status"
    created = ":created_at"

WATERMAIN_BREAKS_DATA_TYPES = MappingProxyType({
    WatermainBreaksCols.break_date: Date,
    WatermainBreaksCols.break_type: String(8),
    # there are 8 "break_type" values:
    #  A - Full Circular, B - Split, C - Corrosion, D - Fitting, E - Joint, F - Diagonal Crack, G - Hole, S - Saddle
    # source: https://dev.socrata.com/foundry/data.calgary.ca/dpcu-jr23
    WatermainBreaksCols.status: String(8),
    # "status" values are either ACTIVE or RETIRED
    WatermainBreaksCols.created:  DateTime(timezone=False),
})