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
STN_IDS_STR_CSV_LIST = ", ".join(STATION_CLIMATE_IDENTIFIERS)


class DatabaseTables(StrEnum):
    weather_daily = "weather_daily"
    weather_daily_staging = "weather_daily_staging"
    weather_hourly = "weather_hourly"
    weather_hourly_staging = "weather_hourly_staging"
    weather_stations = "weather_stations"
    watermain_breaks = "watermain_breaks"
    watermain_pipes = "PublicWaterMain_Pipes"
    hydrology = "Hydrology"
    city_districts = "CommunityDistrictBoundaries"
    city_boundary = "CityBoundary"



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
    dwc_station_name = "STATION_NAME"
    dwc_climate_identifier = "CLIMATE_IDENTIFIER"
    dwc_local_date = "LOCAL_DATE" # NOTE: unique column
    dwc_local_year = "LOCAL_YEAR"
    dwc_mean_temperature = "MEAN_TEMPERATURE"
    dwc_max_temperature = "MAX_TEMPERATURE"
    dwc_min_temperature = "MIN_TEMPERATURE"
    dwc_total_precipitation = "TOTAL_PRECIPITATION"
    dwc_min_rel_humidity = "MIN_REL_HUMIDITY"
    dwc_max_rel_humidity = "MAX_REL_HUMIDITY"
    dwc_snow_on_ground = "SNOW_ON_GROUND"
    dwc_heating_degree_days = "HEATING_DEGREE_DAYS"
    dwc_cooling_degree_days = "COOLING_DEGREE_DAYS"
    # HWC_total_rain = "TOTAL_RAIN" # NOTE: cut from project - see `API_Readme.md` for more details
    # HWC_total_snow = "TOTAL_SNOW" # NOTE: cut from project - see `API_Readme.md` for more details
    # NOTE:
    # having class-acronym at starts means I can't grab the right key from the wrong table
    # this can cause an error that's hard to spot, since syntactically it's fine
    # but this way, grabbing the wrong key from the wrong table IMMEDIATELY causes an error

# now we want the list of values in that DAILY_WEATHER_COLS class/object I have, as a comma-seperated text-string
DAILY_WEATHER_PROPERTIES = ','.join(DailyWeatherCols)


# okay, I need to define the types for these; 
# this site: https://api.weather.gc.ca/openapi?f=html#/climate-daily/getClimate-dailySchema 
# gets me the info, I just need to make a dict - or mapping-proxy-type so its immutable

# class of DailyWeatherCols data-types
DAILY_WEATHER_DATA_TYPES = MappingProxyType({
    DailyWeatherCols.dwc_station_name: String(30), # name should be string less than 30 chars
    DailyWeatherCols.dwc_climate_identifier: Integer,
    DailyWeatherCols.dwc_local_date: Date,
    DailyWeatherCols.dwc_local_year: Integer,
    DailyWeatherCols.dwc_mean_temperature: Float,
    DailyWeatherCols.dwc_max_temperature: Float,
    DailyWeatherCols.dwc_min_temperature: Float,
    DailyWeatherCols.dwc_total_precipitation: Float,
    DailyWeatherCols.dwc_min_rel_humidity: Float,
    DailyWeatherCols.dwc_max_rel_humidity: Float,
    DailyWeatherCols.dwc_snow_on_ground: Float,
    DailyWeatherCols.dwc_heating_degree_days: Float, # documentation says `Int`, but I think it lied to me and it's float
    DailyWeatherCols.dwc_cooling_degree_days: Float, # documentation says `Int`, but I think it lied to me and it's float
    # DailyWeatherCols.total_rain: Float, # NOTE: cut from project - see `API_Readme.md` for more details
    # DailyWeatherCols.total_snow: Float, # NOTE: cut from project - see `API_Readme.md` for more details
})
# NOTE: I could generate this from API call, but it's probably easier to do it manually
# I'm not querying enough different APIs that have a separate schema API to be worth automating it
# I just need to set dtypes when I need to make sure that newly-queried hourly/daily data matches existing historical data
# especially if there's no data for that period, so GeoPandas arbitrarily decides what to assign a column with NULL
# NOTE: names with `CAPS_` always register as "valid" by VS Code linter, so making them all lowercase now

# ADD CONSTRAINT uq_{DatabaseTables.weather_data_daily_staging}_{DailyWeatherCols.datetime_station} UNIQUE ("{DailyWeatherCols.datetime_station}");
# uniqueness constraint for SQL
DAILY_WEATHER_UNIQUE_DATE_CONSTRAINT = f"uq_{DatabaseTables.weather_daily}_{DailyWeatherCols.dwc_local_date}"
DAILY_WEATHER_STAGING_UNIQUE_DATE_CONSTRAINT = f"uq_{DatabaseTables.weather_daily_staging}_{DailyWeatherCols.dwc_local_date}"




########################################################################################################################
### section 3: variables related to hourly-weather

