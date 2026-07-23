#!/usr/bin/env bash
# remember we need chmod +x script.sh to make executable!



########################################################################################################################
# file name: bash_fetch.sh
# author: William Hovdestad
#
# Simple script to call my fetch-scripts in order, when starting everything out.



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
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# complicated line, *ensuring* we get the directory the script is located in
# that's because the path to the script directory varies by where the git repo was cloned into

# gets path of UV bin
UV_BIN="$(which uv)"

####################
### verify uv exists
if [ -z "$UV_BIN" ]; then
# this statement checks if "$UV_BIN" matches the `-z` flag, which is the empty-string
echo "Error: 'uv' not found in PATH. Install it first."
exit 1
fi

#echo "starting fetch historical..."
#"$UV_BIN" run "$SCRIPT_DIR/fetch_historical_weather.py"
#echo "starting fetch daily..."
#"$UV_BIN" run "$SCRIPT_DIR/fetch_daily_weather.py"
#echo "starting fetch hourly..."
#"$UV_BIN" run "$SCRIPT_DIR/fetch_hourly_weather.py"
#echo "done"

echo "starting \`fetch_weatherstation.py\`..."
"$UV_BIN" run "$SCRIPT_DIR/fetch_weatherstation.py"

echo "starting \`fetch_weather_daily_historical.py\`..."
"$UV_BIN" run "$SCRIPT_DIR/fetch_weather_daily_historical.py"

echo "starting \`fetch_weather_daily_current.py\`..."
"$UV_BIN" run "$SCRIPT_DIR/fetch_weather_daily_current.py"

echo "starting \`fetch_weather_hourly_historical.py\`..."
"$UV_BIN" run "$SCRIPT_DIR/fetch_weather_hourly_historical.py"

echo "starting \`fetch_weather_hourly_current.py\`..."
"$UV_BIN" run "$SCRIPT_DIR/fetch_weather_hourly_current.py"

echo "Done."