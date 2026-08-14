########################################################################################################################
# file name: helper_PSQL.py
# author: William Hovdestad
#
# The purpose of this file is for standardized "constant" variables for my PSQL postgis table names.
# That way, I can ensure consistency in the use of table names across all the various Python files.

# TODO:
# need to modify .env file so `postgres_host`, `post_gres_port` and `database_name` aren't hardcoded
# - see line 196 at `class DBConfig(BaseSettings):`
# note from Claude about this:
"""
One thing worth reconsidering: postgres_host, postgres_port, and database_name are hardcoded as class defaults rather than pulled from .env.
That's fine for now since your DB is local, but you've mentioned a DigitalOcean droplet as your deployment target for this project - 
once you deploy, the host almost certainly won't be localhost and the port likely won't be 5433 (no native/containerized conflict to dodge on a droplet).
Hardcoding those means editing the Python file itself between dev and prod, which is exactly the problem pydantic-settings is meant to avoid.
Worth moving POSTGRES_HOST, POSTGRES_PORT, and DATABASE_NAME into .env too (keeping the current values only as fallback defaults) once you're closer to deploying.
"""

# TODO:
# Clean up this file lol

########################################################################################################################
### script-setup 1: project-root-setup
import os
import sys
from pathlib import Path

# gets file-path, (hopefully) resolves relative path issues, gets grand-parent folder
PROJECT_ROOT = Path(__file__).resolve().parents[1]
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

STATION_NAME = "CALGARY INT'L A"
STATION_CLIMATE_IDENTIFIER = "3031094"
STATION_CLIMATE_IDENTIFIERS = ("3031092", "3031093", "3031094")


class DatabaseTables(StrEnum):
    weather_data_daily = "weather_data_daily"
    weather_data_daily_2 = "weather_data_daily_2"
    weather_data_daily_staging = "weather_data_staging"
    weather_data_hourly = "weather_data_hourly"
    weather_data_hourly_staging = "weather_data_hourly_staging"
    weather_stations = "weather_stations"
    watermain_breaks = "watermain_breaks"



########################################################################################################################
### section 2: variables related to weather

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
    min_temperature = "MIN_TEMPERATURE"
    max_temperature = "MAX_TEMPERATURE"
    total_precipitation = "TOTAL_PRECIPITATION"
    total_rain = "TOTAL_RAIN"
    total_snow = "TOTAL_SNOW"
    station_id = "STN_ID"
# now we want the list of values in that DAILY_WEATHER_COLS class/object I have, as a comma-seperated text-string
DAILY_WEATHER_PROPERTIES = ','.join(DailyWeatherCols)

# class HourlyWeatherCols(StrEnum)

# okay, I need to define the types for these; 
# this site: https://api.weather.gc.ca/openapi?f=html#/climate-daily/getClimate-dailySchema 
# gets me the info, I just need to make a dict - or mapping-proxy-type so its immutable

