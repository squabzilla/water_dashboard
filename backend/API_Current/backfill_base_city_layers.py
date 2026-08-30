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



########################################################################################################################
### script-setup 2: library imports
#import argparse # used for adding command line arguments to script
from datetime import datetime # used to get current time
import psycopg # stuff needed to connect with postgis database
import pandas as pd # dataframe library, for when I'm not ready to make the DataFrame all Geo quite yet
import geopandas as gpd # geospatial library, used for GeoDataFrames
import httpx # used for calling API
import json # used for handling export of json data
import logging
# lets add tenacity
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

# custom modules!
from backend.helper.helper_progress_bar import update_progress_bar
from backend.helper.helper_error import CustomErrorMessage
from backend.helper.helper_API_try_except_job import try_except_city_API
from backend.helper.helper_PSQL_config import default_SQL_engine, DATABASE_CONFIG
from backend.helper.helper_API_errors import DataPipelineError, \
    APITimeoutError, APIConnectError, APIResponseError, DBError



########################################################################################################################
### script-setup 3: logging config
logfile = Path(PROJECT_ROOT) / "backend" / "API_Current" / "log_files" / "backfill_base_city_layers.log"
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

"""# let's add tenacity stuff here
@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    # decorator itself, and the condition for retrying anything at all
    stop=stop_after_attempt(4), # tells tenacity when to give up - after 4 attemps (1 initial call, 3 retries)
    wait=wait_exponential(multiplier=1, min=2, max=30),
    # wait an increasing time between each attempt;
    # the `max` setting is redundant since we stop after attempt 4, but redundancy is good in this case
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
"""
def fetch_city_layer(layer_dict: dict) -> None:
    layer_name = layer_dict[NAME]
    #print(f"Fetching {layer_name}")
    geojson_url = layer_dict[LINK]
    payload = {"includeSynthetic": False,}
    job_name = f"fetching city layer {layer_name}"
    # `"includeSynthetic": False` prevents auto-generated, made-up columns from showing up, which are annoying
    """
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
    """
    response = try_except_city_API(job_name=job_name, url=geojson_url, payload=payload)
    #json_result = gpd.GeoDataFrame(response.json())["features"]
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
    logger.info(f"Script: {__file__} started at {datetime.now()}")# print statement for start of script, and current time
    # loop through layers, with exceptions ready
    for layer in city_layers:
        layer_name = layer[NAME]
        fetch_city_layer(layer)
        """
        try:
            fetch_city_layer(layer)
        except httpx.TimeoutException as e:
            raise APITimeoutError(f"Timed out fetching layer {layer_name} after retries") from e
        except httpx.ConnectError as e:
            raise APIConnectError(f"Connection error fetching layer {layer_name} after retries") from e
        except httpx.HTTPStatusError as e:
            raise APIResponseError(f"Bad status fetching layer {layer_name}: {e.response.status_code}") from e
        except (KeyError, json.JSONDecodeError) as e:
            raise APIResponseError(f"Malformed page while paginating layer {layer_name}: {e}") from e
        except Exception as e:
            raise DataPipelineError(f"Unexpected error while fetching layer {layer_name}: {e}") from e
        """
    # log end
    logger.info(f"Script: {__file__} completed at {datetime.now()}")# print statement for end of script, and current time


# call main
# this function will run by itself if this script is called, including the start & end time pieces
if __name__ == "__main__":
    main()
    



