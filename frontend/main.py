"""
file name: main.y
author: William Hovdestad

basic main-file for running app
"""


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
# get path for environment so I can load it later



########################################################################################################################
### script-setup 2: library imports
from datetime import datetime # for getting date-time stuff
from fastapi import FastAPI
import psycopg # stuff needed to connect with postgis database
import sqlalchemy # stuff needed to connect with postgis database
import httpx # used for calling API
import json # used for handling export of json data



########################################################################################################################
### script-setup 3: logging config



########################################################################################################################
### section 1: 
app = FastAPI()