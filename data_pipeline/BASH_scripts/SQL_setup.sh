#!/usr/bin/env bash
# remember we need chmod +x script.sh to make executable!



########################################################################################################################
# file name: run_SQL.sh
# author: William Hovdestad
#
# So this file loops through any `run_SQL__<...>` scripts that I want to run when I setup my project
# remember that it's just looping through bash scripts tho - which are all themselves just wrappers
# for using `run_SQL.sh` with a specific .sql file
#
# Usage:
#   ./SQL_setup.sh



########################################################################################################################
### setup - create some variables, set configuration options

# some error handling stuff
set -euo pipefail
# Explanation:
# `set -e` - exit immediately if any command returns an error code, instead of plowing ahead
# `set -u` - treat unset variables as errors
# `set -o pipefail` - in pipelines specifically, such as `cmd1 | cmd2 | cmd3`, 
# only the exit (error) code of the LAST command is reported. This makes pipeline fail
# if ANY command in it fails, not just the last one.
# This isn't relevant to my script at the moment, but it's good general practice & future-proofing



########################################################################################################################
### config - get project directory

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

BASH_FOLDER="$PROJECT_DIR/data_pipeline/BASH_scripts"
RUN_SQL_SCRIPTS_ARRAY=(
    "run_SQL__annual_watermain_weather_summary.sh"
)

for BASH_SCRIPT in "${RUN_SQL_SCRIPTS_ARRAY[@]}"; do
    cmd="$BASH_FOLDER/./$BASH_SCRIPT"
    echo "Evaluating:    $cmd"
    eval "$cmd"
done