#!/usr/bin/env bash
# remember we need chmod +x script.sh to make executable!



########################################################################################################################
# file name: bash_backfill.sh
# author: William Hovdestad
#
# Simple script to call the API-data-fetching scripts, for backfilling that  I only need to run once at project setup.
# NOTE: the bash script doesn't make logs, because the Python scripts themselves do



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
BASH_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# complicated line, *ensuring* we get the directory the script is located in
# that's because the path to the script directory varies by where the git repo was cloned into
SCRIPT_DIR="$BASH_DIR/API"

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


################
### set log file
################
# EXPLAINING:
# > /dev/null 2>> $BASH_LOG 
# `2>> $BASH_LOG` sends `stderr` to my BASH log

BASH_BACKFILL_LOG="$SCRIPT_DIR/log_files/BASH_BACKFILL.log"


########################################################################################################################
### function to run a job
run_job() {
    local job_name="$1"
    local job_cmd="$2"
    echo "$(date '+%F %T') starting $job_name" | tee -a "$BASH_BACKFILL_LOG"
    # NOTE: `tee` is a function that splits output (like output from previous echo) in two streams
    # first stream is regular stdout, meaning I can see the echo statement, while the second appends it to $BASH_BACKFILL_LOG
    eval "$job_cmd"
    local exit_code=$?
    echo "$(date '+%F %T') $job_name exit=$exit_code" | tee -a "$BASH_BACKFILL_LOG"
}
# (date '+%F %T') -> gets date in 'YYYY-MM-DD HH:MM:SS' format



########################################################################################################################
### setup variables for backfill scripts

NAME__backfill_base_city_layers="backfill_base_city_layers"
PYSCRIPT__backfill_base_city_layers="$SCRIPT_DIR/backfill_base_city_layers.py"
JOB__backfill_base_city_layers="cd $SCRIPT_DIR && $UV_BIN run $PYSCRIPT__backfill_base_city_layers 2>> $BASH_BACKFILL_LOG"

NAME__waterMainBreaks_backfill="waterMainBreaks_backfill"
PYSCRIPT__waterMainBreaks_backfill="$SCRIPT_DIR/waterMainBreaks_backfill.py"
JOB__waterMainBreaks_backfill="cd $SCRIPT_DIR && $UV_BIN run $PYSCRIPT__waterMainBreaks_backfill 2>> $BASH_BACKFILL_LOG"

NAME__weatherData_backfillDaily="weatherData_backfillDaily"
PYSCRIPT__weatherData_backfillDaily="$SCRIPT_DIR/weatherData_backfillDaily.py"
JOB__weatherData_backfillDaily="cd $SCRIPT_DIR && $UV_BIN run $PYSCRIPT__weatherData_backfillDaily 2>> $BASH_BACKFILL_LOG"

NAME__weatherData_backfillHourly="weatherData_backfillHourly"
PYSCRIPT__weatherData_backfillHourly="$SCRIPT_DIR/weatherData_backfillHourly.py"
JOB__weatherData_backfillHourly="cd $SCRIPT_DIR && $UV_BIN run $PYSCRIPT__weatherData_backfillHourly 2>> $BASH_BACKFILL_LOG"

NAME__weatherData_weatherStations="weatherData_weatherStations"
PYSCRIPT__weatherData_weatherStations="$SCRIPT_DIR/weatherData_weatherStations.py"
JOB__weatherData_weatherStations="cd $SCRIPT_DIR && $UV_BIN run $PYSCRIPT__weatherData_weatherStations 2>> $BASH_BACKFILL_LOG"

# backfill of hourly-swob-records to be ran with backfill as well!
NAME__weatherData_updateHourlyWeather_runHourly="weatherData_updateHourlyWeather_runHourly"
PYSCRIPT__weatherData_updateHourlyWeather_runHourly="$SCRIPT_DIR/weatherData_updateHourlyWeather_runHourly.py"
JOB__weatherData_updateHourlyWeather_runHourly="cd $SCRIPT_DIR && $UV_BIN run $PYSCRIPT__weatherData_updateHourlyWeather_runHourly -hrs 48 2>> $BASH_BACKFILL_LOG"
# gotta remember that 48 hour backfill for new jobs!



########################################################################################################################
### HIT IT
run_job "$NAME__backfill_base_city_layers" "$JOB__backfill_base_city_layers"
run_job "$NAME__waterMainBreaks_backfill" "$JOB__waterMainBreaks_backfill"
run_job "$NAME__weatherData_backfillDaily" "$JOB__weatherData_backfillDaily"
run_job "$NAME__weatherData_backfillHourly" "$JOB__weatherData_backfillHourly"
run_job "$NAME__weatherData_weatherStations" "$JOB__weatherData_weatherStations"
run_job "$NAME__weatherData_updateHourlyWeather_runHourly" "$JOB__weatherData_updateHourlyWeather_runHourly"



########################################################################################################################
### test my cron_tasks scripts while we're at it, make sure they work

echo "testing \`cron_tasks_daily.sh\`"
cron_daily_cmd=".\\cron_tasks_daily.sh 2>> $BASH_BACKFILL_LOG"
eval "$cron_daily_cmd"

echo "testing \`cron_tasks_hourly.sh\`"
cron_hourly_cmd=".\\cron_tasks_hourly.sh 2>> $BASH_BACKFILL_LOG"
eval "$cron_hourly_cmd"