####################################################################################################
# file name: fetch_current.py
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
# set PROJECT_ROOT so libraries from cousin folders import properly
# note that I want the main directory and file is `scripts`, a sub-directory of main,
#  so I need grand-parent folder instead of simply parent-folder

# gets file-path, (hopefully) resolves relative path issues, gets grand-parent folder
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# sets working directory to project root - there may be redundancy here but oh well lol
os.chdir(PROJECT_ROOT)
# Ensure repository code is importable when this wrapper is run directly.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))



####################################################################################################
### script-setup 2: library imports
import httpx # used for calling API
from dateutil.parser import parse # used for properly formatting DATE data into datetime variables
import json # used for handling export of json data
from dotenv import load_dotenv



####################################################################################################
### starting real code here lol

print(f"Project root:\n{PROJECT_ROOT}")