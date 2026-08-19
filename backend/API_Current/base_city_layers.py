########################################################################################################################
# file name: fetch_city_shapes.py
# author: William Hovdestad
#
# The goal of this script is to retrieve "static" city shapes for my water main break dashboard:
# 1.    public water main
# 2.    city boundary
# 3.    community boundaries
# 4.    hydrology



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
#import argparse # used for adding command line arguments to script
from datetime import datetime # used to get current time
import psycopg # stuff needed to connect with postgis database
import pandas as pd # dataframe library, for when I'm not ready to make the DataFrame all Geo quite yet
import geopandas as gpd # geospatial library, used for GeoDataFrames
import httpx # used for calling API
import json # used for handling export of json data

# custom modules!
from backend.helper.helper_progress_bar import update_progress_bar
from backend.helper.helper_error import CustomErrorMessage
from backend.helper.helper_PSQL_config import default_SQL_engine, DATABASE_CONFIG



########################################################################################################################
### script-setup 3: print statement for start of script, and current time
print(f"Script: {__file__} started at {datetime.now()}")



########################################################################################################################
### set up variables for API calls

#### set API variables 
CALGARY_APP_TOKEN = DATABASE_CONFIG.app_token
CALGARY_API_KEY = DATABASE_CONFIG.api_key               # Key ID -> Basic Auth username -> api-key
CALGARY_API_SECRET = DATABASE_CONFIG.api_secret_key     # Key Secret -> Basic Auth password -> api-secret-key

#### setup dictionaries of name/url variables
NAME = "name"
LINK = "link"

PublicWaterMain_dict = {
    NAME: "PublicWaterMain_Pipes", # NOTE: naming this one "..._Pipes" to distinguish more easily from BREAKS
    LINK: """https://data.calgary.ca/api/v3/views/w6h9-w33i/query.geojson"""
}
Hydrology_dict = {
    NAME: "Hydrology",
    LINK: """https://data.calgary.ca/api/v3/views/47bt-eefd/query.geojson"""
}
CommunityDistrictBoundaries_dict = {
    NAME: "CommunityDistrictBoundaries",
    LINK: """https://data.calgary.ca/api/v3/views/surr-xmvs/query.geojson"""
}
CityBoundary_dict = {
    NAME: "CityBoundary",
    LINK: """https://data.calgary.ca/api/v3/views/erra-cqp9/query.geojson"""
}


#### put all dictionaries into list
city_layers = [
    PublicWaterMain_dict,
    Hydrology_dict,
    CommunityDistrictBoundaries_dict,
    CityBoundary_dict,
]


#### function that fetches and saves a geojson layer, given a dict with name and url-link
def fetch_city_layer(layer_dict):
    layer_name = layer_dict[NAME]
    print(f"Fetching {layer_name}")
    geojson_url = layer_dict[LINK]
    payload = {"includeSynthetic": False,}
    # `"includeSynthetic": False` prevents auto-generated, made-up columns from showing up, which are annoying
    with httpx.Client(timeout=30.0) as client:
            response = client.post(
                geojson_url,
                json=payload,
                headers={"X-App-Token": DATABASE_CONFIG.app_token.get_secret_value()},
                auth=(
                    DATABASE_CONFIG.api_key.get_secret_value(),
                    DATABASE_CONFIG.api_secret_key.get_secret_value(),
                ),
            )
    response.raise_for_status()
    json_result = gpd.GeoDataFrame(response.json())["features"]
    gdf = gpd.GeoDataFrame.from_features(json_result, crs="EPSG:4326")
    engine = default_SQL_engine()
    gdf.to_postgis(layer_name, engine, if_exists="replace", index=False,)


#### loop through all my layers
for layer in city_layers: fetch_city_layer(layer)



########################################################################################################################
### END - print script finish statement
print(f"Script: {__file__} completed at {datetime.now()}")