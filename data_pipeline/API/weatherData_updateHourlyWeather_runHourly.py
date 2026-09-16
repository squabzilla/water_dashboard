"""
file name: weatherData_updateHourlyRecords_runHourly.py
author: William Hovdestad

This script is designed to call the `fetch_MSC_GeoMet_weather` from the `weather_APIlogic.py` file,
in order to update the hourly-weather values in the PostGIS database; this script is intended to be run hourly.

Command line usage: `uv run weatherData_updateHourlyRecords_runHourly.py -hrs <int>`

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

# gets file-path, (hopefully) resolves relative path issues, gets great grand-parent folder
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# sets working directory to project root - there may be redundancy here but oh well lol
os.chdir(PROJECT_ROOT)
# Ensure repository code is importable when this wrapper is run directly.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))



########################################################################################################################
### script-setup 2: library imports
import argparse # used for adding command line arguments to script
from datetime import datetime, timedelta # for getting date-time stuff
import psycopg # stuff needed to connect with postgis database
import sqlalchemy # stuff needed to connect with postgis database
import pandas as pd # pandas nonsense
import geopandas as gpd # geospatial library, used for GeoDataFrames
import httpx # used for calling API
import json # used for handling export of json data
import logging # want to log data

# custom modules!
from data_pipeline.helper.helper_logging_config import setup_logging
from data_pipeline.helper.helper_timezones import AB_TIME, UTC_TIME
from data_pipeline.helper.helper_SQL_tables import HOURLY_WEATHER_DATA_TYPES, HourlyWeatherCols, DatabaseTables, SWOBWeatherCols,\
    STN_IDS_STR_CSV_LIST, SWOB_PROPERTIES, HOURLY_WEATHER_STAGING_UNIQUE_DATETIME_CONSTRAINT, HOURLY_SWOB_CONVERSION
from data_pipeline.API.weather_helper_API import fetch_weather_pages, filter_stations_by_priority
from data_pipeline.helper.helper_PSQL_config import default_SQL_engine
from data_pipeline.helper.helper_DB_update import add_new_records_to_table
from data_pipeline.helper.helper_API_errors import DataUniquenessConstraintViolation



########################################################################################################################
### script-setup 3: logging config - now with a helper function!
logger = logging.getLogger(__name__)



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



########################################################################################################################
### section 1: grab hourly weather data

def _fetch_swob_data(hours_back:int = args.hours_back) -> gpd.GeoDataFrame:
    # let's just raise some errors if data not good
    if not type(hours_back) is int:
        msg = f"Error: TypeError: Expecting an integer; got {hours_back} which is a {type(hours_back)}."
        raise TypeError(msg)
    if hours_back not in range(0,100):
        msg = f"Error: ValueError: valid hours_back are from 0 to 99 (inclusive). {hours_back} not within that range."
        raise ValueError(msg)

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

    # set parameters for API query
    params = {
        "limit":1000, # script paginates by default, so default limit is fine
        "filter": f'"properties.{SWOBWeatherCols.swob_climate_identifier}" IN ({STN_IDS_STR_CSV_LIST})',
        # NOTE: gotta throw double-quotes IN THE STRONG around the properties section because of the dash character...
        "datetime": f"{utc_start_time.strftime('%Y-%m-%dT%H:%M:%SZ')}/{utc_current_time.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "sortby": "date_tm-value",
        "properties": SWOB_PROPERTIES,
    }
    job_title = f"SWOB-realtime-last-{hours_back}hrs"

    gdf = fetch_weather_pages(start_url=url, params=params, job_title=job_title)

    gdf = filter_stations_by_priority(gdf, station_id_col=SWOBWeatherCols.swob_climate_identifier,
                                      datetime_col=SWOBWeatherCols.swob_utc_date)

    # for some gods-forsaken reason, the SWOB-realtime data API includes the Z dimension...
    gdf.geometry = gdf.geometry.force_2d()

    # NOTE: dates should be unique now, so let's check that
    if not gdf[SWOBWeatherCols.swob_utc_date].is_unique:
        err_mss = f"Error: DataUniquenessConstraintViolation: SWOB-realtime data datetimes not unique from UTC:{utc_start_time} to UTC:{utc_current_time}"
        logger.error(err_mss)
        raise DataUniquenessConstraintViolation(err_mss)

    return gdf



########################################################################################################################
### section 2: function to re-order columns to match hourly-weather

def _reorder_cols(gdf:gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    # get list for column order
    col_order_list = [col.value for col in HourlyWeatherCols]
    
    # don't forget to include geometry column at start!
    col_order_list.insert(0, 'geometry')
    # I hate how lists have in-place methods, but 99% of what I do is pandas, where you gotta do:
    # 'df = df.method()', but in lists that syntax actually doesn't work???
    # GAHHHHHHHHHHHHH

    # re-organize the columns
    gdf = gdf.reindex(columns=col_order_list)
    return gdf



########################################################################################################################
### section 3: function to format SWOB GDF like hourly-weather GDF

def _convert_SWOBFormat_to_HourlyFormat(gdf:gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    # get my key for renaming columns
    conversion_dict = dict(HOURLY_SWOB_CONVERSION)

    # rename the columns
    gdf_hourly = gdf.rename(columns=conversion_dict)

    # add local-datetime-column
    gdf_hourly[HourlyWeatherCols.hwc_utc_date] = pd.to_datetime(gdf_hourly[HourlyWeatherCols.hwc_utc_date], utc=True)

    # add local date column
    gdf_hourly[HourlyWeatherCols.hwc_local_date] = gdf_hourly[HourlyWeatherCols.hwc_utc_date].dt.tz_convert("America/Edmonton")

    # add local year column
    gdf_hourly[HourlyWeatherCols.hwc_local_year] = gdf_hourly[HourlyWeatherCols.hwc_local_date].dt.year.astype('Int64')
    # making it the 'Int64' dtype means the d-type supports null-values, so it won't upcast to float if there's a null value
    # because if it upcasts to float, the year value becomes `2026.0` instead of `2026` and later code that expects an integer breaks
    # because it's not an integer
    # also not that I need to use specifically the `Int64` dtype (capital I), not `int64` (lowercase i) because pandas is dumb, dumb legacy issues I guess

    # re-order columns
    gdf_hourly = _reorder_cols(gdf_hourly)

    # return it
    return gdf_hourly



########################################################################################################################
### section 4: filter results to just on-the-hours results....
def _filter_hourly_records(gdf:gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    # NOTE: remember gdf has been converted to proper hourly-format by now
    
    # sort values by datetime, then make datetime the index-column
    gdf = gdf.sort_values(HourlyWeatherCols.hwc_local_date).set_index(HourlyWeatherCols.hwc_local_date)

    # now create an idnex of hourly values (pretty sure this is a "pandas series" object now)
    hourly_index = pd.date_range(gdf.index.min().floor("h"), gdf.index.max().ceil("h"), freq="h")

    # build a new dataframe by re-indexing the original one on the newly-created hourly index
    new_gdf = gdf.reindex(hourly_index, method="nearest", tolerance=pd.Timedelta(minutes=5))
    # let's get rid of any empty rows (where ALL points are empty, does not include index in this)
    new_gdf = new_gdf.dropna(how='all')
    # also, reset the index when we're done
    new_gdf = new_gdf.reset_index()

    # rename the index to the datetime
    new_gdf = new_gdf.rename(columns={"index": HourlyWeatherCols.hwc_local_date})
    
    # reorder the columns AGAIN, since setting/resetting the index borked it
    new_gdf = _reorder_cols(new_gdf)

    # NOTE: dates should be unique now, so let's check that
    if not new_gdf[HourlyWeatherCols.hwc_local_date].is_unique:
        #msg = f"Error: DataUniquenessConstraintViolation: dates not unique on daily-update of daily-weather-values on day: {datetime.now().date()}"
        msg = f"Error: DataUniquenessConstraintViolation: filtered-hourly-records not unique; suggests algorithm error in `_filter_hourly_records` function."
        logger.error(msg)
        raise DataUniquenessConstraintViolation()

    # return it
    return new_gdf


########################################################################################################################
### section 5 - define main function to call local helpers

def _update_hourly_weather_run_hourly() -> None:
    gdf = _fetch_swob_data() # let this be the default value now lol
    gdf = _convert_SWOBFormat_to_HourlyFormat(gdf)
    # NOTE: remember that this adds time-zone data, in order to derive "LOCAL_DATE" column from "UTC_DATE" column
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
### section 5: setup and call main

def main() -> None:
    # setup logging in main
    logfile = Path(PROJECT_ROOT) / "data_pipeline" / "API" / "log_files" / f"{Path(__file__).stem}.log" # base log name on file name
    setup_logging(logfile) # NOTE: logging config already adds current time

    # log start
    logger.info(f"Script: {__file__} started.")# print statement for start of script, and current time

    # try fetch_all_layers, log error if fails
    try:
        _update_hourly_weather_run_hourly()
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