# class of HourlyWeatherCols column-names
# NOTE: adding `DATETIME_STATION: String,` to end, for custom unique-identifier of table
class HourlyWeatherCols(StrEnum):
    hwc_station_name = "STATION_NAME"
    hwc_climate_identifier = "CLIMATE_IDENTIFIER"
    hwc_local_date = "LOCAL_DATE"
    hwc_utc_date = "UTC_DATE"
    hwc_local_year = "LOCAL_YEAR"
    hwc_temp = "TEMP"
    hwc_precip_amount = "PRECIP_AMOUNT"
    hwc_relative_humidity = "RELATIVE_HUMIDITY"
    hwc_station_pressure = "STATION_PRESSURE"
    hwc_wind_speed = "WIND_SPEED"
    hwc_wind_direction = "WIND_DIRECTION"
    hwc_dew_point = "DEW_POINT_TEMP"

# create comma-seperated text of HourlyWeatherCols
HOURLY_WEATHER_PROPERTIES=','.join(HourlyWeatherCols)

# mapping-proxy-type of HourlyWeatherCols data-types
HOURLY_WEATHER_DATA_TYPES = MappingProxyType({
    HourlyWeatherCols.hwc_station_name: String(30), # name should be string less than 30 chars
    HourlyWeatherCols.hwc_climate_identifier: Integer,
    HourlyWeatherCols.hwc_local_date: DateTime(timezone=False), # turns out this is a datetime variable???
    HourlyWeatherCols.hwc_utc_date: DateTime(timezone=False), # turns out this is a datetime variable???
    HourlyWeatherCols.hwc_local_year: Integer,
    HourlyWeatherCols.hwc_temp: Float,
    HourlyWeatherCols.hwc_precip_amount: Float,
    HourlyWeatherCols.hwc_relative_humidity: Float,
    HourlyWeatherCols.hwc_station_pressure: Float,
    HourlyWeatherCols.hwc_wind_speed: Float,
    HourlyWeatherCols.hwc_wind_direction: Float,
    HourlyWeatherCols.hwc_dew_point: Float,
})

class SWOBWeatherCols(StrEnum):
    swob_station_name="stn_nam-value"
    swob_climate_identifier="clim_id-value"
    swob_utc_date="date_tm-value"
    swob_temp="avg_air_temp_pst1hr"
    swob_precip_amount="pcpn_amt_pst1hr"
    swob_relative_humidity="avg_rel_hum_pst1hr"
    swob_station_pressure="stn_pres"
    swob_wind_speed="avg_wnd_spd_10m_pst1hr"
    swob_wind_direction="avg_wnd_dir_10m_pst1hr"
    swob_dew_point="avg_dwpt_temp_pst1hr"

HOURLY_SWOB_CONVERSION = MappingProxyType({
    f"{SWOBWeatherCols.swob_station_name}": f"{HourlyWeatherCols.hwc_station_name}",
    f"{SWOBWeatherCols.swob_climate_identifier}": f"{HourlyWeatherCols.hwc_climate_identifier}",
    # NOTE: `HourlyWeatherCols.hwc_local_date` will need to be calculated from `HourlyWeatherCols.hwc_utc_date`
    f"{SWOBWeatherCols.swob_utc_date}": f"{HourlyWeatherCols.hwc_utc_date}",
    # NOTE: `HourlyWeatherCols.hwc_local_year` will need to be calculated from `HourlyWeatherCols.hwc_local_date`
    f"{SWOBWeatherCols.swob_temp}": f"{HourlyWeatherCols.hwc_temp}", # celcius
    f"{SWOBWeatherCols.swob_precip_amount}": f"{HourlyWeatherCols.hwc_precip_amount}", # mm
    f"{SWOBWeatherCols.swob_relative_humidity}": f"{HourlyWeatherCols.hwc_relative_humidity}", # %
    f"{SWOBWeatherCols.swob_station_pressure}": f"{HourlyWeatherCols.hwc_station_pressure}", # hPa
    f"{SWOBWeatherCols.swob_wind_speed}": f"{HourlyWeatherCols.hwc_wind_speed}", # km/h
    f"{SWOBWeatherCols.swob_wind_direction}": f"{HourlyWeatherCols.hwc_wind_direction}", # degrees
    f"{SWOBWeatherCols.swob_dew_point}": f"{HourlyWeatherCols.hwc_dew_point}", # celcius
})
# fuck-off, not accepting my variable-values unless I tell you its a variable in a f-string

SWOB_PROPERTIES = ','.join(HOURLY_SWOB_CONVERSION)

# uniqueness constraint for SQL
HOURLY_WEATHER_UNIQUE_DATETIME_CONSTRAINT = f"uq_{DatabaseTables.weather_hourly}_{HourlyWeatherCols.hwc_local_date}"
HOURLY_WEATHER_STAGING_UNIQUE_DATETIME_CONSTRAINT = f"uq_{DatabaseTables.weather_hourly_staging}_{HourlyWeatherCols.hwc_local_date}"



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
    point = "point" # needed to get x/y coords
    created_API_name = ":created_at"
    created_PSQL_name = "created_at"

WATERMAIN_BREAKS_DATA_TYPES = MappingProxyType({
    WatermainBreaksCols.break_date: Date,
    WatermainBreaksCols.break_type: String(8),
    # there are 8 "break_type" values:
    #  A - Full Circular, B - Split, C - Corrosion, D - Fitting, E - Joint, F - Diagonal Crack, G - Hole, S - Saddle
    # source: https://dev.socrata.com/foundry/data.calgary.ca/dpcu-jr23
    WatermainBreaksCols.status: String(8),
    # "status" values are either ACTIVE or RETIRED
    WatermainBreaksCols.created_PSQL_name:  DateTime(timezone=True),
})