# class of DailyWeatherCols data-types
DAILY_WEATHER_DATA_TYPES = MappingProxyType({
    # DailyWeatherCols.climate_identifier: String(10), # this should realistically have less than 10 characters
    # NOTE: turns out I don't want this for final database lol
    DailyWeatherCols.station_name: String(30), # name should be string less than 30 chars
    DailyWeatherCols.climate_identifier: Integer,
    DailyWeatherCols.local_date: Date,
    DailyWeatherCols.mean_temperature: Float,
    DailyWeatherCols.min_temperature: Float,
    DailyWeatherCols.max_temperature: Float,
    DailyWeatherCols.total_precipitation: Float,
    DailyWeatherCols.total_rain: Float,
    DailyWeatherCols.total_snow: Float,
    #DailyWeatherCols.station_3031094: Boolean,#(default=False),
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
    utc_date = "UTC_DATE"
    local_date = "LOCAL_DATE"
    temp = "TEMP"
    precip_amount = "PRECIP_AMOUNT"
    relative_humidity = "RELATIVE_HUMIDITY"
    windchill = "WINDCHILL"
    wind_direction = "WIND_DIRECTION"
    wind_speed = "WIND_SPEED"
    weather_eng_desc = "WEATHER_ENG_DESC"
    # datetime_station = DATETIME_STATION

# create text-description of HourlyWeatherCols
"""
HOURLY_WEATHER_PROPERTIES = ""
for item in HourlyWeatherCols:
    # if item == DATETIME_STATION: continue
    # NOTE: the "HOURLY_WEATHER_PROPERTIES" is input for API call, whereas DATETIME_STATION is derived data, so does not exist in API
    HOURLY_WEATHER_PROPERTIES += item + "," # add item and comma after item
# NOTE: remove the last comma or everything breaks
HOURLY_WEATHER_PROPERTIES = HOURLY_WEATHER_PROPERTIES[:-1]"""
HOURLY_WEATHER_PROPERTIES=','.join(HourlyWeatherCols)

# mapping-proxy-type of HourlyWeatherCols data-types
HOURLY_WEATHER_DATA_TYPES = MappingProxyType({
    HourlyWeatherCols.station_name: String(30), # name should be string less than 30 chars
    HourlyWeatherCols.climate_identifier: String(10), # this should realistically have less than 10 characters
    HourlyWeatherCols.utc_date: DateTime(timezone=False), # turns out this is a datetime variable???
    HourlyWeatherCols.local_date: DateTime(timezone=False), # turns out this is a datetime variable???
    HourlyWeatherCols.temp: Float,
    HourlyWeatherCols.precip_amount: Float,
    HourlyWeatherCols.relative_humidity: Float,
    HourlyWeatherCols.windchill: Float,
    HourlyWeatherCols.wind_direction: String,
    HourlyWeatherCols.wind_speed: Float,
    HourlyWeatherCols.weather_eng_desc: String, # long-ass description doesn't have limit lol
    # HourlyWeatherCols.datetime_station: String(30), # datetime + climate identifier should be less than 30
})



########################################################################################################################
### section 4: variables related to WatermainBreaks

# class of WatermainBreaksCols column-names - at least ones I'll care about at end
class WatermainBreaksCols(StrEnum):
    break_date = "break_date"
    break_type = "break_type"
    status = "status"
    point = "point"
    x = "x"
    y = "y"

WATERMAIN_BREAKS_DATA_TYPES = MappingProxyType({
    WatermainBreaksCols.break_date: Date,
    WatermainBreaksCols.break_type: String(8),
    # there are 8 "break_type" values:
    #  A - Full Circular B - Split C - Corrosion D - Fitting E - Joint F - Diagonal Crack G - Hole S - Saddle
    # source: https://dev.socrata.com/foundry/data.calgary.ca/dpcu-jr23
    WatermainBreaksCols.status: String(8),
    # "status" values are either ACTIVE or RETIRED
    #"geometry": Geometry('POINT'),
    WatermainBreaksCols.point: Geometry('POINT'),
    WatermainBreaksCols.x: Float,
    WatermainBreaksCols.y: Float,
})


########################################################################################################################
### section 5: variables related to sql-connection

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, Engine

class DBConfig(BaseSettings):
    model_config = SettingsConfigDict(frozen=True, env_file=env_dir)
    postgres_user: str
    postgres_password: SecretStr
    api_key: SecretStr
    api_secret_key: SecretStr
    app_token: SecretStr
    postgres_host: str = "localhost"
    postgres_port: int = 5433 # using 5433 instead of 5432 so I don't get port conflict on local machine from native vs containerized PSQL install
    database_name: str = "calgary_watermains"

DATABASE_CONFIG = DBConfig()


def default_SQL_engine(config: DBConfig = DATABASE_CONFIG) -> Engine:
    url = URL.create(
        drivername="postgresql+psycopg",
        username=config.postgres_user,
        password=config.postgres_password.get_secret_value(),
        host=config.postgres_host,
        port=config.postgres_port,
        database=config.database_name,
    )
    engine = create_engine(url)
    return engine

"""
load_dotenv(env_dir) # get my environment variables

# setup config class
@dataclass(frozen=True) # set up unchanging, constants dataclass for these variables
class Config: # this is a custom class, I could name it whatever I want lol
    postgres_user: str
    postgres_password: str
    api_key: str
    api_secret_key: str
    app_token: str
    postgres_host: str
    postgres_port: int
    database_name: str

# initialize CONFIG variable of type `Config` class
CONFIG = Config(
    postgres_user = os.environ["POSTGRES_USER"], # NOTE: using `os.environ[]` means it'll crash if not found
    postgres_password = os.environ["POSTGRES_PASSWORD"], # `os.getenv()` would just return `None` if not found
    api_key = os.environ["API_KEY"],
    api_secret_key = os.environ["API_SECRET_KEY"],
    app_token = os.environ["APP_TOKEN"],
    postgres_host = "localhost",
    postgres_port = 5433, # using 5433 instead of 5432 so I don't get port conflict on local machine from native vs containerized PSQL install
    database_name = "calgary_watermains",
)

# set default text value for sqlalchemy engine initialization
ENGINE_TEXT = f"postgresql+psycopg://{CONFIG.postgres_user}:{CONFIG.postgres_password}@{CONFIG.postgres_host}:{CONFIG.postgres_port}/{CONFIG.database_name}"


# function to create engine
# doing as function instead of creating actual engine here as constant variable, 
# so errors with connection are found around query time, and so I don't initialize connection
# in scripts importing this module, that don't actually need the connection
# while none of this is relevant for my use-case, it's good to be aware of
def default_SQL_engine(text = ENGINE_TEXT):
    engine = create_engine(text)
    return engine
"""

# NOTE: newer geojsons don't have a CRS, and assume EPSG 4326 is CRS
def set_geojson_crs(gdf):
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf
