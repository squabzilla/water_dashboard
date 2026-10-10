#!/usr/bin/env bash
# remember we need chmod +x script.sh to make executable!



########################################################################################################################
# file name: start_FastAPI.sh
# author: William Hovdestad
#
# Script to run terminal command to start FastAPI so I don't have to remember it 



########################################################################################################################
### BOILERPLATE setup

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
### BOILERPLATE config

# Source - https://stackoverflow.com/a/246128
# Posted by dogbane, modified by community. See post 'Timeline' for change history
# Retrieved 2026-05-22, License - CC BY-SA 4.0
CURRENT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
# complicated line, *ensuring* we get the directory the script is located in
# that's because the path to the script directory varies by where the git repo was cloned into
LOCAL_ENV_NAME="01__PROJECT_DIR__BASH_scripts.env"
LOCAL_ENV_FILEPATH="$CURRENT_DIR/$LOCAL_ENV_NAME"



########################################################################################################################
### actual start of script

cmd="uv run uvicorn backend.backend_main:app --reload --reload-dir backend --reload-dir data_pipeline"
eval "$cmd"