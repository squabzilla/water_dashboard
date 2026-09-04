"""
file name: weatherData_updateHourlyRecords_runHourly.py
author: William Hovdestad

This script is designed to call the `fetch_MSC_GeoMet_weather` from the `weather_APIlogic.py` file,
in order to update the hourly-weather values in the PostGIS database; this script is intended to be run hourly.

It grabs the `swob-realtime` data from the Canada weather API
link: https://api.weather.gc.ca/openapi?f=html#/swob-realtime

Because the `climate-hourly` data is only updated once a day, and has a few days between weather-station-recordings
and release of data (due to an internal QA/QC process), it does not contain data of the current day, let alone hour.
Thus, we grab the `swob-realtime` data for the most up-to-date readings
- which, notably, have NOT been through any sort of QA/QC process.

It will grab the last X hours of data, with X specified by command-line argument. 
The default will be 6 hours, but during backfill we will grab 72.
Why? Because the `swob-realtime` data collects records every minute.
We will want to filter our records to records as close to on-the-hour as possible,
but our API call will still fetch 60 readings per hour.

Another note about this data is the data is only available in UTC time, not local time.

This data is designed to be used in tandem with Water-Main-Breaks data from the City-of-Calgary,
whose data can be found here: https://data.calgary.ca/Environment/Water-Main-Breaks/dpcu-jr23/data_preview
so this data fetches records starting at 1956-01-01 to match the Water-Main-Break records.
"""



########################################################################################################################
### script-setup 1: project-root-setup
import os
import sys
from pathlib import Path

# gets file-path, (hopefully) resolves relative path issues, gets grand-parent folder
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# sets working directory to project root - there may be redundancy here but oh well lol
os.chdir(PROJECT_ROOT)
# Ensure repository code is importable when this wrapper is run directly.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))



########################################################################################################################
### script-setup 2: library imports
import argparse # used for adding command line arguments to script
from datetime import date, datetime, time, timedelta, timezone # for getting current date
import psycopg # stuff needed to connect with postgis database
import sqlalchemy # stuff needed to connect with postgis database
from sqlalchemy import text # make pylance happy by recognizing this as a keyword lol
from sqlalchemy import create_engine # stuff needed to connect with postgis database
import pandas as pd # pandas nonsense
import geopandas as gpd # geospatial library, used for GeoDataFrames
#from shapely.geometry import Point # used to properly format lat/long values for use by GeoPandas
import httpx # used for calling API
#from dateutil.parser import parse # used for properly formatting DATE data into datetime variables
import json # used for handling export of json data
import logging # want to log data

# custom modules!
from backend.helper.helper_timezones import AB_TIME, UTC_TIME
#from backend.helper_error import CustomErrorMessage
#from backend.helper_PSQL import default_SQL_engine, set_geojson_crs, STATION_NAME, \
    #STATION_CLIMATE_IDENTIFIER, HOURLY_WEATHER_PROPERTIES, HOURLY_WEATHER_DATA_TYPES, HourlyWeatherCols, DatabaseTables
from backend.helper.helper_SQL_tables import HOURLY_WEATHER_PROPERTIES, HOURLY_WEATHER_DATA_TYPES, \
    HourlyWeatherCols, DatabaseTables, STN_IDS_STR_CSV_LIST, SWOBWeatherCols, SWOB_PROPERTIES,\
    HOURLY_WEATHER_UNIQUE_DATETIME_CONSTRAINT, HOURLY_WEATHER_STAGING_UNIQUE_DATETIME_CONSTRAINT, HOURLY_SWOB_CONVERSION
from backend.API.weather_helper_API import fetch_weather_pages
from backend.API.weather_helper_filterStationPriority import filter_stations_by_priority
from backend.helper.helper_PSQL_config import default_SQL_engine
from backend.helper.helper_DB_update import add_new_records_to_table
from backend.helper.helper_set_geojson_crs import set_geojson_crs
from backend.helper.helper_API_errors import DataUniquenessConstraintViolation




########################################################################################################################
### script-setup 3: logging config
logfile = Path(PROJECT_ROOT) / "backend" / "API" / "log_files" / "weatherData_updateHourlyRecords_runDaily.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[ # handles output stuff
        logging.FileHandler(logfile), # handles output file
        logging.StreamHandler() # writes log to a "stream" which by default is terminal/console
        ],
    # NOTE: logging levels: affects labelling and filtering when looking through errors
    # like remember how I'd tell Python "idgaf about that warning just stop telling me"
    # but also not wanting to eliminate like SERIOUS errors?
    # that's what the logging levels let us do
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING) # STOP LOGGING EVERY API CALL DAMNIT
# LOGGING ORDER:
# debug
# info
# warning
# error
# critical



