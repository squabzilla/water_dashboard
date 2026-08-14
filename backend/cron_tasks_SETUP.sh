#!/usr/bin/env bash
# remember we need chmod +x script.sh to make executable!



########################################################################################################################
# file name: setup_cron.sh
# author: William Hovdestad
#
# The goal of this script is to setup a cron job to run scripts at scheduled times - be it daily or hourly.
# Having a Bash script setup these jobs is part of making this repo more portable, and easy to run on another machine.



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

### python scripts we wanna schedule jobs for go here!
PY_SCRIPT__FETCH_DAILY_WEATHER="$SCRIPT_DIR/fetch_weather_daily_current.py" # gets path of python script
PY_SCRIPT__FETCH_HOURLY_WEATHER="$SCRIPT_DIR/fetch_weather_hourly_current.py"
PY_SCRIPT__FETCH_WATERMAINBREAKS="$SCRIPT_DIR/fetch_watermainBreaks.py"

### Log files - since making a log file is probably useful lol
LOG__FETCH_DAILY_WEATHER="$SCRIPT_DIR/fetch_daily_weather.log"
LOG__FETCH_HOURLY_WEATHER="$SCRIPT_DIR/fetch_hourly_weather.log" 
LOG__FETCH_WATERMAINBREAKS="$SCRIPT_DIR/fetch_watermainbreaks.log"

###############################################
### cron explanation part 1 - time-code command
# * * * * * command
# order is:
# <minute (0-59)>   <hour (0-23)>   <day (1-31)>   <month (1-12)>   <day-of-week (0-7)>
# note - both 0 and 7 count as day-of-week for cron
# so every day at 1am is:  `0 1 * * *`
# and every hour would be: `0 * * * *`

### cron-variables to implement our desired cron frequency
CRON_SCHEDULE_DAILY="0 1 * * *"
CRON_SCHEDULE_HOURLY="0 * * * *"
# NOTE:
# The hourly-weather-data API from Environment Canada, used in `fetch_weather_hourly_current.py`
# Only actually updates DAILY, only providing hourly weather up to the PREVIOUS day - not the current one.
# So until I make a web-scraper for:
# https://www.alberta.ca/acis-find-current-weather-data
# to grab the CURRENT hourly data from that site,
# my fetch-hourly-weather CRON-job will only run daily - not hourly.


####################
### verify uv exists
if [ -z "$UV_BIN" ]; then
# this statement checks if "$UV_BIN" matches the `-z` flag, which is the empty-string
echo "Error: 'uv' not found in PATH. Install it first."
exit 1
fi



########################################################################################################################
### creation and explanation of full cron-job-entry-command that we'll be running if everything is good

CRON_JOB__FETCH_DAILY_WEATHER="$CRON_SCHEDULE_DAILY cd $SCRIPT_DIR && $UV_BIN run $PY_SCRIPT__FETCH_DAILY_WEATHER >> $LOG__FETCH_DAILY_WEATHER 2>&1"
CRON_JOB__FETCH_HOURLY_WEATHER="$CRON_SCHEDULE_DAILY cd $SCRIPT_DIR && $UV_BIN run $PY_SCRIPT__FETCH_HOURLY_WEATHER >> $LOG__FETCH_HOURLY_WEATHER 2>&1"
# explanation:
# `CRON_JOB_1="..."` just assigns everything to the variable `CRON_JOB_1`
# `$CRON_SCHEDULE_DAILY` calls the variable containing code for WHEN cron runs the job
# `cd $SCRIPT_DIR &&` tells it to move to repo directory, and ONLY PROCEED IF `cd` SUCCEEDED, so script isn't run from wrong location
# ` $UV_BIN run $PYTHON_SCRIPT` - the actual command to run the script
# `>> $LOG_FILE` appends `stdout` to the logfile. Note that `>` is overwrite, `>>` is append.
# 
# aside: file descriptors
# in linux, there are three standard file descriptors (FD):
# FD    Name        Default Destination
#  0    stdin       Keyboard input
#  1    stdout      Terminal
#  2    stderr      Terminal
# HOWEVER: if the output is sent to a log file: then `stdout` will go to the file,
# but stderr will still show up in the terminal
# so if we want stderr to show up in a log file, we need to redirect it to stdout
# NOW: let's look at the last piece: `2>&1`
# `2>` means we're redirecting stderr somewhere - the 'somewhere' is `&1`
# the `&` part of `&1` says "the following thing is a file descriptor", so `&1` ends up meaning FD1, which is stdout
# so it gets redirected to the log file!



########################################################################################################################
### Create parallel arrays for the py-scripts and cron-scripts, so I can loop through them
### NOTE:
### While I'd prefer some sort of array-of-array structure so I can pair the relevant PyScripts and CronJobs,
### Bash doesn't support multidimensional arrays like this.
### So parallel arrays is the cleanest way to do this.

# script/cron-job 1: FETCH_DAILY_WEATHER
PYSCRIPT_1="$PY_SCRIPT__FETCH_DAILY_WEATHER"
CRON_JOB_1="$CRON_JOB__FETCH_DAILY_WEATHER"

# script/cron-job 2: FETCH_HOURLY_WEATHER
PYSCRIPT_2="$PY_SCRIPT__FETCH_HOURLY_WEATHER"
CRON_JOB_2="$CRON_JOB__FETCH_HOURLY_WEATHER"

PYSCRIPTS=("$PYSCRIPT_1" "$PYSCRIPT_2")
CRON_JOBS=("$CRON_JOB_1" "$CRON_JOB_2")



########################################################################################################################
### for-loop, to loop through all of our scripts

### START OF FOR-LOOP HERE ##################################
for i in "${!PYSCRIPTS[@]}"; do
# NOTE:
# `PYSCRIPTS[@]` refers to all elements of the array `PYSCRIPTS`
# the `${...}` syntax is the parameter/array expansion syntax
# (remember that `$` tells bash to treat the following thing as a variable, not a string
# add the exclamation mark `!`, and changing `${VARNAME[@]}` to `${!VARNAME[@]}` gets is the indices/keys instead of the values
# by getting the index value, it means we can loop through both scripts in parallel
    
    TEMP_PYSCRIPT="${PYSCRIPTS[$i]}" # <- this syntax gets us the i'th value from the array PYSCRIPTS
    TEMP_CRON_JOB="${CRON_JOBS[$i]}" # <- this syntax gets us the i'th value from the array CRON_JOBS

    ### if-statements, to ensure idempotency, or in other words: 
    ### making sure running `setup_cron.sh` won't create duplicate cron entries
    ### START OF IF STATEMENT HERE ##############################
    if crontab -l 2>/dev/null | grep -qF "$TEMP_PYSCRIPT"; then

        echo "Cron job already exists — skipping."
        # explanation of "if" statement:
        # `crontab -l` prints users crontab things, but gives an error if nothing is found, which is dumb?
        # so `2>/dev/null` redirects the error to a special null file that ignores it, and lets us ignore it
        # `|` pipes stdout from `crontab -l` into next thing, which is:
        # `grep -qF "$TEMP_PYSCRIPT"` - grep searches TEMP_PYSCRIPT for stuff (searches previous thing that was piped into it)
        # -q makes grep output quiet since we don't need it to print success/failure;
        # -F means "regular string not regex" because oh god regex a filepath? GG

        else
        (crontab -l 2>/dev/null; echo "$TEMP_CRON_JOB") | crontab -
        # explanation of else statement:
        # `crontab -l 2>/dev/null` is the same thing that prints our existing cron jobs, but ignores "wah no cron file exists" error
        # `;` is a command separator, so that `echo "$TEMP_CRON_JOB"` happens after first half, 
        # and the brackets combined these into a sub-shell, so the output can be piped together
        # and the reason to pipe them together is:
        # CRON HAS NO APPEND FLAG
        # so we pipe everything in the brackets (using `|`) into `crontab -`, with the trailing-hyphen telling crontab to use `stdin`,
        # rather than using interactive text editor
        # USEFUL REFERENCE:
        # https://unix.stackexchange.com/questions/322900/is-it-possible-to-write-to-the-crontab-from-a-multipurpose-script 

        # oh, uh, I guess add an echo statement to tell user shit?
        echo "Cron job installed:"
        echo "  $TEMP_CRON_JOB"

    ###  END OF IF STATEMENT HERE  ##############################
    fi

###  END OF FOR-LOOP HERE  ##################################
done
echo "Viewing existing CRON jobs:"
crontab -l

########################################################################################################################
### other if-statements go here I guess lol