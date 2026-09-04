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
BASH_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# complicated line, *ensuring* we get the directory the script is located in
# that's because the path to the script directory varies by where the git repo was cloned into
SCRIPT_DIR="$BASH_DIR/API"

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



########################################################################################################################
### creation and explanation of full cron-job-entry-command that we'll be running if everything is good

# name of run-daily bash script
BASH_DAILY="cron_tasks_daily.sh"
# full-text of the CRON job we want scheduled to run DAILY in CRON
CRON_DAILY="$CRON_SCHEDULE_DAILY cd $BASH_DIR && ./$BASH_DAILY"

# name of the run-hourly bash script
BASH_HOURLY="cron_tasks_hourly.sh"
# full-text of the CRON job we want scheduled to run HOURLY in CRON
CRON_HOURLY="$CRON_SCHEDULE_HOURLY cd $BASH_DIR && ./$BASH_HOURLY"



########################################################################################################################
### Create parallel arrays for the py-scripts and cron-scripts, so I can loop through them
### NOTE:
### While I'd prefer some sort of array-of-array structure so I can pair the relevant PyScripts and CronJobs,
### Bash doesn't support multidimensional arrays like this.
### So parallel arrays is the cleanest way to do this.

BASH_SCRIPTS=("$BASH_DAILY" "$BASH_HOURLY")
CRON_JOBS=("$CRON_DAILY" "$CRON_HOURLY")

# NOTE: this is way over-engineered because originally I had planned to potentially have LOTS of Python scipts scheduled,
# but later decided I'd do one BASH script calling all the Python scripts that have the same schedule
# (and I only ever planned to have 2 schedules: DAILY and HOURLY)



########################################################################################################################
### for-loop, to loop through all of our scripts

### START OF FOR-LOOP HERE ##################################
for i in "${!BASH_SCRIPTS[@]}"; do
# NOTE:
# `BASH_SCRIPTS[@]` refers to all elements of the array `BASH_SCRIPTS`
# the `${...}` syntax is the parameter/array expansion syntax
# (remember that `$` tells bash to treat the following thing as a variable, not a string
# add the exclamation mark `!`, and changing `${VARNAME[@]}` to `${!VARNAME[@]}` gets is the indices/keys instead of the values
# by getting the index value, it means we can loop through both scripts in parallel
    
    TEMP_BASH_SCRIPT="${BASH_SCRIPTS[$i]}" # <- this syntax gets us the i'th value from the array BASH_SCRIPTS
    TEMP_CRON_JOB="${CRON_JOBS[$i]}" # <- this syntax gets us the i'th value from the array CRON_JOBS

    ### if-statements, to ensure idempotency, or in other words: 
    ### making sure running `setup_cron.sh` won't create duplicate cron entries
    ### START OF IF STATEMENT HERE ##############################
    if crontab -l 2>/dev/null | grep -qF "$TEMP_BASH_SCRIPT"; then

        echo "Cron job already exists — skipping."
        # explanation of "if" statement:
        # `crontab -l` prints users crontab things, but gives an error if nothing is found, which is dumb?
        # so `2>/dev/null` redirects the error to a special null file that ignores it, and lets us ignore it
        # `|` pipes stdout from `crontab -l` into next thing, which is:
        # `grep -qF "$TEMP_BASH_SCRIPT"` - grep searches TEMP_BASH_SCRIPT for stuff (searches previous thing that was piped into it)
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