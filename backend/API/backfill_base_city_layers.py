"""
file name: fetch_city_shapes.py
author: William Hovdestad

The goal of this script is to retrieve "static" city shapes for my water main break dashboard:
1.    public water main
2.    city boundary
3.    community boundaries
4.    hydrology
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
# get path for environment so I can load it later



########################################################################################################################
### script-setup 2: library imports
from datetime import datetime # for getting date-time stuff
import psycopg # stuff needed to connect with postgis database
import pandas as pd # dataframe library, for when I'm not ready to make the DataFrame all Geo quite yet
import geopandas as gpd # geospatial library, used for GeoDataFrames
import httpx # used for calling API
import json # used for handling export of json data
import logging

# custom modules!
from backend.helper.helper_progress_bar import update_progress_bar
from backend.helper.helper_API_try_except_job import try_except_city_API
from backend.helper.helper_PSQL_config import default_SQL_engine, DATABASE_CONFIG
from backend.helper.helper_timezones import AB_TIME
from backend.helper.helper_API_errors import DBError



########################################################################################################################
### script-setup 3: logging config
logfile = Path(PROJECT_ROOT) / "backend" / "API" / "log_files" / "backfill_base_city_layers.log"
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
### section 1: set up variables for API calls

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



########################################################################################################################
### section 2: function that fetches and saves a geojson layer, given a dict with name and url-link

def fetch_city_layer(layer_dict: dict) -> None:
    layer_name = layer_dict[NAME]
    #print(f"Fetching {layer_name}")
    geojson_url = layer_dict[LINK]
    payload = {"includeSynthetic": False,}
    job_name = f"fetching city layer {layer_name}"
    # `"includeSynthetic": False` prevents auto-generated, made-up columns from showing up, which are annoying
    
    response = try_except_city_API(job_name=job_name, url=geojson_url, payload=payload)
    json_result = gpd.GeoDataFrame(response)["features"]
    gdf = gpd.GeoDataFrame.from_features(json_result, crs="EPSG:4326")
    engine = default_SQL_engine()
    try:
        gdf.to_postgis(layer_name, engine, if_exists="replace", index=False,)
        logger.info(f"Posted {layer_name} to PostGIS Database")
    except:
        raise DBError(f"Error - could not upload {layer_name} to PostGIS Database")



########################################################################################################################
### section 3: main - loop through all my layers
         
def main() -> None:
    # log start
    logger.info(f"Script: {__file__} started at {datetime.now(AB_TIME)}")# print statement for start of script, and current time

    # start progress bar for fun
    progress_bar_count = 0
    total_iterations = len(city_layers)
    progress_bar_prefix = "Fetching city layers..."
    update_progress_bar(iteration=progress_bar_count, total=total_iterations, prefix=progress_bar_prefix) # first iteration is 0

    # loop through layers, with exceptions ready
    for layer in city_layers:
        fetch_city_layer(layer)
        # progress bar part!
        progress_bar_count += 1
        update_progress_bar(iteration=progress_bar_count, total=total_iterations, prefix=progress_bar_prefix)

    # log end
    print("") # print statement to fixup progress bar
    logger.info(f"Script: {__file__} completed at {datetime.now(AB_TIME)}")# print statement for end of script, and current time


# call main
# this function will run by itself if this script is called, including the start & end time pieces
if __name__ == "__main__":
    main()