"""
author: William Hovdestad
file name: helper_env_dir.py

This is a very basic file that just stores the location of the environment directory.

That way, if I pull this to another machine, I have a very-visible and easily-editable way
to adjust where my code looks for the .env file that contains super-secret info I don't want
to upload to GitHub.
"""


########################################################################################################################
### script-setup 1: project-root-setup
import os
import sys
from pathlib import Path

# gets file-path, (hopefully) resolves relative path issues, gets great-grand-parent folder
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# sets working directory to project root - there may be redundancy here but oh well lol
os.chdir(PROJECT_ROOT)
# Ensure repository code is importable when this wrapper is run directly.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))



########################################################################################################################
### section 1: the directory
ENV_DIRPATH = r"~/.config/water_dashboard/.env"