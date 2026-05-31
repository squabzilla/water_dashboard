####################################################################################################
# file name: update_hourly.py
# author: William Hovdestad
#
# The goal of this script is to retrieve hourly temperature data from the following weather station:
# STATION_NAME: CALGARY INT'L CS; CLIMATE_IDENTIFIER: 3031094;
# We only want data for the past week, meaning the most recent 7 * 24 = 168 readings.
#
# Ideally this script will be ran every hour, and update our database with the results.
# However, currently we are just fetching the data, and saving it as GeoJSON.
# Once this step is complete, we'll focus on the logic for bringing it into the database.



####################################################################################################
### script-setup 1: project-root-setup
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

env_dir = os.path.expanduser(r"~/.config/water_dashboard/.env")



####################################################################################################
### script-setup 2: library imports
from dotenv import load_dotenv # used to get environment data so I can login to postgis database
import psycopg # stuff needed to connect with postgis database
import sqlalchemy # stuff needed to connect with postgis database
from sqlalchemy import create_engine # stuff needed to connect with postgis database
import geopandas as gpd # geospatial library, used for distance calculations
#from shapely.geometry import Point # used to properly format lat/long values for use by GeoPandas
import httpx # used for calling API
#from dateutil.parser import parse # used for properly formatting DATE data into datetime variables
import json # used for handling export of json data

# custom library!
from backend.progress_bar import update_progress_bar



####################################################################################################
### script-setup 3: global variables

load_dotenv(env_dir) # get my environment variables

# set my environment variables as global variables
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
API_KEY = os.getenv("API_KEY")
API_SECRET_KEY = os.getenv("API_SECRET_KEY")
APP_TOKEN = os.getenv("APP_TOKEN")

STATION_CLIMATE_IDENTIFIER = "3031094"
# this is the weather station that has all the data in the correct time-range for this project

### ALSO: LINK I'M USING:
# NOTE: IMPORANT: LINK I'M REFERENCING: https://api.weather.gc.ca/openapi?f=html#



####################################################################################################
### section 1: function that grabs all data for relevant station

def station__fetch():

    # min_x, min_y, max_x, max_y = __bbox_from_radius(CALGARY["lat"], CALGARY["long"], RADIUS_KM)

    url = "https://api.weather.gc.ca/collections/climate-stations/items"
    #url = f"https://api.weather.gc.ca/collections/climate-stations/items/{STATION_CLIMATE_IDENTIFIER}"

    # actual API call - make request, do response.wait-for-update, return the response data
    params = {"CLIMATE_IDENTIFIER": STATION_CLIMATE_IDENTIFIER}
    
    # sends an HTTP GET request to the URL
    # NOTE: everything is stored in response - status code, headers, body
    response = httpx.get(url, params=params)
    #response = httpx.get(url)
    # checks that status code is "200" which means everything is ok
    response.raise_for_status()
    # turn raw response body text into Python dictionary
    response_output = response.json()
    # grab only items from "features" in said dictionary, 
    # since API returns a GeoJSON `FeatureCollection` that wraps actualy data inside "features" key,
    # and the data I ACTUALLY care about is inside "properties" inside of "features"
    # station = response_output["features"]
    # NOTE: could also do that in one step
    # station = response.json()["features"]["properties"]

    # turn into geodataframe so I can save it to postgis
    gdf = gpd.GeoDataFrame.from_features(response_output["features"]) # this apparently converts to geojson lol
    # NOTE: newer geojsons don't have a CRS, and assume EPSG 4326 is CRS
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")

    # return it
    return gdf



####################################################################################################
### section 1: let's actually fetch the weather data for the relevant station lol