########################################################################################################################
### script-setup 4: setup command line arguments for script
#

parser = argparse.ArgumentParser(description=__doc__)

DEFAULT_LOOKBACK_HOURS = 6

# We have a command-line argument for how many hours we look back
parser.add_argument(
    "-hrs", "--hours_back", # NOTE: `-h` is reserved for "help" lol
    type=int,
    default=DEFAULT_LOOKBACK_HOURS,
    help=f"Lookback window in hours (default: {DEFAULT_LOOKBACK_HOURS}; use 48 for a fresh-deployment backfill)",
)
args = parser.parse_args()

#print(f"args.hours-back: {args.hours_back}")
#print(f"doc: {__doc__}")



########################################################################################################################
### section 1: grab hourly weather data

def _fetch_swob_data(hours_back:int = args.hours_back) -> gpd.GeoDataFrame:
    # url of API
    url = "https://api.weather.gc.ca/collections/swob-realtime/items"

    # easier variable for how many hows back we're looking
    

    # get start time in UTC
    utc_current_time = datetime.now(UTC_TIME)

    # round time time to current hour
    # NOTE: when filtering it to hourly results, we set start time rounded down to nearest hour from earliest time
    # if earliest time is 2:35, it rounds down to 2pm, then next it looks for a record within 5 minutes of 2pm
    # so we round down the time so we don't run into weird errors lol
    utc_current_time = utc_current_time.replace(minute=0, second=0, microsecond=0)
    # NOTE: our rounding here makes us want to run this just slightly past the hour lol

    # get our start time of X hours back
    utc_start_time = utc_current_time - timedelta(hours=hours_back)

    # get standard li

    # set parameters for API query
    params = {
        "limit":1000, # script paginates by default, so default limit is fine
        "filter": f'"properties.{SWOBWeatherCols.swob_climate_identifier}" IN ({STN_IDS_STR_CSV_LIST})',
        # NOTE: gotta throw double-quotes IN THE STRONG around the properties section because of the dash character...
        #"clim_id-value": "3031094",
        #SWOBWeatherCols.swob_climate_identifier:  "3031094",
        "datetime": f"{utc_start_time.strftime('%Y-%m-%dT%H:%M:%SZ')}/{utc_current_time.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "sortby": "date_tm-value",
        "properties": SWOB_PROPERTIES,
    }
    job_title = f"SWOB-realtime-last-{hours_back}hrs"
    # print(f"datetime values:\n{params["datetime"]}")
    # print(f"station name: `{STATION_NAME}`")
    gdf = fetch_weather_pages(start_url=url, params=params, job_title=job_title)

    gdf = filter_stations_by_priority(gdf, station_id_col=SWOBWeatherCols.swob_climate_identifier,
                                      datetime_col=SWOBWeatherCols.swob_utc_date)
    # NOTE: dates should be unique now, so let's check that
    if not gdf[SWOBWeatherCols.swob_utc_date].is_unique:
        err_mss = f"ERROR: dates not unique on hourly-update of SWOB-realtime from UTC:{utc_start_time} to UTC:{utc_current_time}"
        raise DataUniquenessConstraintViolation(err_mss)
    return gdf



