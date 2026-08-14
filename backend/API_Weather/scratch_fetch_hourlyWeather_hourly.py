# NOTE: Am I using the silence-command line argument here?





########################################################################################################################
# file name: fetch_hourlyWeather_hourly.py
# author: William Hovdestad
#
# The goal of this script is to retrieve hourly weather data from the following weather station:
# STATION_NAME: CALGARY INT'L CS; CLIMATE_IDENTIFIER: 3031094;
#
# This script will be using "Swob-realtime" from https://api.weather.gc.ca/openapi
#
# This data is raw and unfiltered, but should hopefully give us access to near-realtime-data,
# and this script will be run hourly to retrieve that data.



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
# get path for environment so I can load it later
env_dir = os.path.expanduser(r"~/.config/water_dashboard/.env")



########################################################################################################################
### script-setup 2: library imports
from datetime import date, datetime, time, timedelta # for getting current date
from zoneinfo import ZoneInfo # for time zones
import psycopg # stuff needed to connect with postgis database
import sqlalchemy # stuff needed to connect with postgis database
from sqlalchemy import text # make pylance happy by recognizing this as a keyword lol
from sqlalchemy import create_engine # stuff needed to connect with postgis database
import geopandas as gpd # geospatial library, used for GeoDataFrames
#from shapely.geometry import Point # used to properly format lat/long values for use by GeoPandas
import httpx # used for calling API
#from dateutil.parser import parse # used for properly formatting DATE data into datetime variables
import json # used for handling export of json data

# custom modules!
from backend.helper_error import CustomErrorMessage
from backend.helper_PSQL import default_SQL_engine, set_geojson_crs,\
    STATION_CLIMATE_IDENTIFIER, HOURLY_WEATHER_PROPERTIES, HOURLY_WEATHER_DATA_TYPES, HourlyWeatherCols, DatabaseTables



########################################################################################################################
### script-setup 3: print statement for start of script, and current time
print(f"Script: {__file__} started at {datetime.now()}")



########################################################################################################################
### section 1: grab hourly weather data

# url of API
url = "https://api.weather.gc.ca/collections/swob-realtime/items"

# get proper datetime string to use! first, subtract 1 week from current date
my_time_zone = ZoneInfo("America/Edmonton")
today_date = datetime.now(my_time_zone).date() # gets today's date as datetime so I can include timezone, then make it date
day_minus_seven = today_date - timedelta(days=7) # subtract 7 days from current date
# now, convert it to proper parameter to API call
datetime_param = str(day_minus_seven) + "T00:00:00Z/.."
datetime_param = str(today_date) + "T00:00:00Z/.."
# NOTE: This gives me 12:00am from 7 days ago

print(f"datetime_param: `{datetime_param}`")

# print(HOURLY_WEATHER_PROPERTIES)
#list_HOURLY_WEATHER_PROPERTIES = ",".join(HOURLY_WEATHER_PROPERTIES)
#print(f"list_HOURLY_WEATHER_PROPERTIES:\n{list_HOURLY_WEATHER_PROPERTIES}")