def weather_fetch():
    # url of API
    url = "https://api.weather.gc.ca/collections/climate-daily/items"

    # set variables to help use pagination to get all data
    #offset = 0
    limit = 100
    years = range(2000,2027) # years from 2000 thru 2026 (stops at 2027)
    months = range(1,13) # months from 1 thru 12 (stops at 13)
    all_data = []
    total_records = 1000 # arbitary total records thats higher then limit, will properly set later
    
    # filter properties I want - multi-line because it's a lot of characters lol
    # so I can do multi-line, or one like 200+ character line lol
    prop__ID_time = "CLIMATE_IDENTIFIER,LOCAL_DATE,LOCAL_YEAR,LOCAL_MONTH,LOCAL_DAY"
    prop__temp = "MEAN_TEMPERATURE,MIN_TEMPERATURE,MAX_TEMPERATURE"
    prop__precip = "TOTAL_PRECIPITATION,TOTAL_RAIN,TOTAL_SNOW"
    # NOTE: my prop values are comma separated, BUT LAST ONE DOESN'T HAVE COMMA
    prop__all = prop__ID_time + "," + prop__temp + "," + prop__precip

    # actually put parameters together
    params = {
        #"offset": offset,
        "limit": limit,
        "CLIMATE_IDENTIFIER": STATION_CLIMATE_IDENTIFIER,
        # according to documentation, this should filter it for dates about 2000-01-01
        "datetime": "2000-01-01T00:00:00Z/..",
        # filter to specific properties I want from station
        "properties": prop__all,
        "sortby": "LOCAL_DATE",
        # arbitrary date filtering, to limit results when testing
        #"LOCAL_MONTH": 5,
        #"LOCAL_DAY": 5,
        # filter amount of items API query gives me
        #"limit": 10,
    }
    # NOTE: number of results from 2000-01Jan-01 to 2026-05May-27:
    # 26*365+31+28+31+30+28 = 9638...plus like 6 leap years...? = 9644

    # let's run a quick query to determine total number of items
    params["limit"] = 1 # set limit to 1 for our quick call
    response = httpx.get(url, params=params) # api call
    params["limit"] = 100 # reset limit back to what it should be
    response.raise_for_status() # make sure status is good
    response_output = response.json() # turn results into json
    response_expected = response_output["numberMatched"] # get expected number of responses
    
    # loop thru results with pagination!
    # fuck everything, this is being dumb, I'm just gonna loop thru year/month combos
    # because I know that'll actually fucking work

    # setup progress bar for it tho
    total_iterations = len(years) * len(months)
    prefix = "Fetching historical weather data"
    count = 0
    update_progress_bar(iteration=count, total=total_iterations, prefix=prefix)

    for year in years:
        for month in months:
            
            params["LOCAL_YEAR"] = year
            params["LOCAL_MONTH"] = month

            response = httpx.get(url, params=params) # api call
            response.raise_for_status() # make sure status is good
            response_output = response.json() # turn results into json
            
            data = response_output.get("features",[]) # get items from "features" key, returns empty list (square-brackets) is key missing
            all_data.extend(data) # add `data` to `all_data`, extend works better than append for REASONS

            # update progress bar
            count += 1
            update_progress_bar(iteration=count, total=total_iterations, prefix=prefix)
    print("") # newline print after progress bar is done

    # lets confirm our results match...
    print(f"Expected responses: {response_expected}; actual: {len(all_data)}")

    # gdf = gpd.GeoDataFrame.from_features(response_output["features"]) # this apparently converts to geojson lol
    gdf = gpd.GeoDataFrame.from_features(all_data) # I already selected the "features" key while looping thru data
    # NOTE: newer geojsons don't have a CRS, and assume EPSG 4326 is CRS
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf

# NOTE: for handling high amount of data:
# I could just filter it by every relevant year, and loop through the years I want
# maybe add in a delay between loop iterations
# this way I'd only be grabbing one year at a time, each individual year would be small enough to handle

# NOTE: Historical rainfall data:
# I'd be better off with a Bash script using say WGET to download the (hopefully compressed) CSV archive
# and then writing Python code to process that archive
# rather than using an API call
# tbh, there's a way to write Python code to download an item from a download link too
# I did that with historical population data for the NZEST project




####################################################################################################
### section 2 - actually save our data to use later

# first, call function to get weather data lol - probably doesn't need to be function but whatever
gdf_station = station__fetch()
gdf_weather = weather_fetch()
#station_path = Path(PROJECT_ROOT) / "backend" / "data" / "CALGARY_INTL_CS_station.geojson"
#weather_path = Path(PROJECT_ROOT) / "backend" / "data" / "CALGARY_INTL_CS_climate.geojson"

# setup engine to connect to postgis
# NOTE: `POSTGRES_DB=calgary_watermains` in podman stuff, so assume 'your_database' = 'calgary_watermains'
database_name = 'calgary_watermains'

engine_text = f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@localhost:5433/{database_name}"
engine = create_engine(engine_text)

gdf_station.to_postgis("CALGARY_INTL_CS_station", engine, if_exists="replace", index=False)
gdf_weather.to_postgis("CALGARY_INTL_CS_weather", engine, if_exists="replace", index=False)

print(f"Added weather-station-data and climate-data for weather station {STATION_CLIMATE_IDENTIFIER}")