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


UV_BIN="$(which uv)" # gets path of UV bin
LOG_FILE="$SCRIPT_DIR/fetch_daily.log" # making a log file is probably useful lol

# python scripts we wanna schedule jobs for go here!
PYTHON_SCRIPT_1="$SCRIPT_DIR/fetch_daily_weather.py" # gets path of python script

########################################################################################################################
### cron explanation part 1 - time-code command
# * * * * * command
# order is:
# <minute (0-59)>   <hour (0-23)>   <day (1-31)>   <month (1-12)>   <day-of-week (0-7)>
# note - both 0 and 7 count as day-of-week for cron
# so every day at 2am is:  `0 2 * * *`
# and every hour would be: `0 * * * *`

CRON_SCHEDULE_DAILY="0 2 * * *"
CRON_SCHEDULE_HOURLY="0 * * * *"

########################################################################################################################
### verify uv exists
if [ -z "$UV_BIN" ]; then
# this statement checks if "$UV_BIN" matches the `-z` flag, which is the empty-string
echo "Error: 'uv' not found in PATH. Install it first."
exit 1
fi

########################################################################################################################
### creationg and explanation of full cron-job-entry-command that we'll be running if everything is good

CRON_JOB_1="$CRON_SCHEDULE_DAILY cd $SCRIPT_DIR && $UV_BIN run $PYTHON_SCRIPT_1 >> $LOG_FILE 2>&1"
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
### other cron commands go here
# (placeholder)



########################################################################################################################
### if-statements, to ensure idempotency, or in other words: 
### making sure running `setup_cron.sh` won't create duplicate cron entries
if crontab -l 2>/dev/null | grep -qF "$PYTHON_SCRIPT_1"; then
echo "Cron job already exists — skipping."
# explanation of "if" statement:
# `crontab -l` prints users crontab things, but gives an error if nothing is found, which is dumb?
# so `2>/dev/null` redirects the error to a special null file that ignores it, and lets us ignore it
# `|` pipes stdout from `crontab -l` into next thing, which is:
# `grep -qF "$PYTHON_SCRIPT_1"` - grep searches PYTHON_SCRIPT_1 for stuff (searches previous thing that was piped into it)
# -q makes grep output quiet since we don't need it to print success/failure; -F means "regular string not regex" because oh god regex a filepath? GG
else
(crontab -l 2>/dev/null; echo "$CRON_JOB_1") | crontab -
# explanation of else statement:
# `crontab -l 2>/dev/null` is the same thing that prints our existing cron jobs, but ignores "wah no cron file exists" error
# `;` is a command separator, so that `echo "$CRON_JOB_1"` happens after first half, 
# and the brackets combined these into a sub-shell, so the output can be piped together
# and the reason to pipe them together is:
# CRON HAS NO APPEND FLAG
# so we pipe everything in the brackets (using `|`) into `crontab -`, with the trailing-hyphen telling crontab to use `stdin`,
# rather than using interactive text editor
# USEFUL REFERENCE:
# https://unix.stackexchange.com/questions/322900/is-it-possible-to-write-to-the-crontab-from-a-multipurpose-script 

# oh, uh, I guess add an echo statement to tell user shit?
echo "Cron job installed:"
echo "  $CRON_JOB_1"
fi



########################################################################################################################
### other if-statements go here I guess lol