########################################################################################################################
### section 2: function to format SWOB GDF like hourly-weather GDF
def _convert_SWOBFormat_to_HourlyFormat(gdf:gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    # get my key for renaming columns
    conversion_dict = dict(HOURLY_SWOB_CONVERSION)
    #print(f"conversion dict:\n{conversion_dict}")
    # rename the columns
    gdf_hourly = gdf.rename(columns=conversion_dict)
    # add local-datetime-column
    # NOTE: maybe need `from datetime import datetime` and `from zoneinfo import ZoneInfo`
    gdf_hourly[HourlyWeatherCols.hwc_utc_date] = pd.to_datetime(gdf_hourly[HourlyWeatherCols.hwc_utc_date], utc=True)
    # add local date column
    gdf_hourly[HourlyWeatherCols.hwc_local_date] = gdf_hourly[HourlyWeatherCols.hwc_utc_date].dt.tz_convert("America/Edmonton")
    # add local year column
    gdf_hourly[HourlyWeatherCols.hwc_local_year] = gdf_hourly[HourlyWeatherCols.hwc_local_date].dt.year

    # get list for column order
    col_order_list = [col.value for col in HourlyWeatherCols]
    
    # don't forget to include geometry column at start!
    col_order_list.insert(0, 'geometry')
    # I hate how lists have in-place methods, but 99% of what I do is pandas where you gotta do:
    # 'df = df.method()', but in lists that syntax actually doesn't work???

    # re-organize the columns
    gdf_hourly = gdf_hourly.reindex(columns=col_order_list)

    # return it
    return gdf_hourly



########################################################################################################################
### section 3: filter results to just on-the-hours results....
def _filter_hourly_records(gdf:gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    # TODO: FINISHI THIS LOL
    #pass
    og_gdf = gdf.copy()
    working_gdf = gdf.copy()
    print(f"Length of working gdf: {len(working_gdf)}")
    # NOTE: remember it's been converted to proper hourly-format by now
    
    # sort values by datetime, then make datetime the column
    gdf = gdf.sort_values(HourlyWeatherCols.hwc_local_date).set_index(HourlyWeatherCols.hwc_local_date)

    # create an index of hourly values
    hourly_index = pd.date_range(gdf.index.min().floor("h"), gdf.index.max().ceil("h"), freq="h")
    # print(f"hourly_index:\n{hourly_index}\n")
    # for col in working_gdf.columns: print(f"{col} head:\n{working_gdf[col].head(1)}\n")

    # build a new dataframe by re-indexing the original one on the hourly index
    new_gdf = gdf.reindex(hourly_index, method="nearest", tolerance=pd.Timedelta(minutes=5))

    # rename the index to the datetime lol
    new_gdf = new_gdf.rename(columns={"index": HourlyWeatherCols.hwc_local_date})
    #print(f"new gdf:\n{new_gdf}")

    # return it
    return new_gdf


########################################################################################################################
### section 4 - define main function to call local helper

def main() -> None:
    """
    gdf = _fetch_swob_data()
    engine = default_SQL_engine()
    main_table_name = DatabaseTables.weather_hourly
    staging_table_name = DatabaseTables.weather_hourly_staging
    unique_column = HourlyWeatherCols.hwc_local_date
    staging_table_unique_constraint_name = HOURLY_WEATHER_STAGING_UNIQUE_DATETIME_CONSTRAINT
    dtype_dictionary = dict(HOURLY_WEATHER_DATA_TYPES)

    add_new_records_to_table(gdf=gdf, engine=engine, main_table_name=main_table_name,
                                staging_table_name=staging_table_name, unique_column=unique_column,
                                staging_table_unique_constraint_name=staging_table_unique_constraint_name,
                                dtype_dictionary=dtype_dictionary, overwrite=True) # still want this one to overwrite!
    #
    """
    #print(f"UTC NOW: {datetime.now(UTC_TIME)}")
    gdf = _fetch_swob_data(3)
    gdf = _convert_SWOBFormat_to_HourlyFormat(gdf)
    gdf = _filter_hourly_records(gdf)

    # add records to table
    # NOTE: should be the same as regular update-hourly-records now, because of `_convert_SWOBFormat_to_HourlyFormat`
    # NOTE: EXCEPT WE DON'T WANT TO OVERWRITE SHIT
    engine = default_SQL_engine()
    main_table_name = DatabaseTables.weather_hourly
    staging_table_name = DatabaseTables.weather_hourly_staging
    unique_column = HourlyWeatherCols.hwc_local_date
    staging_table_unique_constraint_name = HOURLY_WEATHER_STAGING_UNIQUE_DATETIME_CONSTRAINT
    dtype_dictionary = dict(HOURLY_WEATHER_DATA_TYPES)
    add_new_records_to_table(gdf=gdf, engine=engine, main_table_name=main_table_name,
                                staging_table_name=staging_table_name, unique_column=unique_column,
                                staging_table_unique_constraint_name=staging_table_unique_constraint_name,
                                dtype_dictionary=dtype_dictionary, overwrite=False) # NOTE: DO NOT OVERWRITE WITH SWOB RECORDS



########################################################################################################################
### section 5:  call main
# this function will run by itself if this script is called, including the start & end time pieces
if __name__ == "__main__":
    logger.info(f"Script: {__file__} started at {datetime.now(AB_TIME)}")# print statement for start of script, and current time
    main()
    logger.info(f"Script: {__file__} completed at {datetime.now(AB_TIME)}")# print statement for end of script, and current time