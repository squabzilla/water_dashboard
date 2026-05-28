import os
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

env_dir = os.path.expanduser(r"~/.config/water_dashboard/.env")

load_dotenv(env_dir)

POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
API_KEY = os.getenv("API_KEY")
API_SECRET_KEY = os.getenv("API_SECRET_KEY")
APP_TOKEN = os.getenv("APP_TOKEN")


####################################################################################################
### script-setup 1: library imports
import geopandas as gpd # geospatial library, used for distance calculations
from shapely.geometry import Point # used to properly format lat/long values for use by GeoPandas
import httpx # used for calling API
from dateutil.parser import parse # used for properly formatting DATE data into datetime variables
import json # used for handling export of json data




####################################################################################################
### SAUCE:
# NOTE: IMPORANT: LINK I'M REFERENCING: https://api.weather.gc.ca/openapi?f=html#




####################################################################################################
### section 1: grab all relevant stations

STATION_CLIMATE_IDENTIFIER = "3031094"


# calls the api to get all stations in general calgary area, using the `bbox_from_radius` function
def stations__fetch():

    # min_x, min_y, max_x, max_y = __bbox_from_radius(CALGARY["lat"], CALGARY["long"], RADIUS_KM)

    url = "https://api.weather.gc.ca/collections/climate-stations/items"
    #url = f"https://api.weather.gc.ca/collections/climate-stations/items/{STATION_CLIMATE_IDENTIFIER}"

    """
    params = {
        "bbox": f"{min_x},{min_y},{max_x},{max_y}",
        # NOTE: bbox order is  standard order defined by the 
        # OGC (Open Geospatial Consortium) API spec that Environment Canada's API follows
        # basically, maps to west-boundary, south-boundary, east-boundary, north-boundary
        "PROV_STATE_TERR_CODE": "AB",
        "f": "json", # this line says we want it in json format
        "limit": 200,
        # NOTE: above sets the limits of results;
        # 200 is higher than Environment Canada API's default limit of 10, 
        # but low enough not to upset API
    }"""

    # actual API call - make request, do response.wait-for-update, return the response data
    params = {"CLIMATE_IDENTIFIER": STATION_CLIMATE_IDENTIFIER}
    
    # sends an HTTP GET request to the URL
    # NOTE: everything is stored in response - status code, headers, body
    response = httpx.get(url, params=params)
    #response = httpx.get(url)
    # checks that status code is "200" which means everything is ok
    response.raise_for_status()
    # turn raw response body text into Python dictionary
    all_stations = response.json()
    # grab only items from "features" in said dictionary, 
    # since API returns a GeoJSON `FeatureCollection` that wraps actualy data inside "features" key
    #all_stations = all_stations["features"]
    #all_stations = all_stations["properties"]
    # NOTE: could also do that in one step
    # all_stations = response.json()["features"]
    return all_stations

mystation = stations__fetch()
#print(mystation)

def weather_fetch():
    # url of API
    url = "https://api.weather.gc.ca/collections/climate-daily/items"
    
    # filter properties I want - multi-line because it's a lot of characters lol
    # so I can do multi-line, or one like 200+ character line lol
    prop__ID_time = "CLIMATE_IDENTIFIER,LOCAL_DATE,LOCAL_YEAR,LOCAL_MONTH,LOCAL_DAY"
    prop__temp = "MEAN_TEMPERATURE,MIN_TEMPERATURE,MAX_TEMPERATURE"
    prop__precip = "TOTAL_PRECIPITATION,TOTAL_RAIN,TOTAL_SNOW"
    # NOTE: my prop values are comma separated, BUT LAST ONE DOESN'T HAVE COMMA
    prop__all = prop__ID_time + "," + prop__temp + "," + prop__precip
    params = {
        "CLIMATE_IDENTIFIER": STATION_CLIMATE_IDENTIFIER,
        # according to documentation, this should filter it for dates about 2000-01-01
        "datetime": "2000-01-01T00:00:00Z/..",
        # filter to specific properties I want from station
        "properties": prop__all,
        # arbitrary date filtering, to limit results when testing
        #"LOCAL_MONTH": 5,
        #"LOCAL_DAY": 5,
        # filter amount of items API query gives me
        #"limit": 10,
    }
    # NOTE: number of results from 2000-01Jan-01 to 2026-05May-27:
    # 26*365+31+28+31+30+28 = 9638...plus like 6 leap years...? = 9644
    response = httpx.get(url, params=params)
    response.raise_for_status()
    weather = response.json()
    weather = weather["features"]
    return weather

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

weather = weather_fetch()
#print(weather)
print(f"len weather: {len(weather)}")
"""
for index, item in enumerate(weather):
    json_dict = {
        "CLIMATE_IDENTIFIER": STATION_CLIMATE_IDENTIFIER,
        "LOCAL_DATE": item["properties"]["LOCAL_DATE"],
        "LOCAL_YEAR": item["properties"]["LOCAL_YEAR"],
        "LOCAL_MONTH": item["properties"]["LOCAL_MONTH"],
        "LOCAL_DAY": item["properties"]["LOCAL_DAY"],
        "MEAN_TEMPERATURE": item["properties"]["MEAN_TEMPERATURE"],
        "MIN_TEMPERATURE": item["properties"]["MIN_TEMPERATURE"],
        "MAX_TEMPERATURE": item["properties"]["MAX_TEMPERATURE"],
        "TOTAL_PRECIPITATION": item["properties"]["TOTAL_PRECIPITATION"],
        "TOTAL_RAIN": item["properties"]["TOTAL_RAIN"],
        "TOTAL_SNOW":item["properties"]["TOTAL_SNOW"],


    }
    weather[index] = json_dict"""
#print(weather[0])
#new_dict = []
#for item in weather:
    #new_dict.append(item["properties"]["LOCAL_DATE"])
#new_dict.sort()
#for item in new_dict: print(item)

####################################################################################################
### step 5.2 - save our data as json, to make output data easier to use in the future
with open("backend/weather_data.json", "w") as f:
    json.dump(weather, f, indent=2)