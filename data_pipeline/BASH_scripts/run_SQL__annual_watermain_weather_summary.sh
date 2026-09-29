#!/usr/bin/env bash
# remember we need chmod +x script.sh to make executable!



########################################################################################################################
# file name: run_SQL__annual_watermain_weather_summary.sh
# author: William Hovdestad
#
# This file exists specifically to use the `run_SQL.sh` script with the `annual_watermain_weather_summary.sql` file,
# in order to get said SQL script to actually be ran on our database.
#
# Usage:
#   ./run_SQL__annual_watermain_weather_summary.sh



########################################################################################################################
### setup, config, main logic
### - create some variables, set configuration options, get project directory, make more variables, run the thing

# some error handling stuff
set -euo pipefail

# get current dir
CURRENT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# setup local env variable
LOCAL_ENV_NAME="01__PROJECT_DIR__BASH_scripts.env"
LOCAL_ENV_FILEPATH="$CURRENT_DIR/$LOCAL_ENV_NAME"

# import project directory variable
set -a
# shellcheck disable=SC1090
source "$LOCAL_ENV_FILEPATH" # ignore that shellcheck can't confirm if <variable> is proper path or not
set +a
# check that the variable we want exists and is not empty
if [[ -z "${PROJECT_DIR:-}" ]]; then
    echo "Error: PROJECT_DIR not set in $PROJECT_DIR" >&2
    exit 1
fi


RUN_SQL="$PROJECT_DIR/data_pipeline/BASH_scripts/./run_SQL.sh"
SQL_FOLDER="$PROJECT_DIR/data_pipeline/SQL_scripts"
SQL_NAME="annual_watermain_weather_summary.sql"
SQL_FILEPATH="$SQL_FOLDER/$SQL_NAME"

CMD="$RUN_SQL $SQL_FILEPATH"
eval "$CMD"