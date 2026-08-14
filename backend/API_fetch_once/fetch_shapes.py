########################################################################################################################
# file name: fetch_city_shapes.py
# author: William Hovdestad
#
# The goal of this script is to retrieve "static" city shapes for my water main break dashboard:
# 1.    public water main
# 2.    city boundary
# 3.    community boundaries
# 4.    water pressure zones
# 5.    rainfall gauge locations
# 6.    hydrology



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