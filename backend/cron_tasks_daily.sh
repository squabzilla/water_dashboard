#!/usr/bin/env bash
# remember we need chmod +x script.sh to make executable!



########################################################################################################################
# file name: cron_tasks_daily.sh
# author: William Hovdestad
#
# This script is intended to be ran every DAY by a CRON job.
# This script will sequentially run every CRON job that I want run on a daily basis.



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
### setup variables for fetch-daily scripts
FETCH_DAILY_DIR="$SCRIPT_DIR/API_fetch_daily"

# fetch_dailyWeather_daily
# fetch_hourlyWeather_daily

PYSCRIPT__fetch_dailyWeather_daily="$FETCH_DAILY_DIR/fetch_dailyWeather_daily.py"
LOG__fetch_dailyWeather_daily="$FETCH_DAILY_DIR/LOG__fetch_dailyWeather_daily.log"
JOB__fetch_dailyWeather_daily="cd $FETCH_DAILY_DIR && $UV_BIN run $PYSCRIPT__fetch_dailyWeather_daily -s >> $LOG__fetch_dailyWeather_daily 2>&1"

PYSCRIPT__fetch_hourlyWeather_daily="$FETCH_DAILY_DIR/fetch_hourlyWeather_daily.py"
LOG__fetch_hourlyWeather_daily="$FETCH_DAILY_DIR/LOG__fetch_hourlyWeather_daily.log"
JOB__fetch_hourlyWeather_daily="cd $FETCH_DAILY_DIR && $UV_BIN run $PYSCRIPT__fetch_hourlyWeather_daily >> $LOG__fetch_hourlyWeather_daily 2>&1"



########################################################################################################################
### run the fetch-once scripts

echo "BASH: starting \`$FETCH_DAILY_DIR/fetch_dailyWeather_daily.py\`..."
eval "$JOB__fetch_dailyWeather_daily"

echo "BASH: starting \`$FETCH_DAILY_DIR/fetch_hourlyWeather_daily.py\`..."
eval "$JOB__fetch_hourlyWeather_daily"

echo "done"