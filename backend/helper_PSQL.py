########################################################################################################################
# file name: helper_PSQL.py
# author: William Hovdestad
#
# The purpose of this file is for standardized "constant" variables for my PSQL postgis table names.
# That way, I can ensure consistency in the use of table names across all the various Python files.



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
from dotenv import load_dotenv # used for loading environment variables
from dataclasses import dataclass # for making immutable classes, used for my CONFIG variables (user, login, API, etc.)
from types import MappingProxyType # for making immutable dicts, used for making immutable dict of table names
import psycopg # stuff needed to connect with postgis database
import sqlalchemy # stuff needed to connect with postgis database
from sqlalchemy import text # make pylance happy by recognizing this as a keyword lol
from sqlalchemy import create_engine # stuff needed to connect with postgis database
from sqlalchemy import String, Date, SmallInteger, Float
import geopandas as gpd # geospatial library, used for GeoDataFrames

# setup environment directory which contains the `.env` file
env_dir = os.path.expanduser(r"~/.config/water_dashboard/.env")



########################################################################################################################
### section 1: global variables

# station I'm using for weather data, might as well make it global variable
STATION_CLIMATE_IDENTIFIER = "3031094"
# this is the weather station that has all the data in the correct time-range for this project

# long string of weather properties I want
DAILY_WEATHER_PROPERTIES =\
"CLIMATE_IDENTIFIER,LOCAL_DATE,LOCAL_YEAR,LOCAL_MONTH,LOCAL_DAY,MEAN_TEMPERATURE,MIN_TEMPERATURE,MAX_TEMPERATURE,TOTAL_PRECIPITATION,TOTAL_RAIN,TOTAL_SNOW"
# NOTE: my list of WEATHER_PROPERTIES are comma separated, BUT LAST ONE DOESN'T HAVE COMMA

# okay, I need to define the types for these; 
# this site: https://api.weather.gc.ca/openapi?f=html#/climate-daily/getClimate-dailySchema 
# gets me the info, I just need to make a dict - or mapping-proxy-type so its immutable
DAILY_CLIMATE_DATA_TYPES = MappingProxyType({
    "CLIMATE_IDENTIFIER": String,
    "LOCAL_DATE": Date,
    "LOCAL_YEAR": SmallInteger,
    "LOCAL_MONTH": SmallInteger,
    "LOCAL_DAY": SmallInteger,
    "MEAN_TEMPERATURE": Float,
    "MIN_TEMPERATURE": Float,
    "MAX_TEMPERATURE": Float,
    "TOTAL_PRECIPITATION": Float,
    "TOTAL_RAIN": Float,
    "TOTAL_SNOW": Float,
})
# NOTE: I could generate this from API call, but it's probably easier to do it manually
# I'm not querying enough different APIs that have a separate schema API to be worth automating it
# I just need to set dtypes when I need to make sure that newly-queried hourly/daily data matches existing historical data
# especially if there's no data for that period, so GeoPandas arbitrarily decides what to assign a column with NULL

HOURLY_WEATHER_PROPERTIES =\
"CLIMATE_IDENTIFIER,UTC_DATE,LOCAL_DATE,LOCAL_YEAR,LOCAL_MONTH,LOCAL_DAY,LOCAL_HOUR,TEMP,PRECIP_AMOUNT,RELATIVE_HUMIDITY,WINDCHILL,WIND_DIRECTION,WIND_SPEED,WEATHER_ENG_DESC"

HOURLY_CLIMATE_DATA_TYPES = MappingProxyType({
    "CLIMATE_IDENTIFIER": String,
    "UTC_DATE": Date,
    "LOCAL_DATE": Date,
    "LOCAL_YEAR": SmallInteger,
    "LOCAL_MONTH": SmallInteger,
    "LOCAL_DAY": SmallInteger,
    "LOCAL_HOUR": SmallInteger,
    "TEMP": Float,
    "PRECIP_AMOUNT": Float,
    "RELATIVE_HUMIDITY": Float,
    "WINDCHILL": Float,
    "WIND_DIRECTION": String,
    "WIND_SPEED": Float,
    "WEATHER_ENG_DESC": String,
})

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

# setup DatabaseTables class, initialize default variables so its less work to add more later
@dataclass(frozen=True) # set up unchanging, constants dataclass for these variables
class DatabaseTables:
    weather_data_daily: str = "weather_data_daily"
    weather_data_daily_staging: str = "weather_data_staging"
    weather_data_hourly: str = "weather_data_hourly"
    weather_data_hourly_staging: str = "weather_data_hourly_staging"
    weather_stations: str = "weather_stations"
# initialize TABLE_NAMES variable of type `DatabaseTables` class
TABLE_NAMES = DatabaseTables()

# setup DatabaseCols class, initialize default variables so its less work to add more later
# note that I'm only putting columns in here if I need to use those columns in code somewhere
class DatabaseCols:
    datetime_station: str = "DATETIME_STATION"
# initialize TABLE_COLS variable of type `DatabaseCols` class
TABLE_COLS = DatabaseCols()


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

# NOTE: newer geojsons don't have a CRS, and assume EPSG 4326 is CRS
def set_geojson_crs(gdf):
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf