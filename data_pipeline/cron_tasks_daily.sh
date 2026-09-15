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

BASH_RUN_DAILY_LOG="$SCRIPT_DIR/log_files/BASH_RUN_DAILY.log"



########################################################################################################################
### function to run a job
run_job() {
    local job_name="$1"
    local job_cmd="$2"
    echo "$(date '+%F %T') starting $job_name" | tee -a "$BASH_RUN_DAILY_LOG"
    # NOTE: `tee` is a function that splits output (like output from previous echo) in two streams
    # first stream is regular stdout, meaning I can see the echo statement, while the second appends it to $BASH_RUN_DAILY_LOG
    eval "$job_cmd"
    local exit_code=$?
    echo "$(date '+%F %T') $job_name exit=$exit_code" | tee -a "$BASH_RUN_DAILY_LOG"
    # make non-zero exit codes REALLY obvious
    if [[ "$exit_code" -ne 0 ]]; then
        echo "$(date '+%F %T') ##### ERROR: $job_name EXITED WITH NON-ZERO EXIT CODE: $exit_code" | tee -a "$BASH_RUN_DAILY_LOG"
    fi
}
# (date '+%F %T') -> gets date in 'YYYY-MM-DD HH:MM:SS' format



########################################################################################################################
### setup variables for fetch-daily scripts

NAME__weatherData_updateDailyWeather_runDaily="weatherData_updateDailyWeather_runDaily"
PYSCRIPT__weatherData_updateDailyWeather_runDaily="$SCRIPT_DIR/weatherData_updateDailyWeather_runDaily.py"
JOB__weatherData_updateDailyWeather_runDaily="cd $SCRIPT_DIR && $UV_BIN run $PYSCRIPT__weatherData_updateDailyWeather_runDaily 2>> $BASH_RUN_DAILY_LOG"

NAME__weatherData_updateHourlyWeather_runDaily="weatherData_updateHourlyWeather_runDaily"
PYSCRIPT__weatherData_updateHourlyWeather_runDaily="$SCRIPT_DIR/weatherData_updateHourlyWeather_runDaily.py"
JOB__weatherData_updateHourlyWeather_runDaily="cd $SCRIPT_DIR && $UV_BIN run $PYSCRIPT__weatherData_updateHourlyWeather_runDaily 2>> $BASH_RUN_DAILY_LOG"

NAME__waterMainBreaks_checkAPI_runDaily="waterMainBreaks_checkAPI_runDaily"
PYSCRIPT__waterMainBreaks_checkAPI_runDaily="$SCRIPT_DIR/waterMainBreaks_checkAPI_runDaily.py"
JOB__waterMainBreaks_checkAPI_runDaily="cd $SCRIPT_DIR && $UV_BIN run $PYSCRIPT__waterMainBreaks_checkAPI_runDaily 2>> $BASH_RUN_DAILY_LOG"



########################################################################################################################
### HIT IT
run_job "$NAME__weatherData_updateDailyWeather_runDaily" "$JOB__weatherData_updateDailyWeather_runDaily"
run_job "$NAME__weatherData_updateHourlyWeather_runDaily" "$JOB__weatherData_updateHourlyWeather_runDaily"
run_job "$NAME__waterMainBreaks_checkAPI_runDaily" "$JOB__waterMainBreaks_checkAPI_runDaily"