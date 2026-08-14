#!/usr/bin/env bash
# remember we need chmod +x script.sh to make executable!



########################################################################################################################
# file name: bash_fetch.sh
# author: William Hovdestad
#
# Simple script to call the API-data-fetching scripts I only need to run once at project setup.



########################################################################################################################
### setup - create some variables, set configuration options

# some error handling stuff
# set -euo pipefail
set -uo pipefail
# Explanation:
# `set -e` - exit immediately if any command returns an error code, instead of plowing ahead
# actually, I DON'T want that here, I want it to keep running my other py-scripts
# `set -u` - treat unset variables as errors
# `set -o pipefail` - in pipelines specifically, such as `cmd1 | cmd2 | cmd3`, 
# only the exit (error) code of the LAST command is reported. This makes pipeline fail
# if ANY command in it fails, not just the last one.
# This isn't relevant to my script at the moment, but it's good general practice & future-proofing



########################################################################################################################
### basic config

# Source - https://stackoverflow.com/a/246128
# Posted by dogbane, modified by community. See post 'Timeline' for change history
# Retrieved 2026-05-22, License - CC BY-SA 4.0
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# complicated line, *ensuring* we get the directory the script is located in
# that's because the path to the script directory varies by where the git repo was cloned into

# gets path of UV bin
UV_BIN="$(which uv)"


####################
### verify uv exists
####################
if [ -z "$UV_BIN" ]; then
# this statement checks if "$UV_BIN" matches the `-z` flag, which is the empty-string
echo "Error: 'uv' not found in PATH. Install it first."
exit 1
fi



########################################################################################################################
### setup variables for fetch-once scripts
FETCH_ONCE_DIR="$SCRIPT_DIR/API_fetch_once"

# fetch_dailyWeather_historical
# fetch_hourlyWeather_historical
# fetch_shapes

PYSCRIPT__fetch_dailyWeather_historical="$FETCH_ONCE_DIR/fetch_dailyWeather_historical.py"
LOG__fetch_dailyWeather_historical="$FETCH_ONCE_DIR/LOG_fetch_dailyWeather_historical.log"
JOB__fetch_dailyWeather_historical="cd $FETCH_ONCE_DIR && $UV_BIN run $PYSCRIPT__fetch_dailyWeather_historical -s >> $LOG__fetch_dailyWeather_historical 2>&1"

PYSCRIPT__fetch_hourlyWeather_historical="$FETCH_ONCE_DIR/fetch_hourlyWeather_historical.py"
LOG__fetch_hourlyWeather_historical="$FETCH_ONCE_DIR/LOG_fetch_hourlyWeather_historical.log"
JOB__fetch_hourlyWeather_historical="cd $FETCH_ONCE_DIR && $UV_BIN run $PYSCRIPT__fetch_hourlyWeather_historical -s >> $LOG__fetch_hourlyWeather_historical 2>&1"

PYSCRIPT__fetch_shapes="$FETCH_ONCE_DIR/fetch_shapes.py"
LOG__fetch_shapes="$FETCH_ONCE_DIR/LOG_fetch_shapes.log"
JOB__fetch_shapes="cd $FETCH_ONCE_DIR && $UV_BIN run $PYSCRIPT__fetch_shapes >> $LOG__fetch_shapes 2>&1"



########################################################################################################################
### run the fetch-once scripts


echo "BASH: starting \`$FETCH_ONCE_DIR/fetch_dailyWeather_historical.py\`..."
eval "$JOB__fetch_dailyWeather_historical"

echo "BASH: starting \`$FETCH_ONCE_DIR/fetch_hourlyWeather_historical.py\`..."
eval "$JOB__fetch_hourlyWeather_historical"

echo "BASH: starting \`$FETCH_ONCE_DIR/fetch_shapes.py\`..."
eval "$JOB__fetch_shapes"

echo "done"