swob_properties_list = [
	#"clim_id-uom",
	"clim_id-value",
	"date_tm-value",
	#"date_tm-uom",
	"dwpt_temp",
	#"dwpt_temp-qa",
	#"dwpt_temp-uom",
	"avg_air_temp_pst1hr",
	#"avg_air_temp_pst1hr-data_flag-code_src",
	#"avg_air_temp_pst1hr-data_flag-uom",
	#"avg_air_temp_pst1hr-data_flag-value",
	#"avg_air_temp_pst1hr-qa",
	#"avg_air_temp_pst1hr-uom",
	#"avg_air_temp_pst1hr_1",
	#"avg_air_temp_pst1hr_1-uom",
	#"avg_air_temp_pst1hr_2",
	#"avg_air_temp_pst1hr_2-uom",
	#"avg_air_temp_pst1hr_3",
	#"avg_air_temp_pst1hr_3-uom",
	#"avg_air_temp_pst2mts",
	#"avg_air_temp_pst2mts-qa",
	#"avg_air_temp_pst2mts-uom",
	"air_temp",
	#"air_temp-qa",
	#"air_temp-uom",
	"air_temp_1",
	#"air_temp_1-uom",
	"air_temp_2",
	#"air_temp_2-uom",
	"air_temp_3",
	#"air_temp_3-uom",
	"pcpn_amt_pst1hr", # NOTE: unit is mm
	#"pcpn_amt_pst1hr-qa",
	#"pcpn_amt_pst1hr-uom",
	"rel_hum", # NOTE: relative humidity in percentage
	#"rel_hum-qa",
	#"rel_hum-uom",
	"max_rel_hum_pst1hr",
	#"max_rel_hum_pst1hr-qa",
	#"max_rel_hum_pst1hr-uom",
	"min_rel_hum_pst1hr",
	#"min_rel_hum_pst1hr-qa",
	#"min_rel_hum_pst1hr-uom",
	"avg_wnd_dir_10m_pst1hr", # NOTE: in degrees, from 0-360
	#"avg_wnd_dir_10m_pst1hr-qa",
	#"avg_wnd_dir_10m_pst1hr-uom",
	"avg_wnd_spd_10m_pst1hr", # NOTE: in km/hr
	#"avg_wnd_spd_10m_pst1hr-qa",
	#"avg_wnd_spd_10m_pst1hr-uom",
	#"prsnt_wx_1",
	#"prsnt_wx_1-qa",
	#"prsnt_wx_1-uom",
	#"prsnt_wx_2",
	#"prsnt_wx_2-qa",
	#"prsnt_wx_2-uom",
	#"prsnt_wx_3",
	#"prsnt_wx_3-qa",
	#"prsnt_wx_3-uom",
    "obs_date_tm",
    #"trans_date_tm-uom",
    #"trans_date_tm-value",
    "wetblb_temp",
]

swob_properties_str_arr = ",".join(swob_properties_list)

# now, setup my parameters variable
params = {
    "limit": 2000, 
    "clim_id-value": STATION_CLIMATE_IDENTIFIER,
    "datetime": datetime_param,
    "sortby": "date_tm-value",
    "properties": swob_properties_str_arr, # filter to specific properties I want from station
}

climateHourly_swobHourly_dict = {
	"CLIMATE_IDENTIFIER": "clim_id-value",
	"UTC_DATE": "temp",
	"LOCAL_DATE": "temp",
	"TEMP": "temp",
	"PRECIP_AMOUNT": "temp",
	"RELATIVE_HUMIDITY": "temp",
	# "WINDCHILL": "temp", # NOTE: Omit, as it's derived measurement not available from raw data
	"WIND_DIRECTION": "temp",
	"WIND_SPEED": "temp",
	# "WEATHER_ENG_DESC": "temp", # NOTE: Omit, as it's derived measurement not available from raw data
}



# make the API call!
response = httpx.get(url, params=params, timeout=30.0) # api call
response.raise_for_status() # make sure status is good
response_output = response.json() # turn results into json

# convert to geojson
gdf = gpd.GeoDataFrame.from_features(response_output["features"]) # this apparently converts to geojson lol

print(os.getcwd())
output_file = Path("backend") / "API_fetch_hourly" / "hourlyWeather_hourly.csv"
#print(output_file)
# gdf.to_csv("hourlyWeather_hourly.csv", index=False)
gdf.to_csv(output_file, index=False)

gdf_cols = gdf.columns.to_list()

max_len = 0
for item in swob_properties_list:
    if len(item) > max_len: max_len = len(item)

if False:
    for item in swob_properties_list:
        if item in gdf_cols: match = "MATCH!"
        else: match = "failure"
        print(f"{item}",end="")
        pad_len = max_len - len(item)
        for i in range(pad_len): print(" ",end="")
        print(f"   {match}")


# print(f"Expected number of cols: {len(swob_properties_list)}; actual: {len(gdf_cols)}")

# print(gdf_cols)
print("\ngdf.tail(1):")
print(gdf.tail(1))