#!/usr/bin/env bash
# remember we need chmod +x script.sh to make executable!
# this script wraps two operations:
# 1. sourcing .env file and exporting them as environment variables
# see: https://stackoverflow.com/a/65694371
# see: https://www.gnu.org/software/bash/manual/html_node/The-Set-Builtin.html
# 2. calling a python script that has plan `os.environ.get` code, so it can fetch these variables
# NOTE: while this was an interesting exercise in avoiding external libraries,
# turns out that the "dotenv" (or rather "python-dotenv") package is a dependency of the
# "uvicorn" package I'm using, so I may as well use it directly

# first: we gotta move to our main `water_dashboard` folder
# let's add a check ensuring that we're there

# what we want our main-dir to be
wanted_dir="water_dashboard"
# relative-movement to desired directory
cd ..
# what our actual-dir is
actual_dir=$(basename $(pwd))
# only do the stuff if wanted_dir = actual_dir
if [[ "$wanted_dir" == "$actual_dir" ]]; then
# `set -a` explanation: Each variable or function that is created or modified is given the export
#                       attribute and marked for export to the environment of subsequent commands.
set -a
source .env
# `set +a` explanation: Using ‘+’ rather than ‘-’ causes these options to be turned off.
set +a
# move back to directory of script
cd backend
# run script from backend
uv run fetch_hourly.py
fi