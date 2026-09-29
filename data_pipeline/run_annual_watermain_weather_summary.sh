#!/usr/bin/env bash
# remember we need chmod +x script.sh to make executable!



########################################################################################################################
# file name: run_annual_watermain_weather_summary.sh
# author: William Hovdestad
#
# Runs annual_watermain_weather_summary.sql against the calgary_watermains database. 
# POSTGRES_USER and POSTGRES_PASSWORD are read from a .env file that is not committed to the repo.
#
# Usage:
#   ./run_annual_watermain_weather_summary.sh 



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
### config

# Source - https://stackoverflow.com/a/246128
# Posted by dogbane, modified by community. See post 'Timeline' for change history
# Retrieved 2026-05-22, License - CC BY-SA 4.0
BASH_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_DIR=$(dirname "$BASH_DIR")
# complicated line, *ensuring* we get the directory the script is located in
# that's because the path to the script directory varies by where the git repo was cloned into

#SCRIPT_DIR="$BASH_DIR/SQL_scripts"

ENV_PATH_POINTER="$PROJECT_DIR/.ENV_PATH"

# `set -a` explanation: Each variable or function that is created or modified is given the export
#                       attribute and marked for export to the environment of subsequent commands.
set -a

# `shellcheck` is a useful thing to check shell-scripts, but also, 
# gets mad at using `source` on stuff it doesn't know is a filepath
# so we put in the following thing, so it doesn't get mad at a specific error on the next line:
# shellcheck disable=SC1090
source "$ENV_PATH_POINTER" # this gets variables from objects in that file - so now we know ENV file location...
# shellcheck disable=SC1090
source "$ENV_FILE" # now we source our .env file ahahahahaha

# `set +a` explanation: Using ‘+’ rather than ‘-’ causes these options to be turned off.
set +a
echo "$ENV_FILE"

SQL_FILE="$BASH_DIR/SQL_scripts/annual_watermain_weather_summary.sql"



########################################################################################################################
### some errors

# --- Preconditions: fail loudly, not silently ---------------------------
 
if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: .env file not found at: $ENV_FILE" >&2
    exit 1
fi
 
if [[ ! -f "$SQL_FILE" ]]; then
    echo "ERROR: SQL file not found at: $SQL_FILE" >&2
    exit 1
fi
 
if ! command -v psql >/dev/null 2>&1; then
    echo "ERROR: psql is not installed or not on PATH." >&2
    exit 1
fi