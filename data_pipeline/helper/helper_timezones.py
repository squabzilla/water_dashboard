########################################################################################################################
# file name: helper_timezones.py
# author: William Hovdestad
#
# This is very simply code that just declares some timezone variables
# so I don't have to rewrite them for script that uses timezones, and ensures consistency
#
# A lot of my code is written assuming that the default timezone is the AB timezone.
# However, given that long-term I'm going to upload this to DigitalOcean or something,
# I want to make sure I explicitly call out whatever timezone I'm using.



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


# the rest of it
from zoneinfo import ZoneInfo
AB_TIME = ZoneInfo("America/Edmonton")
UTC_TIME = ZoneInfo("UTC")